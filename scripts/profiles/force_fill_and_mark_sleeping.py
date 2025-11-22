#!/usr/bin/env python3
"""
Скрипт для извлечения user_id из экспортов Telegram и работы с профилями пользователей.
Использует Telethon, SQLAlchemy и PIL для обработки фото.
"""

import asyncio
import io
import json
import logging
import os
import sys
from typing import Optional, Set

from bs4 import BeautifulSoup
from dotenv import load_dotenv
from PIL import Image
from tqdm import tqdm

# Добавляем корень проекта в PYTHONPATH для корректного импорта
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from relove_bot.config import settings, reload_settings
from relove_bot.db.models import User
from relove_bot.db.session import SessionLocal
from relove_bot.services.telegram_service import get_client
from relove_bot.utils.custom_logging import setup_logging
from relove_bot.utils.fill_profiles import fill_all_profiles
from sqlalchemy import select
from telethon import TelegramClient
from telethon.errors.rpcerrorlist import FloodWaitError, PeerIdInvalidError
from telethon.tl.functions.photos import GetUserPhotosRequest

async def safe_get_entity(identifier, max_retries=3):
    client = await get_client()
    for _ in range(max_retries):
        try:
            logger.debug(f'Attempting to get entity for identifier: {identifier}')
        return await client.get_entity(int(identifier))
        except FloodWaitError as e:
            logger.warning(f'FloodWaitError: ждем {e.seconds} секунд для {identifier}')
            # await asyncio.sleep(e.seconds)
        except PeerIdInvalidError:
            logger.warning(f'PeerIdInvalidError: не удалось найти сущность для {identifier}')
            return None
        except Exception as e:
            logger.warning(f'Ошибка получения entity для {identifier}: {e}')
            return None
    return None

load_dotenv(override=True)
reload_settings()
setup_logging()
logger = logging.getLogger(__name__)

# Используем путь из переменной окружения TELEGRAM_EXPORT_PATH
EXPORT_DIR = os.getenv('TELEGRAM_EXPORT_PATH')
logger.info(f"Используем путь к экспорту Telegram: {EXPORT_DIR}")

BATCH_SIZE = 10  # Количество пользователей для обработки в одном пакете
API_DELAY = 1    # Задержка между запросами к API в секундах

result_json = os.path.join(EXPORT_DIR, 'result.json')
messages_html = os.path.join(EXPORT_DIR, 'messages.html')

def extract_user_ids() -> Set[int]:
    """Извлечение ID пользователей из экспортированных файлов Telegram."""
    user_ids: Set[int] = set()
    global user_id_to_username
    user_id_to_username = {}
    
    # Проверка существования директории
    if not os.path.exists(EXPORT_DIR):
        logger.error(f"Директория экспорта не существует: {EXPORT_DIR}")
        return user_ids
        
    if not os.path.exists(result_json) and not os.path.exists(messages_html):
        logger.error(f"В директории {EXPORT_DIR} не найдено ни result.json, ни messages.html! Проверьте путь и экспорт Telegram.")
        raise FileNotFoundError(f"Нет файлов result.json и messages.html в {EXPORT_DIR}")
        
    # Извлечение из result.json (приоритетно)
    if os.path.exists(result_json):
        try:
            with open(result_json, encoding='utf-8') as f:
                data = json.load(f)
                for msg in data.get('messages', []):
                    uid = msg.get('from_id') or msg.get('actor_id')
                    username = msg.get('from', None)
                    # from иногда username (начинается с @), иногда просто имя
                    if isinstance(uid, int):
                        user_ids.add(uid)
                        if username and isinstance(username, str) and username.startswith('@'):
                            user_id_to_username[uid] = username
                    elif isinstance(uid, str):
                        import re
                        match = re.match(r'^(user|channel)(\d+)$', uid)
                        if match:
                            user_ids.add(int(match.group(2)))
                    elif isinstance(uid, dict) and uid.get('user_id'):
                        user_ids.add(uid['user_id'])
            logger.info(f'User IDs из result.json: {len(user_ids)}')
        except Exception as e:
            logger.error(f"Ошибка при чтении result.json: {e}")
    # Если не нашли в result.json, пробуем messages.html
    if not user_ids and os.path.exists(messages_html):
        try:
            with open(messages_html, encoding='utf-8') as f:
                soup = BeautifulSoup(f, 'html.parser')
                for msg in soup.find_all(class_='message'):
                    user_id = msg.get('data-from-id')
                    if user_id:
                        user_ids.add(int(user_id))
            logger.info(f'User IDs из messages.html: {len(user_ids)}')
            if len(user_ids) == 0:
                with open(messages_html, encoding='utf-8') as f2:
                    lines = [next(f2) for _ in range(10)]
                    logger.warning(f"Первые строки messages.html: {''.join(lines)}")
        except Exception as e:
            logger.error(f"Ошибка при чтении messages.html: {e}")
    if not user_ids:
        logger.error('user_id не извлечены ни из result.json, ни из messages.html! Проверьте структуру экспортов Telegram.')
    return user_ids

