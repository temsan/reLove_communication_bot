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
                        telegram_service = TelegramService()
                        psycho = await telegram_service.get_full_psychological_summary(user.id)
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
    """
    Обновляет или создает профиль пользователя с новым summary и gender.
    
    Args:
        session: Асинхронная сессия базы данных
        user_id: ID пользователя
        summary: Новый summary профиля
        gender: Новый пол пользователя (опционально)
        streams: Список интересов пользователя (опционально)
    """
    try:
        # Получаем клиента
        client = await get_client()
        
        # Проверяем, существует ли пользователь
        user = await session.get(User, user_id)
        if not user:
            # Если пользователя нет, создаем нового
            user = User(id=user_id)
            session.add(user)
            await session.commit()
            await session.refresh(user)
        
        # Получаем данные пользователя из Telegram
        entity = await client.get_entity(user_id)
        username = getattr(entity, 'username', None)
        first_name = getattr(entity, 'first_name', None)
        last_name = getattr(entity, 'last_name', None)
        
        # Обновляем поля
        user.profile_summary = summary
        if gender:
            user.gender = gender
        if streams:
            user.interests = streams
        if username:
            user.username = username
        if first_name:
            user.first_name = first_name
        if last_name:
            user.last_name = last_name
        
        await session.commit()
        logger.info(f"Successfully updated profile_summary and gender for user {user_id}")
    except Exception as e:
        logger.error(f"Failed to update user profile for user {user_id}: {e}")
        raise

async def fill_all_profiles(main_channel_id: str):
    """
    Fetches users from the specified main channel, generates their full psychological summary
    using Telethon and LLM, and updates the profile_summary in the database.
    """
    logger.info(f"Starting profile filling process for channel: {main_channel_id}")

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

    user_ids = []
    try:
        logger.info(f"Fetching participants from channel {main_channel_id}...")
        user_ids = await telegram_service.get_channel_users(main_channel_id, batch_size=200)
        logger.info(f"Found {len(user_ids)} participants in channel {main_channel_id}.")
    except Exception as e:
        logger.error(f"Failed to get users from channel {main_channel_id}: {e}")
        return

    processed = 0
    created_count = 0
    updated_count = 0
    skipped_count = 0
    skipped_gender_summary_count = 0

    async with get_db_session() as session:
        for user_id in user_ids:
            try:
                # Получаем пользователя из базы
                user = await session.get(User, user_id)
                if not user:
                    logger.info(f"User {user_id} не найден в базе, создаём новый профиль")
                    user = User(id=user_id)
                    session.add(user)
                    await session.commit()
                    await session.refresh(user)

                # Проверяем наличие необходимых полей
                user_has_summary = user.profile_summary and user.profile_summary.strip()
                user_has_gender = user.gender and str(user.gender) not in ('', 'unknown', 'None')
                user_has_streams = user.interests and isinstance(user.interests, list) and len(user.interests) > 0

                # Нужно ли обновлять профиль?
                need_update = not (user_has_summary and user_has_gender and user_has_streams)

                if not need_update:
                    logger.info(f"User {user_id} уже имеет все необходимые поля, пропущен")
                    skipped_count += 1
                    continue

                # Получаем данные из Telegram
                try:
                    entity = await client.get_entity(user_id)
                    username = getattr(entity, 'username', None)
                    first_name = getattr(entity, 'first_name', None)
                    last_name = getattr(entity, 'last_name', None)
                except Exception as e:
                    logger.warning(f"Не удалось получить данные пользователя из Telegram: {e}")
                    username = None
                    first_name = None
                    last_name = None

                # Генерируем summary если нужно
                if not user_has_summary:
                    try:
                        summary = await telegram_service.get_full_psychological_summary(user_id, settings.discussion_channel_id)
                        if summary:
                            logger.info(f"Сгенерирован summary для user {user_id}")
                        else:
                            logger.warning(f"Не удалось сгенерировать summary для user {user_id}")
                            skipped_gender_summary_count += 1
                    except Exception as e:
                        logger.error(f"Ошибка при генерации summary для user {user_id}: {e}")
                        summary = None
                        skipped_gender_summary_count += 1

                # Определяем пол если нужно
                if not user_has_gender:
                    try:
                        gender = await detect_gender(user_id)
                        if not gender:
                            logger.warning(f"Не удалось определить пол для user {user_id}")
                            skipped_gender_summary_count += 1
                    except Exception as e:
                        logger.error(f"Ошибка при определении пола для user {user_id}: {e}")
                        gender = None
                        skipped_gender_summary_count += 1

                # Обновляем профиль
                try:
                    await update_user_profile_summary(session, user_id, summary, gender)
                    updated_count += 1
                    logger.info(f"Обновлен профиль для user {user_id}")
                except Exception as e:
                    logger.error(f"Ошибка при обновлении профиля для user {user_id}: {e}")

                processed += 1
                logger.info(f"Processed {processed}/{len(user_ids)} users")

            except Exception as e:
                logger.error(f"Ошибка при обработке пользователя {user_id}: {e}")
                continue

    logger.info(f"Profile filling completed: {processed} processed.")
    logger.info(f"Создано новых пользователей: {created_count}")
    logger.info(f"Обновлено пользователей: {updated_count}")
    logger.info(f"Пропущено пользователей: {skipped_count}")
    logger.info(f"Пропущено пользователей из-за отсутствия gender/summary: {skipped_gender_summary_count}")
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
