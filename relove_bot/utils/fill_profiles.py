import asyncio
import logging
import os
from sqlalchemy.ext.asyncio import AsyncSession

from relove_bot.config import settings
from relove_bot.db.database import close_database, get_db_session, setup_database
from relove_bot.db.models import User
from relove_bot.db.session import SessionLocal
from relove_bot.rag.pipeline import aggregate_profile_summary
from relove_bot.rag.llm import LLM
from relove_bot.services.telegram_service import get_client
from relove_bot.services import telegram_service
from relove_bot.utils.gender import detect_gender

logger = logging.getLogger(__name__)

# --- Константы для батчинга ---
DEFAULT_BATCH_SIZE = 50
DEFAULT_BATCH_DELAY_SECONDS = 5



async def select_users(gender: str = None, text_filter: str = None, user_id_list: list = None, rank_by: str = None, limit: int = 30):
    """
    Универсальный отбор пользователей по фильтрам:
    - gender: 'male', 'female', 'unknown', None
    - text_filter: строка (ищет в summary, регистр не важен)
    - user_id_list: список user_id
    - rank_by: поле для сортировки (по context)
    - limit: макс. количество результатов
    Возвращает список словарей: [{id, username, summary, gender, ...}]
    """
    async with SessionLocal() as session:
        users = (await session.execute(User.__table__.select())).fetchall()
        user_objs = []
        for row in users:
            user_id = row.id if hasattr(row, 'id') else row[0]
            if user_id_list and user_id not in user_id_list:
                continue
            user = await session.get(User, user_id)
            if not user:
                continue
            context = user.context or {}
            summary = context.get('summary')
            user_gender = context.get('gender')
            # Фильтр по полу
            if gender and user_gender != gender:
                continue
            # Фильтр по тексту
            if text_filter and summary:
                if text_filter.lower() not in summary.lower():
                    continue
                # Используем profile_summary как психопортрет
                psycho = user.profile_summary if hasattr(user, 'profile_summary') else None
                if not psycho:
                    # Если profile_summary отсутствует — пробуем сгенерировать
                    try:
                        from relove_bot.services.telegram_service import get_full_psychological_summary
                        psycho = await get_full_psychological_summary(user.id)
                        user.profile_summary = psycho
                        await session.commit()
                    except Exception as e:
                        logger.warning(f"Не удалось получить психопортрет для пользователя {user.id}: {e}")
                        psycho = None
                user_dict = {
                    'id': user.id,
                    'username': user.username,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'summary': psycho,
                    'gender': user_gender,
                }
            user_objs.append((user_dict, context))
        # Ранжирование
        if rank_by:
            def get_rank_val(u):
                val = u[1].get(rank_by)
                try:
                    return float(val)
                except (TypeError, ValueError):
                    return str(val or "")
            user_objs.sort(key=get_rank_val, reverse=True)
        # Ограничение по количеству
        user_objs = user_objs[:limit]
        # Только словари
        return [u[0] for u in user_objs]

# --- Новая асинхронная джоба для массового обновления summary ---

async def update_user_profile_summary(session: AsyncSession, user_id: int, summary: str, gender: str = None, streams: list = None):
    """Обновляет или создаёт profile_summary и gender для пользователя."""
    from relove_bot.db.models import User
    user_obj = await session.get(User, user_id)
    if user_obj:
        user_obj.profile_summary = summary
        if gender is not None:
            user_obj.gender = gender
        if streams:
            # Сохраняем только в основное поле streams, если оно есть
            if hasattr(user_obj, 'streams'):
                user_obj.streams = streams
        await session.commit()
        logger.info(f"Successfully updated profile_summary and gender for user {user_id}")
    else:
        # Пытаемся получить данные пользователя из Telegram
        from relove_bot.services import telegram_service
        tg_user = None
        try:
            client = await get_client()
            tg_user = await client.get_entity(user_id)
            username = getattr(tg_user, 'username', None)
            first_name = getattr(tg_user, 'first_name', None)
            last_name = getattr(tg_user, 'last_name', None)
        except Exception as e:
            logger.warning(f"Could not fetch Telegram user info for user {user_id}: {e}")
            username = None
            first_name = None
            last_name = None
        if gender is None:
            from relove_bot.utils.gender import detect_gender
            gender = await detect_gender(tg_user) if tg_user else 'unknown'
        
        # Если first_name пустой, используем username или 'Unknown'
        final_first_name = first_name or username or 'Unknown'
        
        new_user = User(
            id=user_id,
            username=username,
            first_name=final_first_name,
            last_name=last_name,
            is_active=True,
            markers={"gender": gender},
            profile_summary=summary,
            gender=gender
        )
        session.add(new_user)
        await session.commit()
        logger.info(f"Created new user {user_id} and set profile_summary and gender = {gender}.")

