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
from telethon.errors import FloodWaitError
from sqlalchemy.orm import Session
import traceback

# Загружаем переменные окружения
load_dotenv()

from relove_bot.db.models import User, GenderEnum
from relove_bot.db.database import get_db_session, setup_database, get_engine
from relove_bot.services.telegram_service import get_channel_users, get_channel_participants_count, get_client, get_full_user, get_user_profile_summary, get_bot_client, get_personal_channel_posts
from relove_bot.utils.gender import detect_gender as get_user_gender
from relove_bot.utils.interests import get_user_streams
from relove_bot.utils.custom_logging import setup_logging
from relove_bot.utils.logger import get_logger
from relove_bot.handlers.common import get_or_create_user
from relove_bot.db.session import SessionLocal

logger = get_logger(__name__)

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
        # Валидация входных данных
        if not user_id or not isinstance(user_id, int):
            logger.error(f"Некорректный ID пользователя: {user_id}")
            return 'skipped'
            
        # Обрабатываем случай, когда summary - это кортеж
        if isinstance(summary, tuple):
            # Берем первый не-None элемент или пустую строку
            summary = next((str(item) for item in summary if item is not None), '')
        else:
            # Преобразуем в строку, если это не None
            summary = str(summary) if summary is not None else ''
        
        # Проверяем summary на минимальную длину
        if len(summary.strip()) < 10:
            logger.warning(f"Слишком короткий summary для пользователя {user_id}: {len(summary)} символов")
            return 'skipped'
        
        # Обрезаем summary до разумной длины
        MAX_SUMMARY_LENGTH = 8000
        if len(summary) > MAX_SUMMARY_LENGTH:
            summary = summary[:MAX_SUMMARY_LENGTH]
            logger.warning(f"Слишком длинный summary для пользователя {user_id}, обрезано до {MAX_SUMMARY_LENGTH} символов")
        
        # Проверяем корректность пола
        if gender and gender not in [GenderEnum.male, GenderEnum.female, GenderEnum.unknown]:
            logger.warning(f"Некорректный пол для пользователя {user_id}: {gender}")
            gender = GenderEnum.unknown
        
        # Проверяем корректность потоков
        if streams is not None and not isinstance(streams, list):
            logger.warning(f"Некорректные потоки для пользователя {user_id}: {streams}")
            streams = []
        
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
                    await session.commit()
                    logger.info(f"Обновлен профиль пользователя {user_id}")
                    return 'updated'
                else:
                    logger.info(f"Профиль пользователя {user_id} не требует обновления")
                    return 'skipped'
                    
            except Exception as e:
                logger.error(f"Ошибка при обновлении профиля пользователя {user_id}: {e}")
                await session.rollback()
                return 'skipped'
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
                
                # Проверяем наличие обязательных полей
                if not (username or first_name):
                    logger.warning(f"Отсутствуют обязательные поля для пользователя {user_id}")
                    return 'skipped'
                
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
                logger.error(f"Ошибка при создании профиля пользователя {user_id}: {e}")
                await session.rollback()
                return 'skipped'
                
    except Exception as e:
        logger.error(f"Критическая ошибка при обновлении профиля пользователя {user_id}: {e}")
        return 'skipped'

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

async def get_users_from_db(session: AsyncSession) -> List[int]:
    """Получает список ID пользователей из базы данных асинхронно."""
    stmt = select(User.id)
    result = await session.execute(stmt)
    return [row[0] for row in result.all()]

