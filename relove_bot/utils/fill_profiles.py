import asyncio
import logging
from typing import Optional
from tqdm.asyncio import tqdm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import sessionmaker

from relove_bot.db.models import User
from relove_bot.db.database import get_db_session, setup_database, get_engine
from relove_bot.services.telegram_service import get_channel_users, get_channel_participants_count, get_client, get_full_user, get_user_gender, get_user_profile_summary, get_bot_client
from relove_bot.utils.gender import detect_gender as get_user_gender
from relove_bot.utils.interests import get_user_streams
from relove_bot.utils.custom_logging import setup_logging

logger = logging.getLogger(__name__)

# Настройка логирования
setup_logging()

# Глобальные счетчики
created_count = 0
updated_count = 0
skipped_count = 0
skipped_gender_summary_count = 0
processed = 0

# --- Новая асинхронная джоба для инициализации базы данных ---
async def initialize_database():
    """Инициализирует базу данных."""
    await setup_database()
    engine = get_engine()
    logging.getLogger('httpx').setLevel(logging.ERROR)
    logging.getLogger('sqlalchemy').setLevel(logging.ERROR)
    return engine

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
    try:
        # Инициализируем базу данных
        await setup_database()
        
        # Инициализируем сессию базы данных
        session = get_db_session()
        
        # Формируем базовый запрос
        query = select(User)
        
        # Применяем фильтры
        if gender:
            query = query.where(User.gender == gender)
        if text_filter:
            query = query.where(User.profile_summary.ilike(f'%{text_filter}%'))
        if user_id_list:
            query = query.where(User.id.in_(user_id_list))
        
        # Применяем сортировку
        if rank_by:
            if rank_by == 'context':
                query = query.order_by(User.context.desc())
            else:
                query = query.order_by(getattr(User, rank_by).desc())
        
        # Применяем лимит
        query = query.limit(limit)
        
        # Выполняем запрос
        result = await session.execute(query)
        users = result.scalars().all()
        
        # Формируем результат
        result_list = []
        for user in users:
            result_list.append({
                'id': user.id,
                'username': user.username,
                'summary': user.profile_summary,
                'gender': user.gender,
                'context': user.context
            })
        
        return result_list
    except Exception as e:
        logger.error(f"Ошибка при выполнении запроса: {e}")
        raise

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
        # Проверяем существование пользователя
        stmt = select(User).where(User.id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        
        if user:
            # Обновляем существующий профиль
            user.profile_summary = summary
            if gender:
                user.gender = gender
            if streams:
                user.interests = streams
            await session.commit()
        else:
            # Создаем новый профиль
            new_user = User(
                id=user_id,
                profile_summary=summary,
                gender=gender if gender else 'unknown',
                interests=streams if streams else []
            )
            session.add(new_user)
            await session.commit()
    except Exception as e:
        logger.error(f"Ошибка при обновлении профиля пользователя {user_id}: {e}")
        await session.rollback()
        raise

async def get_user_photo_jpeg(user_id: int) -> Optional[bytes]:
    """
    Получает фото пользователя в формате JPEG.
    
    Args:
        user_id: ID пользователя
    
    Returns:
        Байты JPEG-изображения или None, если фото не найдено
    """
    try:
        client = await get_bot_client()
        
        # Скачиваем фото напрямую
        photo = await client.download_profile_photo(user_id, bytes)
        
        return photo
    except Exception as e:
        logger.error(f"Ошибка при получении фото пользователя {user_id}: {e}")
        return None

async def process_user(user_id: int, generator=None):
    """
    Обрабатывает профиль пользователя.
    
    Args:
        user_id (int): ID пользователя для обработки
        generator: Pipeline для генерации текста (опционально)
    """
    global processed
    processed += 1
    
    try:
        # Получаем информацию о пользователе
        full_user = await get_full_user(user_id)
        user = full_user.user
        
        # Получаем пол пользователя
        gender = await get_user_gender(user)
        
        # Получаем интересы
        streams = await get_user_streams(user)
        
        # Генерируем summary с помощью локальной модели
        if generator:
            prompt = f"Generate profile summary for user {user.username}: {user.first_name} {user.last_name if user.last_name else ''}"
            summary = generator(prompt)[0]['generated_text']
        else:
            summary = await get_user_profile_summary(user)
        
        # Обновляем профиль
        async with get_db_session() as session:
            await update_user_profile_summary(
                session,
                user_id,
                summary,
                gender,
                streams
            )
            await session.commit()
            
            global updated_count
            updated_count += 1
            logger.info(f"Updated profile for user {user_id}")
            
        # Проверяем и обновляем базовый профиль
        async with get_db_session() as session:
            # Получаем пользователя из базы данных
            stmt = select(User).where(User.id == user_id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()
            
            if user:
                # Обновляем существующий профиль
                user.profile_summary = base_profile["profile_summary"]
                await session.commit()
    except Exception as e:
        logger.error(f"Error processing user {user_id}: {str(e)}")
        skipped_count += 1

async def close_database():
    """
    Закрывает соединение с базой данных.
    """
    try:
        engine = get_engine()
        if engine:
            await engine.dispose()
    except Exception as e:
        logger.error(f"Ошибка при закрытии соединения с базой данных: {e}")

async def fill_all_profiles(channel_id_or_username: str, generator=None, batch_size: int = 200):
    """
    Заполняет профили всех пользователей из канала.
    
    Args:
        channel_id_or_username: ID или username канала
        batch_size: размер пакета для получения участников (максимум 200)
    """
    global created_count, updated_count, skipped_count, skipped_gender_summary_count, processed
    session = None
    client = None
    
    try:
        # Инициализируем базу данных
        await setup_database()
        
        # Подключаемся к клиенту
        client = await get_bot_client()
        logger.info("Подключено к Telegram клиенту")
        
        # Инициализируем сессию базы данных
        session = get_db_session()
        logger.info("Инициализирована сессия базы данных")
        
        # Получаем общее количество участников
        total_count = await get_channel_participants_count(channel_id_or_username)
        logger.info(f"Всего участников в канале: {total_count}")
        
        # Обрабатываем пользователей по батчам
        async for user_id in get_channel_users(channel_id_or_username, batch_size):
            try:
                # Получаем полную информацию о пользователе
                user_info = await get_user_info(user_id)
                if not user_info:
                    skipped_count += 1
                    continue

                # Получаем summary и gender
                summary, gender = await process_user(user_id, generator)
                if not summary or not gender:
                    skipped_gender_summary_count += 1
                    continue

                # Обновляем или создаем профиль пользователя
                await update_user_profile_summary(
                    session,
                    user_id,
                    summary,
                    gender,
                    get_user_streams(user_id)
                )
                
                processed += 1
                
                # Делаем паузу между пользователями
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Ошибка при обработке пользователя {user_id}: {e}")
                continue
                
        return processed

    except Exception as e:
        logger.error(f"Ошибка при заполнении профилей: {e}")
        raise
        
    finally:
        # Закрываем соединения в обратном порядке
        if session:
            await session.close()
        if client:
            await client.disconnect()
        await close_database()
        logger.info("Очистка завершена.")