async def fetch_user_photo(user_id: int) -> Optional[bytes]:
    """
    Получение фотографии профиля пользователя с обработкой ошибок и задержкой.
    Args:
        user_id: ID пользователя
    Returns:
        bytes фотографии в формате JPEG или None если фото недоступно
    """
    errors_log = os.path.join(EXPORT_DIR, 'errors_skipped_user_ids.txt')
    client = await get_client()
    try:
        # Получаем entity пользователя
        user = await safe_get_entity(client, user_id)
        if not user:
            logger.warning(f"Не удалось получить entity пользователя {user_id}")
            return None

        # Получаем фото профиля
        photos = await client(GetUserPhotosRequest(
            user_id=user_id,
            offset=0,
            max_id=0,
            limit=1
        ))
        if not photos.photos:
            logger.debug(f"Пользователь {user_id} не имеет фотографии профиля")
            return None
        file = await client.download_media(photos.photos[0], file=bytes)
        if not file:
            logger.warning(f"Не удалось загрузить фото пользователя {user_id}")
            return None
        img = Image.open(io.BytesIO(file))
        with io.BytesIO() as output:
            if img.width > 800 or img.height > 800:
                img.thumbnail((800, 800))
            img.convert('RGB').save(output, format='JPEG', quality=85)
            return output.getvalue()
    except FloodWaitError as e:
        wait_time = e.seconds
        logger.warning(f"Превышен лимит запросов API Telegram. Ожидание {wait_time} секунд")
        # await asyncio.sleep(wait_time)
        return await fetch_user_photo(user_id)
        return await fetch_user_photo(client, user_id)
    except (Image.UnidentifiedImageError, TypeError) as e:
        logger.error(f"Ошибка при получении фото для {user_id}: {e}")
        with open(errors_log, "a", encoding="utf-8") as ef:
            ef.write(f"{user_id}: {e}\n")
        return None
    except Exception as e:
        logger.error(f"Неизвестная ошибка при получении фото для {user_id}: {e}")
        with open(errors_log, "a", encoding="utf-8") as ef:
            ef.write(f"{user_id}: {e}\n")
        return None
    except PeerIdInvalidError:
        logger.warning(f"Пользователь {user_id} не найден (PeerIdInvalidError)")
        return None
    except Exception as e:
        logger.error(f"Ошибка при получении фото для {user_id}: {e}", exc_info=True)
        return None