async def process_user(user_id: int, client, session: AsyncSession) -> Optional[User]:
    """
    Обрабатывает одного пользователя.
    
    Args:
        user_id: ID пользователя
        client: Telegram клиент
        session: Сессия базы данных
        
    Returns:
        Optional[User]: Объект пользователя или None в случае ошибки
    """
    try:
        # Проверяем, что user_id является целым числом
        if not isinstance(user_id, int):
            logger.error(f"Некорректный ID пользователя: {user_id}")
            return None
            
        # Создаем новую сессию для каждого пользователя
        async with SessionLocal() as new_session:
            # Получаем информацию о пользователе
            user_info = await get_full_user(user_id)
            if not user_info:
                logger.error(f"Не удалось получить информацию о пользователе {user_id}")
                return None
                
            # Создаем или обновляем пользователя
            user = await get_or_create_user(new_session, user_info)
            return user
    except Exception as e:
        logger.error(f"Ошибка при обработке пользователя {user_id}: {e}")
        return None

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
                         progress_callback=None, client=None, session=None):
    """
    Заполняет профили пользователей из списка или канала.
    
    Args:
        users: Список пользователей для обработки (если None, берет из канала)
        channel_id_or_username: Имя или ID канала (если не передан список пользователей)
        generator: Генератор для обработки текста (опционально)
        batch_size: Размер пакета для обработки
        progress_callback: Функция обратного вызова для отображения прогресса (вызывается после обработки каждого пользователя)
        client: Telegram клиент
        session: Сессия базы данных
    """
    global created_count, updated_count, skipped_count, skipped_gender_summary_count, processed
    tasks = []
    
    try:
        # Если передан список пользователей, используем его
        if users:
            user_list = users
            total_users = len(users)
            logger.critical(f"Обработка {total_users} пользователей из списка")
            logger.info(f"Тип первого элемента: {type(users[0]) if users else 'список пуст'}")
            logger.info(f"Пример ID пользователей: {[str(u) for u in users[:3]]}")
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
            
        # Используем уже полученный список пользователей
        user_ids = user_list
        total_users = len(user_ids)
        logger.info(f"Начинаем обработку {total_users} пользователей")
        logger.info(f"Тип первого ID: {type(user_ids[0]) if user_ids else 'список пуст'}")
        logger.info(f"Пример ID: {user_ids[:3] if user_ids else 'список пуст'}")
        
        if not user_ids:
            logger.warning("Не найдено пользователей для обработки")
            return processed
            
        # Инициализируем прогресс-бар, если передан колбэк
        if progress_callback:
            progress_callback(0, total_users, "Инициализация...")
            
        # Проверяем сессию базы данных
        if not session:
            logger.error("Не передана сессия базы данных")
            return processed
            
        logger.info(f"Тип сессии БД: {type(session).__name__}")
        logger.info(f"Активное подключение: {session.bind.engine.pool.status() if hasattr(session, 'bind') else 'Нет подключения'}")
        
        # Обрабатываем пользователей порциями
        for i in range(0, len(user_ids), batch_size):
            batch = user_ids[i:i + batch_size]
            logger.critical(f"Обработка Пачка {i//batch_size + 1} ({len(batch)} пользователей)...")
            
            # Создаем задачи для обработки пользователей
            tasks = []
            for user_id in batch:
                task = asyncio.create_task(process_user(user_id, client, session))
                tasks.append((user_id, task))
            
            # Ждем завершения всех задач
            results = []
            for user_id, task in tasks:
                try:
                    result = await task
                    if result and isinstance(result, User):
                        results.append((user_id, result))
                except Exception as e:
                    logger.error(f"Ошибка при обработке пользователя {user_id}: {e}")
                    continue
            
            # Записываем результаты в БД
            if results:
                for user_id, result in results:
                    try:
                        if result:
                            res = await update_user_profile_summary(
                                session=session,
                                user_id=user_id,
                                summary=result.profile_summary,
                                gender=result.gender,
                                streams=result.streams,
                                tg_user=result
                            )
                            if res == 'created':
                                created_count += 1
                            elif res == 'updated':
                                updated_count += 1
                            else:
                                skipped_count += 1
                    except Exception as e:
                        logger.error(f"Ошибка при записи пользователя {user_id} в БД: {e}")
                        skipped_count += 1
                        continue
                
                # Коммитим изменения после каждой пачки
                try:
                    await session.commit()
                except Exception as e:
                    logger.error(f"Ошибка при коммите изменений: {e}")
                    await session.rollback()
            
            # Обновляем прогресс
            if progress_callback:
                progress_callback(min(i + batch_size, total_users), total_users, f"Обработано {min(i + batch_size, total_users)} из {total_users}")
            
            # Добавляем задержку между пачками
            await asyncio.sleep(1)
        
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
            if client:
                await client.disconnect()
            # Ждем завершения всех задач
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"Ошибка при завершении работы: {e}")
        
        logger.info(f"Операция завершена. Результаты:")
        logger.info(f"Создано профилей: {created_count}")
        logger.info(f"Обновлено профилей: {updated_count}")
        logger.info(f"Пропущено профилей: {skipped_count}")
        logger.info(f"Пропущено из-за пустого summary: {skipped_gender_summary_count}")
        return processed

async def main():
    """Основная функция скрипта."""
    try:
        # Инициализация клиента
        client = await get_client()
        if not client.is_connected():
            await client.start()
            
        # Инициализация сессии
        session = Session()
        
        # Получаем список пользователей
        users = await get_users_from_db(session)
        total_users = len(users)
        
        # Создаем прогресс-бар
        with tqdm(total=total_users, desc="Сбор пользователей", unit="польз.") as pbar:
            for user_id in users:
                try:
                    profile = await process_user(user_id, client, session)
                    if profile:
                        pbar.update(1)
                except Exception as e:
                    logger.error(f"Ошибка при обработке пользователя {user_id}: {e}")
                    continue
                    
        logger.info("Скрипт заполнения профилей успешно завершил работу.")
        
    except Exception as e:
        logger.error(f"Ошибка при выполнении скрипта: {e}")
        logger.error(traceback.format_exc())
    finally:
        if 'client' in locals() and client.is_connected():
            await client.disconnect()
        if 'session' in locals():
            session.close()
            
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Скрипт прерван пользователем")
    except Exception as e:
        logger.error(f"Ошибка при завершении работы: {e}")
        logger.error(traceback.format_exc())
    finally:
        logger.info("Завершение работы скрипта fill_profiles.")


