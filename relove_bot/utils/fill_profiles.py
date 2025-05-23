import asyncio
from typing import Optional, List, Tuple, Dict, Any
from telethon import TelegramClient
from telethon.tl.types import User as TelegramUser
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from tqdm import tqdm
import logging
import os
import sys
import time
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

from relove_bot.db.models import User
from relove_bot.db.database import get_db_session, setup_database, get_engine
from relove_bot.services.telegram_service import get_channel_users, get_channel_participants_count, get_client, get_full_user, get_user_profile_summary, get_bot_client
from relove_bot.utils.gender import detect_gender as get_user_gender
from relove_bot.utils.interests import get_user_streams
from relove_bot.utils.custom_logging import setup_logging

logger = logging.getLogger(__name__)

# Настройка логирования
setup_logging()

# Настраиваем уровень логирования для текущего модуля
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # Устанавливаем уровень INFO для отслеживания процесса

# Устанавливаем формат логов для лучшей читаемости
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[logging.StreamHandler(sys.stdout)]
)

# Отключаем все логи, кроме ошибок
logging.getLogger('telethon').setLevel(logging.CRITICAL)
logging.getLogger('httpx').setLevel(logging.CRITICAL)
logging.getLogger('sqlalchemy').setLevel(logging.CRITICAL)
logging.getLogger('aiosqlite').setLevel(logging.CRITICAL)
logging.getLogger('asyncio').setLevel(logging.CRITICAL)

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
    # Минимизируем логирование внешних библиотек
    logging.getLogger('httpx').setLevel(logging.CRITICAL)
    logging.getLogger('sqlalchemy').setLevel(logging.CRITICAL)
    logging.getLogger('aiosqlite').setLevel(logging.CRITICAL)
    logging.getLogger('asyncio').setLevel(logging.CRITICAL)
    return engine

# --- Константы для батчинга ---
DEFAULT_BATCH_SIZE = 200
DEFAULT_BATCH_DELAY_SECONDS = 5