async def fill_json_users(user_ids_from_json):
    """
    Заполняет профили пользователей из JSON экспорта Telegram.
    Args:
        user_ids_from_json: список ID пользователей из JSON
    """
    if not user_ids_from_json:
        logger.error("Список user_ids_from_json пуст!")
        return

    # Инициализируем клиент
    client = await get_client()
    await client.start()

    # Логируем пользователей без данных для анализа
    no_data_log = os.path.join(EXPORT_DIR, 'users_skipped_no_data.log')
    
    # Проверяем подключение к БД
    try:
        async with SessionLocal() as session:
            # Проверка подключения
            logger.info("Подключение к БД успешно установлено")
            
            result = await session.execute(select(User.id))
            user_ids_in_db = set(row[0] for row in result.all())
            new_ids = user_ids_from_json - user_ids_in_db
            update_ids = user_ids_from_json & user_ids_in_db
            
            logger.info(f"Новых ID: {len(new_ids)}, ID для обновления: {len(update_ids)}")

            await client.start()

            # Добавляем новых пользователей только из result.json
            total = len(new_ids)
            processed = 0
            skipped = 0
            with tqdm(total=total, desc='Обработка пользователей', ncols=100) as pbar:
                for idx, uid in enumerate(new_ids, 1):
                    logger.info(f"Пробуем получить entity по user_id={uid} (type={type(uid)})")
                    entity = await safe_get_entity(client, uid)
                    if entity is None:
                        logger.warning(f"Не удалось получить entity по user_id={uid}, type={type(uid)}")
                        with open('not_found_user_ids.txt', 'a', encoding='utf-8') as f:
                            f.write(f'{uid}\n')
                        username_candidate = user_id_to_username.get(uid)
                        if username_candidate:
                            logger.info(f"Пробуем получить entity по username={username_candidate} для user_id={uid}")
                            entity = await safe_get_entity(client, username_candidate)
                            if entity:
                                logger.info(f"Удалось получить entity по username={username_candidate} для user_id={uid}")
                                with open('found_by_username_user_ids.txt', 'a', encoding='utf-8') as f:
                                    f.write(f'{uid}\t{username_candidate}\n')
                            else:
                                logger.warning(f"Не удалось получить entity по username={username_candidate} для user_id={uid}")
                                with open('not_found_by_username_user_ids.txt', 'a', encoding='utf-8') as f:
                                    f.write(f'{uid}\t{username_candidate}\n')
                                # Продолжаем обработку текущего пользователя, даже если не удалось получить entity по username
                                continue
                        else:
                            logger.warning(f"Не удалось получить entity для user_id={uid} (нет username)")
                            # Продолжаем обработку текущего пользователя, даже если не удалось получить entity
                            continue
                    else:
                        with open('found_by_id_user_ids.txt', 'a', encoding='utf-8') as f:
                            f.write(f'{uid}\n')
                    username = getattr(entity, 'username', None)
                    first_name = getattr(entity, 'first_name', None)
                    last_name = getattr(entity, 'last_name', None)
                    # Сначала получаем фото
                    photo_bytes = await fetch_user_photo(client, uid)
                    # Проверяем наличие хотя бы одного не пустого поля
                    has_data = any([username, first_name, last_name, photo_bytes])
                    if not has_data:
                        logger.warning(f"Пропускаем пользователя {uid} - нет данных для создания")
                        skipped += 1
                        status = 'SKIP (no data)'
                        continue
                    processed += 1
                    status = 'OK'
                    markers = {'from_json': True}
                    # Если first_name пустой, используем username или 'Unknown'
                    final_first_name = first_name or username or 'Unknown'
                    
                    session.add(User(
                        id=uid,
                        username=username or '',  # Заменяем None на пустую строку
                        first_name=final_first_name,  # Гарантируем, что first_name не пустой
                        last_name=last_name or '',    # Заменяем None на пустую строку
                        is_active=True,
                        photo_jpeg=photo_bytes,
                        markers=markers,
                        streams=[]  # Инициализируем пустой список потоков
                    ))
                    pbar.set_postfix({'OK': processed, 'SKIP': skipped})
                    pbar.update(1)
            print(f"Итого новых пользователей: {total}, успешно добавлено: {processed}, пропущено: {skipped}")
            logger.info(f"Итого новых пользователей: {total}, успешно добавлено: {processed}, пропущено: {skipped}")

            # Обновляем существующих пользователей из result.json
            for uid in update_ids:
                user = await session.get(User, uid)
                if user:
                    if not user.markers or not isinstance(user.markers, dict):
                        user.markers = {}
                    user.markers['from_json'] = True
                    try:
                        entity = await client.get_entity(uid)
                        user.username = getattr(entity, 'username', user.username)
                        user.first_name = getattr(entity, 'first_name', user.first_name)
                        user.last_name = getattr(entity, 'last_name', user.last_name)
                        if user.photo_jpeg is None:
                            photo_bytes = await fetch_user_photo(uid)
                            if photo_bytes:
                                user.photo_jpeg = photo_bytes
                    except PeerIdInvalidError:
                        continue

            await session.commit()
            await client.disconnect()
            print(f"Добавлено новых: {len(new_ids)}. Обновлено: {len(update_ids)}. Данные пользователей из result.json актуализированы.")

        await fill_all_profiles(settings.our_channel_id)
    except Exception as e:
        logger.error(f"Ошибка при работе с базой данных: {e}")
        with open(no_data_log, "a", encoding="utf-8") as ef:
            ef.write(f"Ошибка при работе с базой данных: {e}\n")

if __name__ == '__main__':
    user_ids = extract_user_ids()
    if not user_ids:
        print('user_ids не найдены — экспорт Telegram пуст или некорректен. Завершение работы.')
    else:
        asyncio.run(fill_json_users(user_ids))
