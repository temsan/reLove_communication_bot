import asyncio
from relove_bot.db.session import SessionLocal
from relove_bot.db.models import User
from relove_bot.rag.pipeline import aggregate_profile_summary


from relove_bot.rag.llm import LLM
from relove_bot.services.telegram_service import client
import base64
from io import BytesIO
import logging

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db.database import setup_database, close_database, get_db_session
from ..services import telegram_service # Импортируем весь модуль

logger = logging.getLogger(__name__)

# --- Константы для батчинга ---
DEFAULT_BATCH_SIZE = 50
DEFAULT_BATCH_DELAY_SECONDS = 5

async def detect_gender(user_id: int = None, first_name: str = None, last_name: str = None, username: str = None) -> str:
    """
    Определяет пол пользователя по имени, фамилии, логину, фото (в порядке приоритета).
    Возвращает 'male', 'female' или 'unknown'.
    """
    llm = LLM()
    # 1. По имени
    if first_name and first_name.strip():
        prompt = (
            "Определи пол пользователя по имени. Ответь только одним словом: 'male', 'female' или 'unknown'.\n"
            f"Имя: {first_name}"
        )
        try:
            result = await llm.analyze_content(text=prompt, system_prompt="Определи пол по имени. Ответь 'male', 'female' или 'unknown' одним словом.", max_tokens=6)
            value = (result["summary"] or '').lower().strip()
            if value in {'female', 'жен', 'женский'} or 'female' in value or 'жен' in value:
                return 'female'
            if value in {'male', 'муж', 'мужской'} or 'male' in value or 'муж' in value:
                return 'male'
        except Exception as e:
            print(f"[detect_gender] Ошибка по имени: {e}")
    # 2. По фамилии
    if last_name and last_name.strip():
        prompt = (
            "Определи пол пользователя по фамилии. Ответь только одним словом: 'male', 'female' или 'unknown'.\n"
            f"Фамилия: {last_name}"
        )
        try:
            result = await llm.analyze_content(text=prompt, system_prompt="Определи пол по фамилии. Ответь 'male', 'female' или 'unknown' одним словом.", max_tokens=6)
            value = (result["summary"] or '').lower().strip()
            if value in {'female', 'жен', 'женский'} or 'female' in value or 'жен' in value:
                return 'female'
            if value in {'male', 'муж', 'мужской'} or 'male' in value or 'муж' in value:
                return 'male'
        except Exception as e:
            print(f"[detect_gender] Ошибка по фамилии: {e}")
    # 3. По логину
    if username and username.strip():
        prompt = (
            "Определи пол пользователя по логину (username). Ответь только одним словом: 'male', 'female' или 'unknown'.\n"
            f"Логин: {username}"
        )
        try:
            result = await llm.analyze_content(text=prompt, system_prompt="Определи пол по username. Ответь 'male', 'female' или 'unknown' одним словом.", max_tokens=6)
            value = (result["summary"] or '').lower().strip()
            if value in {'female', 'жен', 'женский'} or 'female' in value or 'жен' in value:
                return 'female'
            if value in {'male', 'муж', 'мужской'} or 'male' in value or 'муж' in value:
                return 'male'
        except Exception as e:
            print(f"[detect_gender] Ошибка по логину: {e}")
    # 4. По фото
    if user_id is not None:
        try:
            async for photo in client.iter_profile_photos(user_id, limit=1):
                bioio = BytesIO()
                await client.download_media(photo, file=bioio)
                bioio.seek(0)
                img_bytes = bioio.read()
                img_b64 = base64.b64encode(img_bytes).decode()
                prompt = (
                    "Определи пол пользователя по фото. Ответь только одним словом: 'male', 'female' или 'unknown'."
                )
                result = await llm.analyze_content(image_base64=img_b64, text=None, system_prompt=prompt, max_tokens=6)
                value = (result["summary"] or '').lower().strip()
                if value in {'female', 'жен', 'женский'} or 'female' in value or 'жен' in value:
                    return 'female'
                if value in {'male', 'муж', 'мужской'} or 'male' in value or 'муж' in value:
                    return 'male'
                break
        except Exception as e:
            print(f"[detect_gender] Ошибка по фото: {e}")
    return 'unknown'



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
            user_dict = {
                'id': user.id,
                'username': user.username,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'summary': summary,
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

async def update_user_profile_summary(session: AsyncSession, user_id: int, summary: str):
    """Обновляет или создаёт profile_summary для пользователя."""
    from relove_bot.db.models import User
    from relove_bot.services import telegram_service
    user = await session.get(User, user_id)
    if user:
        user.profile_summary = summary
        await session.commit()
        logger.info(f"Successfully updated profile_summary for user {user_id}")
    else:
        # Пытаемся получить данные пользователя из Telegram
        try:
            tg_user = await telegram_service.client.get_entity(user_id)
            username = getattr(tg_user, 'username', None)
            first_name = getattr(tg_user, 'first_name', None)
            last_name = getattr(tg_user, 'last_name', None)
        except Exception as e:
            logger.warning(f"Could not fetch Telegram user info for user {user_id}: {e}")
            username = None
            first_name = None
            last_name = None
        # Определяем пол пользователя по summary
        from relove_bot.utils.fill_profiles import detect_gender
        gender = await detect_gender(user_id=user_id, first_name=first_name, last_name=last_name, username=username)
        new_user = User(
            id=user_id,
            username=username,
            first_name=first_name,
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

    for i in range(0, total_users, batch_size):
        batch_user_ids = user_ids[i:i + batch_size]
        logger.info(f"Processing batch {i // batch_size + 1}/{(total_users + batch_size - 1) // batch_size} ({len(batch_user_ids)} users)...")

        async for session in get_db_session(): # Get a fresh session for each batch
            if session is None:
                logger.error("Failed to get DB session for batch. Skipping batch.")
                failed_count += len(batch_user_ids) # Mark all in batch as failed
                break # Exit inner loop (session getter)

            for user_id in batch_user_ids:
                logger.debug(f"Processing user {user_id}...")
                try:
                    # Generate the summary using the service
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

                    # Если есть и summary, и gender — пропускаем
                    if user_has_summary and user_has_gender:
                        logger.info(f"User {user_id} уже имеет summary и gender, пропускаем.")
                        processed_count += 1
                        continue

                    # Получаем данные для detect_gender
                    if tg_user:
                        first_name = getattr(tg_user, 'first_name', None)
                        last_name = getattr(tg_user, 'last_name', None)
                        username = getattr(tg_user, 'username', None)
                    else:
                        first_name = last_name = username = None

                    # Нужно ли делать summary?
                    need_summary = not user_has_summary
                    # Нужно ли определять пол?
                    need_gender = not user_has_gender

                    summary = None
                    gender = None

                    # 1. Делаем только то, что нужно
                    if need_summary:
                        summary = await telegram_service.get_full_psychological_summary(
                            user_id=user_id,
                            main_channel_id=main_channel_id,
                            tg_user=tg_user
                        )
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
                        if not summary or any(phrase in summary.lower() for phrase in refusal_phrases):
                            logger.warning(f"LLM отказался генерировать summary для user {user_id} (summary='{summary}'). Пропуск записи в БД.")
                            failed_count += 1
                            continue
                        await update_user_profile_summary(session, user_id, summary)
                        logger.info(f"Summary успешно обновлён для user {user_id}")
                    else:
                        summary = user.profile_summary if user else None

                    if need_gender:
                        gender = await detect_gender(user_id=user_id, first_name=first_name, last_name=last_name, username=username)
                        user = await session.get(User, user_id)
                        if user:
                            if not user.markers or not isinstance(user.markers, dict):
                                user.markers = {}
                            user.markers['gender'] = str(gender)
                            user.gender = gender
                            await session.commit()
                            logger.info(f"Gender успешно определён и записан для user {user_id}")
                    else:
                        gender = str(user.gender) if user else None

                    processed_count += 1
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
                    if summary and not any(phrase in summary.lower() for phrase in refusal_phrases):
                        # Получаем пользователя из базы для передачи имени/фамилии/логина
                        # Используем ранее полученный tg_user для определения пола
                        if tg_user:
                            first_name = getattr(tg_user, 'first_name', None)
                            last_name = getattr(tg_user, 'last_name', None)
                            username = getattr(tg_user, 'username', None)
                        else:
                            first_name = last_name = username = None
                        gender = await detect_gender(user_id=user_id, first_name=first_name, last_name=last_name, username=username)
                        await update_user_profile_summary(session, user_id, summary)
                        user = await session.get(User, user_id)
                        if user:
                            if gender is not None:
                                # markers['gender'] — строка, user.gender — Enum
                                if not user.markers or not isinstance(user.markers, dict):
                                    user.markers = {}
                                user.markers['gender'] = str(gender)
                                user.gender = gender
                                await session.commit()
                        processed_count += 1
                    else:
                        logger.warning(f"LLM отказался генерировать summary для user {user_id} (summary='{summary}'). Пропуск записи в БД.")
                        failed_count += 1

                    # Optional VERY short delay between users in a batch if needed
                    # await asyncio.sleep(0.1)

                except Exception as e:
                    logger.error(f"Failed to process user {user_id}: {e}", exc_info=True)
                    failed_count += 1
                # Continue to the next user even if one fails
        # End of session block for the batch

        # Delay between batches
        if i + batch_size < total_users:
             logger.info(f"Finished batch. Waiting for {batch_delay} seconds before next batch...")
             await asyncio.sleep(batch_delay)

    logger.info(f"Profile filling process finished. Total: {total_users}, Processed: {processed_count}, Failed: {failed_count}")

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
    asyncio.run(fill_profiles(only_female=args.only_female))