async def select_users(gender: str = None, text_filter: str = None, user_id_list: list = None, rank_by: str = None, limit: int = 30):
    """
    Универсальный отбор пользователей по фильтрам:
    - gender: 'male', 'female', None
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
            # Обновляем существующий профиль, только если поля пустые
            try:
                updated = False
                
                # Обновляем summary только если он пустой
                if not user.profile_summary and summary:
                    user.profile_summary = summary
                    updated = True
                
                # Обновляем пол только если он не определен
                if gender and user.gender is None and gender is not None:
                    user.gender = gender
                    updated = True
                
                # Обновляем потоки только если они не заданы
                if streams is not None and not user.streams:
                    user.streams = streams
                    updated = True
                
                # Обновляем имя пользователя, если оно пустое и есть данные из Telegram
                if tg_user and not user.username:
                    if hasattr(tg_user, 'username') and tg_user.username:
                        user.username = tg_user.username
                        updated = True
                    if hasattr(tg_user, 'first_name') and tg_user.first_name and not user.first_name:
                        user.first_name = tg_user.first_name
                        updated = True
                    if hasattr(tg_user, 'last_name') and tg_user.last_name and not user.last_name:
                        user.last_name = tg_user.last_name
                        updated = True
                
                if updated:
                    # Добавляем отладочную информацию
                    logger.debug(f"Обновление пользователя {user_id} (заполнение пустых полей)")
                    
                    # Разделяем коммит на несколько операций
                    await session.flush()
                    await session.commit()
                    logger.debug(f"Профиль пользователя {user_id} успешно обновлен (заполнены пустые поля)")
                    return 'updated'
                else:
                    logger.debug(f"Пропуск пользователя {user_id} - все поля уже заполнены")
                    return 'skipped'
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
                    gender=gender,
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

async def process_user(user: int, generator=None, session: AsyncSession = None):
    """
    Обрабатывает профиль пользователя.
    
    Args:
        user: ID пользователя или объект User для обработки
        generator: Pipeline для генерации текста (опционально)
        session: Сессия базы данных (опционально)
        
    Returns:
        tuple: (summary, gender, streams, user) или (None, None, None, None) в случае ошибки
    """
    global processed
    processed += 1
    user_id = user if isinstance(user, int) else getattr(user, 'id', 'unknown')
    logger.info(f"Обработка пользователя {user_id}...")
    start_time = time.time()
    
    try:
        # Если передан ID пользователя, получаем объект User
        if isinstance(user, int):
            logger.debug(f"Получение данных пользователя {user}...")
            start_get_user = time.time()
            user = await get_full_user(user)
            logger.info(f"Получение данных пользователя {user} заняло {time.time() - start_get_user:.2f} секунд")
        
        # Пропускаем, если пользователь не найден
        if not user:
            logger.error(f"Пользователь не найден: {user}")
            return None, None, None, None
            
        logger.debug(f"Данные пользователя {user_id} получены")
        
        # Получаем пол пользователя
        logger.debug(f"Определение пола пользователя {user_id}...")
        start_gender = time.time()
        gender = await get_user_gender(user)
        logger.info(f"Определен пол пользователя {user_id}: {gender}")
        logger.info(f"Определение пола заняло {time.time() - start_gender:.2f} секунд")
        
        # Получаем интересы
        logger.debug(f"Получение интересов пользователя {user_id}...")
        start_streams = time.time()
        from relove_bot.config import settings
        streams = await get_user_streams(user.id, settings.our_channel_id)
        logger.info(f"Получены интересы пользователя {user_id}: {streams}")
        logger.info(f"Получение интересов заняло {time.time() - start_streams:.2f} секунд")
        
        # Генерируем summary
        logger.debug(f"Генерация summary для пользователя {user_id}...")
        start_summary = time.time()
        
        try:
            # Используем функцию get_user_profile_summary для получения полного профиля
            logger.info(f"Получение полного профиля пользователя {user_id}...")
            try:
                # Используем правильную сигнатуру функции
                summary, photo_bytes, user_streams = await asyncio.wait_for(
                    get_user_profile_summary(
                        user_id=user.id,
                        main_channel_id=settings.our_channel_id
                    ),
                    timeout=300  # Таймаут 5 минут
                )
                logger.info(f"Получение профиля заняло {time.time() - start_summary:.2f} секунд")
                
                if not summary:
                    logger.warning(f"Пустой summary для пользователя {user_id}")
                    return None, None, None, None
                    
                # Обновляем потоки, если они получены из get_user_profile_summary
                if user_streams:
                    streams = user_streams
                    logger.info(f"Получены потоки для пользователя {user_id}: {streams}")
                
                logger.info(f"Сгенерированный summary для пользователя {user_id}: {summary[:100]}...")
                
                # Обновляем фото пользователя, если оно есть и передан session
                if session is not None and photo_bytes is not None and isinstance(photo_bytes, bytes):
                    try:
                        # Получаем пользователя из базы данных
                        stmt = select(User).where(User.id == user_id)
                        result = await session.execute(stmt)
                        db_user = result.scalar_one_or_none()
                        
                        if db_user:
                            # Обновляем только если фото еще не установлено
                            if not db_user.photo_jpeg:
                                db_user.photo_jpeg = photo_bytes
                                await session.commit()
                                logger.info(f"Обновлено фото пользователя {user_id}")
                    except Exception as e:
                        logger.error(f"Ошибка при обновлении фото пользователя {user_id}: {e}")
                        logger.exception(e)
                        await session.rollback()
                
                return summary, gender, streams, user  # Возвращаем также объект пользователя
                
            except asyncio.TimeoutError:
                logger.warning(f"Таймаут при получении профиля пользователя {user_id}")
                logger.info(f"Таймаут произошел после {time.time() - start_summary:.2f} секунд")
                return None, None, None, None
            except Exception as e:
                logger.error(f"Ошибка при получении профиля пользователя {user_id}: {e}")
                logger.exception(e)
                return None, None, None, None
                
        except Exception as summary_error:
            logger.error(f"Ошибка при генерации summary для пользователя {user_id}: {summary_error}", exc_info=True)
            logger.exception(summary_error)
            return None, None, None, None
        
    except Exception as e:
        logger.error(f"Критическая ошибка при обработке пользователя {user_id}: {e}", exc_info=True)
        logger.exception(e)
        return None, None, None, None

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

async def fill_all_profiles(users: list = None, channel_id_or_username: str = None, 
                         generator=None, batch_size: int = 200, 
                         progress_callback=None, client=None):
    """
    Заполняет профили пользователей из списка или канала.
    
    Args:
        users: Список пользователей для обработки (если None, берет из канала)
        channel_id_or_username: Имя или ID канала (если не передан список пользователей)
        generator: Генератор для обработки текста (опционально)
        batch_size: Размер пакета для обработки
        progress_callback: Функция обратного вызова для отображения прогресса
        client: Telegram клиент
    """
    global created_count, updated_count, skipped_count, skipped_gender_summary_count, processed
    session = None
    tasks = [] # Инициализируем tasks здесь
    
    try:
        # Инициализация базы данных
        await setup_database()
        session = get_db_session()
        
        # Если передан список пользователей, используем его
        if users:
            user_list = users
            total_users = len(users)
            logger.critical(f"Обработка {total_users} пользователей из списка")
        # Иначе получаем пользователей из канала
        elif channel_id_or_username:
            if not client:
                client = await get_client()
                
            # Проверяем подключение к клиенту
            if not client.is_connected():
                logger.critical("КРИТИЧЕСКАЯ ОШИБКА: Клиент не подключен к Telegram")
                raise ConnectionError("Telegram client is not connected")
                
            # Проверяем авторизацию
            if not await client.is_user_authorized():
                logger.critical("КРИТИЧЕСКАЯ ОШИБКА: Клиент не авторизован")
                raise ValueError("Telegram client is not authorized")
                
            # Получаем пользователей из канала
            logger.critical(f"Получение пользователей из канала {channel_id_or_username}")
            user_list = []
            async for user in get_channel_users(channel_id_or_username):
                user_list.append(user)
                
            total_users = len(user_list)
            logger.critical(f"Получено {total_users} пользователей из канала")
        else:
            logger.critical("КРИТИЧЕСКАЯ ОШИБКА: Не указан ни список пользователей, ни канал")
            raise ValueError("Either users list or channel_id_or_username must be provided")
            return
            
        # Получаем все user_id с прогресс-баром
        user_ids = []
        with tqdm(total=total_users, desc="[1/3] Получение пользователей", position=0, leave=True, 
                 bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]') as pbar_get:
            try:
                logger.info("Начинаем получение списка пользователей")
                async for user_id in get_channel_users(channel_id_or_username, batch_size):
                    user_ids.append(user_id)
                    pbar_get.update(1)
                    if len(user_ids) % 100 == 0:
                        logger.info(f"Собрано {len(user_ids)} пользователей")
                        logger.info(f"Пример ID последнего пользователя: {user_id}")
            except Exception as e:
                logger.error(f"Ошибка при получении пользователей: {e}")
                logger.error(f"Тип ошибки: {type(e)}")
                logger.error(f"Подробности ошибки: {str(e)}")
                raise # Если нет пользователей, выходим
        if not user_ids:
            logger.warning("Не найдено пользователей для обработки")
            return processed
        
# Параллельная обработка LLM/summary
        async def process_llm(user_id, retries=3, delay=1):
            """
            Обрабатывает пользователя с повторами при ошибках API.
            
            Args:
                user_id: ID пользователя
                retries: Количество попыток
                delay: Задержка между попытками (в секундах)
            """
            try:
                logger.debug(f"Начинаем обработку пользователя {user_id}")
                result = await asyncio.wait_for(process_user(user_id, generator, session=session), timeout=300)
                logger.debug(f"Обработка пользователя {user_id} завершена")
                return user_id, result
            except asyncio.TimeoutError:
                logger.warning(f"Таймаут при обработке пользователя {user_id}")
                return user_id, (None, None, None, None)
            except asyncio.CancelledError:
                logger.warning(f"Задача обработки пользователя {user_id} была отменена")
                return user_id, (None, None, None, None)
            except Exception as e:
                if retries > 0:
                    error_msg = str(e).lower()
                    if any(limit_error in error_msg for limit_error in ['rate limit', 'too many requests']):
                        logger.warning(f"Превышение лимита API для пользователя {user_id}, ожидаем {delay} секунд")
                        await asyncio.sleep(delay)
                        return await process_llm(user_id, retries-1, delay*2)  # Увеличиваем задержку
                    else:
                        logger.error(f"Ошибка при обработке пользователя {user_id}: {e}")
                        logger.exception(e)
                        return user_id, (None, None, None, None)
                else:
                    logger.error(f"Ошибка при обработке пользователя {user_id} после всех попыток: {e}")
                    logger.exception(e)
                    return user_id, (None, None, None, None)
        
        llm_results = []
        with tqdm(total=len(user_ids), desc="[2/3] Обработка LLM", position=1, leave=True, 
                 bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]') as pbar_llm:
            # Создаем семафор для ограничения количества одновременных задач
            semaphore = asyncio.Semaphore(5)  # Уменьшаем до 5 задач одновременно
            
            async def process_with_semaphore(user_id):
                async with semaphore:
                    try:
                        # Увеличиваем задержку для первых пользователей (warm-up)
                        if processed < 5:  # Для первых 5 пользователей
                            await asyncio.sleep(5)  # Увеличенная задержка
                        else:
                            # Динамическая задержка в зависимости от количества обработанных пользователей
                            base_delay = 2
                            if processed > 100:
                                base_delay = 5  # Увеличиваем задержку после 100 пользователей
                            elif processed > 50:
                                base_delay = 3  # Увеличиваем задержку после 50 пользователей
                            await asyncio.sleep(base_delay)
                        
                        # Добавляем дополнительную задержку между запросами к API
                        if processed > 0:
                            await asyncio.sleep(10)  # Дополнительная задержка между пользователями
                        
                        result = await process_llm(user_id)
                        return result
                    except Exception as e:
                        logger.error(f"Ошибка при обработке пользователя {user_id}: {e}")
                        # Если ошибка связана с лимитами API, увеличиваем задержку
                        if 'Rate limit' in str(e):
                            logger.warning(f"Превышение лимита API для пользователя {user_id}, увеличиваем задержку")
                            await asyncio.sleep(60)  # Ждем минуту перед следующей попыткой
                        return user_id, (None, None, None, None)
            
            # Создаем список задач для асинхронного выполнения
            tasks = []
            for uid in user_ids:
                task = asyncio.create_task(process_with_semaphore(uid))
                tasks.append(task)
            logger.info(f"Запланировано обработка {len(tasks)} пользователей через LLM")
            
            try:
                # Ожидаем завершения всех задач с задержкой между группами
                results = []
                for i in range(0, len(tasks), 5):  # Обрабатываем по 5 задач за раз
                    group = tasks[i:i + 5]
                    logger.info(f"Обработка группы {i//5 + 1} из {len(tasks)//5 + 1}")
                    for task in group:
                        result = await task
                        user_id, result_data = result
                        if result_data and all(result_data):
                            results.append(result)
                            pbar_llm.update(1)
                            logger.info(f"Успешно обработан пользователь {user_id}")
                        else:
                            logger.warning(f"Пропущен пользователь {user_id} - пустые данные")
                    # Добавляем задержку между группами (2 секунды)
                    await asyncio.sleep(2)
                llm_results = results
            except asyncio.CancelledError:
                logger.warning("Процесс обработки LLM был прерван")
                raise
            finally:
                # Отменяем все незавершенные задачи
                for task in tasks:
                    if not task.done():
                        task.cancel()
                # Ждем завершения отмененных задач
                await asyncio.gather(*tasks, return_exceptions=True)
        
        # Если нет результатов LLM, выходим
        if not llm_results:
            logger.warning("Нет результатов для записи в БД")
            return processed
        
# Параллельная запись в БД
        async def write_db(user_id, result):
            if not session:
                logger.error(f"Сессия базы данных не инициализирована для пользователя {user_id}")
                return 'skipped'
            
            if not result or not isinstance(result, tuple) or len(result) != 4:
                logger.warning(f"Пропущен пользователь {user_id} - некорректные данные")
                return 'skipped_gender_summary'
            summary, gender, streams, tg_user = result
            if not summary or not gender or streams is None:
                logger.warning(f"Пропущен пользователь {user_id} - пустые данные")
                return 'skipped_gender_summary'
            try:
                if not all([summary, gender]):
                    logger.warning(f"Пропущен пользователь {user_id} - пустые поля")
                    return 'skipped'
                res = await update_user_profile_summary(
                    session=session,
                    user_id=user_id,
                    summary=summary,
                    gender=gender,
                    streams=streams,
                    tg_user=tg_user
                )
                logger.info(f"Пользователь {user_id} успешно записан в БД: {res}")
                return res
            except asyncio.CancelledError:
                logger.warning(f"Задача записи в БД для пользователя {user_id} была отменена")
                return 'skipped'
            except Exception as e:
                logger.error(f"Ошибка при обновлении профиля пользователя {user_id}: {e}")
                logger.exception(e)
                return 'skipped'
        
        with tqdm(total=len(llm_results), desc="[3/3] Запись в БД   ", position=2, leave=True, 
                 bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]') as pbar_db:
            tasks = [write_db(user_id, result) for user_id, result in llm_results]
            try:
                for coro in asyncio.as_completed(tasks):
                    res = await coro
                    if res == 'created':
                        created_count += 1
                        logger.info(f"Создан новый профиль для пользователя {user_id}")
                    elif res == 'updated':
                        updated_count += 1
                        logger.info(f"Обновлен профиль пользователя {user_id}")
                    elif res == 'skipped_gender_summary':
                        skipped_gender_summary_count += 1
                        logger.warning(f"Пропущен пользователь {user_id} - пустой summary")
                    else:
                        skipped_count += 1
                        logger.warning(f"Пропущен пользователь {user_id}")
                    pbar_db.update(1)
            except asyncio.CancelledError:
                logger.warning("Процесс записи в БД был прерван")
                raise
        
        logger.info(f"Операция завершена. Результаты:")
        logger.info(f"Создано профилей: {created_count}")
        logger.info(f"Обновлено профилей: {updated_count}")
        logger.info(f"Пропущено профилей: {skipped_count}")
        logger.info(f"Пропущено из-за пустого summary: {skipped_gender_summary_count}")
        return processed
    except Exception as e:
        logger.error(f"Ошибка при заполнении профилей: {e}", exc_info=True)
        raise
    finally:
        try:
            # Закрываем все соединения
            if session:
                await session.close()
            if client:
                await client.disconnect()
            await close_database()
            # Ждем завершения всех задач
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"Ошибка при завершении работы: {e}")
            # raise # Предотвращаем распространение ошибки, чтобы не влиять на код выхода, если основная работа выполнена
        
        logger.info(f"Операция завершена. Результаты:")
        logger.info(f"Создано профилей: {created_count}")
        logger.info(f"Обновлено профилей: {updated_count}")
        logger.info(f"Пропущено профилей: {skipped_count}")
        logger.info(f"Пропущено из-за пустого summary: {skipped_gender_summary_count}")
        return processed


