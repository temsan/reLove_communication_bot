import asyncio
import logging
from typing import Optional
from tqdm.asyncio import tqdm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import sessionmaker

from relove_bot.db.models import User
from relove_bot.db.database import get_db_session, setup_database, get_engine
from relove_bot.services.telegram_service import get_channel_users, get_channel_participants_count, get_client, get_full_user, get_user_profile_summary, get_bot_client
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

from relove_bot.db.models import GenderEnum

async def update_user_profile_summary(session: AsyncSession, user_id: int, summary, gender: GenderEnum = None, streams: list = None, tg_user=None) -> str:
    """
    Обновляет или создает профиль пользователя с новым summary и gender.
    
    Args:
        session: Асинхронная сессия базы данных
        user_id: ID пользователя
        summary: Новый summary профиля (может быть строкой или кортежем)
        gender: Новый пол пользователя (объект GenderEnum, опционально)
        streams: Список интересов пользователя (опционально)
        tg_user: Объект пользователя из Telegram (опционально)
        
    Returns:
        'created' если создан новый профиль, 'updated' если обновлен существующий
    """
    try:
        # Обрабатываем случай, когда summary - это кортеж
        if isinstance(summary, tuple):
            # Берем первый не-None элемент или пустую строку
            summary = next((str(item) for item in summary if item is not None), '')
        else:
            # Преобразуем в строку, если это не None
            summary = str(summary) if summary is not None else ''
        
        # Обрезаем summary до разумной длины (например, 8 000 символов)
        # чтобы избежать проблем с ограничениями базы данных
        MAX_SUMMARY_LENGTH = 8000
        if len(summary) > MAX_SUMMARY_LENGTH:
            summary = summary[:MAX_SUMMARY_LENGTH]
            logger.warning(f"Слишком длинный summary для пользователя {user_id}, обрезано до {MAX_SUMMARY_LENGTH} символов")
        
        # Проверяем существование пользователя
        stmt = select(User).where(User.id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        
        if user:
            # Обновляем существующий профиль
            try:
                user.profile_summary = summary
                if gender:
                    user.gender = gender
                if streams is not None:
                    user.streams = streams
                
                # Добавляем отладочную информацию
                logger.debug(f"Обновление пользователя {user_id} с summary длиной {len(summary)} символов")
                
                # Разделяем коммит на несколько операций
                await session.flush()
                await session.commit()
                logger.debug(f"Профиль пользователя {user_id} успешно обновлен")
                return 'updated'
            except Exception as e:
                logger.error(f"Ошибка при обновлении профиля пользователя {user_id}: {e}", exc_info=True)
                await session.rollback()
                raise
        else:
            # Создаем новый профиль
            try:
                # Убедимся, что streams не None
                user_streams = streams if streams is not None else []
                
                # Получаем данные пользователя из Telegram, если они доступны
                username = ''
                first_name = ''
                last_name = ''
                
                if tg_user is not None:
                    username = getattr(tg_user, 'username', '')
                    first_name = getattr(tg_user, 'first_name', '')
                    last_name = getattr(tg_user, 'last_name', '')
                
                # Создаем пользователя с обязательными полями
                new_user = User(
                    id=user_id,
                    username=username or '',
                    first_name=first_name or '',
                    last_name=last_name or '',
                    profile_summary=summary,
                    gender=gender if gender else GenderEnum.unknown,
                    streams=user_streams,
                    is_active=True,
                    markers={}    # Инициализируем пустым словарем
                )
                
                # Добавляем отладочную информацию
                logger.debug(f"Создание нового пользователя {user_id} с summary длиной {len(summary)} символов")
                
                session.add(new_user)
                
                # Разделяем коммит на несколько операций
                await session.flush()
                await session.commit()
                
                logger.debug(f"Профиль пользователя {user_id} успешно создан")
                return 'created'
                
            except Exception as e:
                logger.error(f"Ошибка при создании профиля пользователя {user_id}: {e}", exc_info=True)
                await session.rollback()
                raise
            
    except Exception as e:
        logger.error(f"Критическая ошибка при обновлении профиля пользователя {user_id}: {e}", exc_info=True)
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

async def process_user(user: int, generator=None):
    """
    Обрабатывает профиль пользователя.
    
    Args:
        user: ID пользователя или объект User для обработки
        generator: Pipeline для генерации текста (опционально)
        
    Returns:
        tuple: (summary, gender, streams) или (None, None, None) в случае ошибки
    """
    global processed
    processed += 1
    user_id = user if isinstance(user, int) else getattr(user, 'id', 'unknown')
    logger.info(f"Обработка пользователя {user_id}...")
    
    try:
        # Если передан ID пользователя, получаем объект User
        if isinstance(user, int):
            logger.debug(f"Получение данных пользователя {user}...")
            user = await get_full_user(user)
        
        # Пропускаем, если пользователь не найден
        if not user:
            logger.error(f"Пользователь не найден: {user}")
            return None, None, None
            
        logger.debug(f"Данные пользователя {user_id} получены")
        
        # Получаем пол пользователя
        logger.debug(f"Определение пола пользователя {user_id}...")
        try:
            gender = await get_user_gender(user)
            logger.info(f"Определен пол пользователя {user_id}: {gender}")
        except Exception as gender_error:
            logger.error(f"Ошибка при определении пола пользователя {user_id}: {gender_error}", exc_info=True)
            gender = None
        
        # Получаем интересы
        logger.debug(f"Получение интересов пользователя {user_id}...")
        try:
            from relove_bot.config import settings
            streams = await get_user_streams(user.id, settings.our_channel_id)
            logger.info(f"Получены интересы пользователя {user_id}: {streams}")
        except Exception as streams_error:
            logger.error(f"Ошибка при получении интересов пользователя {user_id}: {streams_error}", exc_info=True)
            streams = []
        
        # Генерируем summary
        logger.debug(f"Генерация summary для пользователя {user_id}...")
        
        try:
            if generator:
                prompt = f"Generate profile summary for user {getattr(user, 'username', '')}: {getattr(user, 'first_name', '')} {getattr(user, 'last_name', '')}"
                logger.debug(f"Использование локального генератора для пользователя {user_id}")
                summary = generator(prompt)[0]['generated_text']
            else:
                logger.debug(f"Использование get_user_profile_summary для пользователя {user_id}")
                summary = await asyncio.wait_for(
                    get_user_profile_summary(user.id),
                    timeout=120  # Таймаут 2 минуты
                )
                if not summary:
                    logger.warning(f"Пустой summary для пользователя {user_id}")
                    return None, None, None, None
                
            logger.info(f"Успешно сгенерировано summary для пользователя {user_id}")
            return summary, gender, streams, user  # Возвращаем также объект пользователя
            
        except asyncio.TimeoutError:
            logger.warning(f"Таймаут при генерации summary для пользователя {user_id}")
            return None, None, None, None
            
        except Exception as summary_error:
            logger.error(f"Ошибка при генерации summary для пользователя {user_id}: {summary_error}", exc_info=True)
            return None, None, None, None
        
    except Exception as e:
        logger.error(f"Критическая ошибка при обработке пользователя {user_id}: {e}", exc_info=True)
        return None, None, None

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

async def fill_all_profiles(channel_id_or_username: str, generator=None, batch_size: int = 200, progress_callback=None):
    """
    Заполняет профили всех пользователей из канала с пагинацией и прогресс-баром.
    
    Args:
        channel_id_or_username: ID или username канала
        generator: Генератор для обработки пользователей (опционально)
        batch_size: размер пакета для получения участников (максимум 200)
        progress_callback: Функция обратного вызова для обновления прогресса
    """
    global created_count, updated_count, skipped_count, skipped_gender_summary_count, processed
    session = None
    client = None
    pbar = None
    
    try:
        # Инициализируем базу данных
        await setup_database()
        
        # Подключаемся к клиенту
        client = await get_bot_client()
        
        # Инициализируем сессию базы данных
        session = get_db_session()
        
        # Получаем общее количество участников
        total_count = await get_channel_participants_count(channel_id_or_username)
        
        # Обрабатываем пользователей по батчам
        batch = []
        async for user_id in get_channel_users(channel_id_or_username, batch_size):
            try:
                # Добавляем пользователя в текущий батч
                batch.append(user_id)
                
                # Если набрали полный батч, обрабатываем его
                if len(batch) >= batch_size:
                    await _process_batch(batch, session, generator, progress_callback)
                    batch = []
                    
                    # Делаем паузу между батчами
                    await asyncio.sleep(1)
                    
            except Exception as e:
                logger.error(f"Ошибка при обработке батча: {e}")
                if progress_callback:
                    progress_callback()
                continue
        
        # Обрабатываем оставшихся пользователей
        if batch:
            await _process_batch(batch, session, generator, progress_callback)
        
        return processed
            
    except Exception as e:
        logger.error(f"Ошибка при заполнении профилей: {e}")
        raise
        
    finally:
        # Закрываем соединения в обратном порядке
        try:
            if pbar:
                pbar.close()
                
            if session:
                await session.close()
                
            if client:
                await client.disconnect()
                
            await close_database()
        except Exception as e:
            logger.error(f"Ошибка при завершении работы: {e}")
            raise

async def _process_batch(batch, session, generator, progress_callback=None):
    """
    Обрабатывает батч пользователей.
    
    Args:
        batch: Список ID пользователей для обработки
        session: Сессия базы данных
        generator: Генератор для обработки пользователей (опционально)
        progress_callback: Функция обратного вызова для обновления прогресса
    """
    global created_count, updated_count, skipped_count, skipped_gender_summary_count, processed
    
    if not batch:
        logger.warning("Получен пустой батч для обработки")
        return
    
    for user_id in batch:
        try:
            # Получаем полную информацию о пользователе с таймаутом
            try:
                user_info = await asyncio.wait_for(
                    get_full_user(user_id),
                    timeout=60  # 60 секунд на получение данных пользователя
                )
                if not user_info:
                    skipped_count += 1
                    if progress_callback:
                        progress_callback()
                    continue
                    
            except asyncio.TimeoutError:
                skipped_count += 1
                if progress_callback:
                    progress_callback()
                continue
                
            except Exception as e:
                logger.error(f"Ошибка при получении информации о пользователе {user_id}: {e}")
                skipped_count += 1
                if progress_callback:
                    progress_callback()
                continue

            # Получаем summary, gender и streams
            try:
                result = await process_user(user_info, generator)
                
                if not result or len(result) != 4:
                    skipped_gender_summary_count += 1
                    if progress_callback:
                        progress_callback()
                    continue
                    
                summary, gender, streams, tg_user = result
                
                if not summary or not gender or streams is None:
                    skipped_gender_summary_count += 1
                    if progress_callback:
                        progress_callback()
                    continue

                # Обновляем профиль пользователя
                try:
                    # Проверяем, что у нас есть все необходимые данные
                    if not all([summary, gender]):
                        skipped_count += 1
                        if progress_callback:
                            progress_callback()
                        continue
                        
                    result = await update_user_profile_summary(
                        session=session,
                        user_id=user_info.id,
                        summary=summary,
                        gender=gender,
                        streams=streams,
                        tg_user=tg_user
                    )
                    
                    if result == 'created':
                        created_count += 1
                    elif result == 'updated':
                        updated_count += 1
                    else:
                        skipped_count += 1
                        
                except Exception as e:
                    logger.error(f"Ошибка при обновлении профиля пользователя {user_id}: {e}")
                    skipped_count += 1
                    if progress_callback:
                        progress_callback()
                    continue
                    
            except Exception as e:
                logger.error(f"Ошибка при обработке пользователя {user_id}: {e}")
                skipped_gender_summary_count += 1
                if progress_callback:
                    progress_callback()
                continue
                
            # Успешная обработка
            processed += 1
            if progress_callback:
                progress_callback()
            
        except Exception as e:
            logger.error(f"Непредвиденная ошибка при обработке пользователя {user_id}: {e}")
            skipped_count += 1
            if progress_callback:
                progress_callback()
            continue