async def fill_all_profiles(main_channel_id: str, batch_size: int = DEFAULT_BATCH_SIZE, batch_delay: int = DEFAULT_BATCH_DELAY_SECONDS):
    """
    Fetches users from the specified main channel, generates their full psychological summary
    using Telethon and LLM, and updates the profile_summary in the database.

    Processes users in batches to avoid rate limiting and improve stability.
    """
    logger.info(f"Starting profile filling process for channel: {main_channel_id} with batch size {batch_size}")

    # 1. Initialize Database
    db_initialized = await setup_database()
    if not db_initialized:
        logger.critical("Database initialization failed. Cannot proceed.")
        return

    # 2. Initialize Telethon Client
    try:
        client = await get_client()
        await telegram_service.start_client()
    except Exception as e:
        logger.critical(f"Failed to start Telethon client: {e}. Cannot proceed.")
        await close_database()
        return

    # 3. Get users from the channel
    user_ids = []
    try:
        logger.info(f"Fetching participants from channel {main_channel_id}...")
        user_ids = await telegram_service.get_channel_users(main_channel_id)
        logger.info(f"Found {len(user_ids)} participants in channel {main_channel_id}.")
    except Exception as e:
        logger.error(f"Failed to get users from channel {main_channel_id}: {e}")
        # Decide whether to proceed without channel users or stop
        # For now, we stop if we can't get users from the main channel
        await close_database()
        # await telegram_service.client.disconnect() # Consider disconnecting client
        return

    if not user_ids:
        logger.warning(f"No users found in channel {main_channel_id}. Exiting.")
        await close_database()
        return

    # 4. Process users in batches
    total_users = len(user_ids)
    processed_count = 0
    failed_count = 0
    logger.info(f"Starting processing of {total_users} users in batches of {batch_size}...")

    created_count = 0
    updated_count = 0
    skipped_count = 0
    skipped_streams_count = 0
    skipped_gender_summary_count = 0
    for user_id in user_ids:
        logger.info(f"Processing user {user_id}...")
        async for session in get_db_session():
            if session is None:
                logger.error("Failed to get DB session for user. Skipping user.")
                failed_count += 1
                break

            try:
                # Получаем entity пользователя из Telegram один раз
                tg_user = None
                try:
                    tg_user = await telegram_service.client.get_entity(user_id)
                except Exception as e:
                    logger.warning(f"Не удалось получить entity пользователя из Telegram: {e}")
                    tg_user = None

                # Проверяем наличие пользователя и полей в базе
                user = await session.get(User, user_id)
                user_has_summary = user and user.profile_summary and user.profile_summary.strip()
                user_has_gender = user and user.gender and str(user.gender) not in ('', 'unknown', 'None')
                user_has_streams = user and user.streams and isinstance(user.streams, list) and len(user.streams) > 0

                # Нужно ли делать summary?
                need_summary = not user_has_summary
                # Нужно ли определять пол?
                need_gender = not user_has_gender

                summary = None
                gender = None
                streams = []

                if not need_summary and not need_gender and not user_has_streams:
                    logger.info(f"User {user_id} уже имеет все необходимые поля (summary, gender, streams), пропущен (ничего не обновлялось).")
                    processed_count += 1
                    skipped_count += 1
                    continue

                # Получаем summary, если нужно
                if need_summary:
                    # summary теперь строится по постам из канала обсуждений
                    max_llm_attempts = 3
                    for attempt in range(1, max_llm_attempts + 1):
                        try:
                            summary, _, streams = await telegram_service.get_full_psychological_summary(user_id, settings.discussion_channel_id, tg_user)
                            if streams:
                                logger.info(f"User {user_id} обнаружены потоки: {', '.join(streams)}")
                            break
                        except Exception as e:
                            logger.error(f"Попытка {attempt}/{max_llm_attempts} — Ошибка LLM для user {user_id}: {e}")
                            if attempt < max_llm_attempts:
                                import asyncio
                                await asyncio.sleep(5)
                            else:
                                summary = None
                    # Фильтрация отказных ответов LLM
                    refusal_phrases = [
                        "i'm sorry, i can't help",
                        "i'm sorry, i can't assist",
                        "i can't help with that",
                        "i can't assist with that",
                        "я не могу помочь",
                        "не могу помочь",
                        "не могу выполнить",
                        "не могу анализировать",
                        "отказ",
                        "извините, я не могу помочь с этой задачей"
                    ]
                    if not summary or not isinstance(summary, str) or any(phrase in summary.lower() for phrase in refusal_phrases):
                        logger.warning(f"LLM отказался генерировать summary для user {user_id} (summary='{summary}'). Summary не будет обновлен.")
                        summary = None
                        # Продолжаем процесс обновления других полей

                # Определяем пол, если нужно
                if need_gender:
                    from relove_bot.utils.gender import detect_gender
                    gender = await detect_gender(tg_user)



                # Обновляем профиль пользователя с учётом потоков
                before = await session.get(User, user_id)
                await update_user_profile_summary(session, user_id, summary, gender, streams)
                if streams:
                    logger.info(f"User {user_id} обновлены потоки: {', '.join(streams)}")
                after = await session.get(User, user_id)
                if before is None and after is not None:
                    created_count += 1
                    logger.info(f"User {user_id} был создан в базе данных.")
                elif before is not None and after is not None:
                    updated_count += 1
                    logger.info(f"User {user_id} был обновлён в базе данных.")
                else:
                    logger.warning(f"User {user_id} не был создан/обновлён! Проверьте логи.")
                processed_count += 1
                
                if summary and not any(phrase in summary.lower() for phrase in refusal_phrases):
                    # Получаем пользователя из базы для передачи имени/фамилии/логина
                    # Используем ранее полученный tg_user для определения пола
                    if tg_user:
                        first_name = getattr(tg_user, 'first_name', None)
                
                if summary and not any(phrase in summary.lower() for phrase in refusal_phrases):
                    # Получаем пользователя из базы для передачи имени/фамилии/логина
                    # Используем ранее полученный tg_user для определения пола
                    if tg_user:
                        first_name = getattr(tg_user, 'first_name', None)
            except Exception as e:
                logger.error(f"Ошибка при обработке пользователя {user_id}: {e}")
                failed_count += 1
                # Continue to the next user even if one fails
        # End of session block for the batch


    logger.info(f"Profile filling completed: {processed_count} processed, {failed_count} failed.")
    logger.info(f"Создано новых пользователей: {created_count}")
    logger.info(f"Обновлено пользователей: {updated_count}")
    logger.info(f"Пропущено (уже всё заполнено): {skipped_count}, из них с заполненными streams: {skipped_streams_count}, с отказом LLM/gender/summary: {skipped_gender_summary_count}")

    # 5. Clean up
    await close_database()
    # Consider disconnecting client if the script is meant to be short-lived
    # await telegram_service.client.disconnect()
    logger.info("Cleanup finished.")

# Старый fill_profiles оставляем для CLI-использования (можно вызвать select_users внутри него)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Fill/refresh profile summaries and gender for all users.")
    parser.add_argument('--only-female', action='store_true', help='Process only female users')
    args = parser.parse_args()
    asyncio.run(fill_all_profiles(settings.our_channel_id))
