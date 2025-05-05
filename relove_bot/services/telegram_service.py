import asyncio
import base64
import logging
import os
import re
import sys
from typing import Optional, Any, Dict, List
from telethon import TelegramClient
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.functions.channels import GetParticipantRequest, GetParticipantsRequest, GetFullChannelRequest
from telethon.tl.types import ChannelParticipantsSearch, Channel, Message, User
from tqdm.asyncio import tqdm

from pydantic import SecretStr
from relove_bot.config import settings
from relove_bot.rag.llm import LLM

API_ID = settings.tg_api_id
API_HASH = settings.tg_api_hash if not isinstance(settings.tg_api_hash, SecretStr) else settings.tg_api_hash.get_secret_value()
SESSION = settings.tg_session.get_secret_value() if isinstance(settings.tg_session, SecretStr) else settings.tg_session

_client = None

async def get_client():
    global _client
    if _client is None:
        _client = TelegramClient(SESSION, int(API_ID), str(API_HASH))
    return _client

async def get_bot_client():
    global _client
    if _client is None:
        _client = TelegramClient('user_session', int(settings.tg_api_id), str(settings.tg_api_hash.get_secret_value()))
        await _client.start()
    return _client

async def start_client():
    global _client
    if _client is None:
        _client = await get_client()
    if not _client.is_connected():
        await _client.start()
        logging.info("Telethon client started")

import base64
from relove_bot.rag.llm import LLM
import logging

logger = logging.getLogger(__name__)

# Экспортируем сервис как объект
telegram_service = sys.modules[__name__]

async def analyze_photo_via_llm(photo_bytes: bytes) -> str:
    """
    Отправляет фото в OpenAI Vision (через LLM.analyze_content) и возвращает summary.
    """
    img_b64 = base64.b64encode(photo_bytes).decode()
    llm = LLM()
    result = await llm.analyze_content(
        image_base64=img_b64,
        system_prompt="Кратко опиши психологические черты пользователя по фото профиля.",
        max_tokens=128
    )
    return result["summary"]

async def openai_psychological_summary(text: str, image_url: str = None) -> str:
    """
    Отправляет текст и/или фото в LLM.analyze_content и возвращает психологический портрет пользователя.
    """
    llm = LLM()
    prompt = "Ты — профессиональный психолог. Проанализируй личность пользователя по представленному тексту и/или фото. Дай краткий, информативный портрет."
    result = await llm.analyze_content(
        text=text,
        image_url=image_url,
        system_prompt=prompt,
        max_tokens=256
    )
    return result["summary"]

async def get_full_psychological_summary(user_id: int, main_channel_id: Optional[str] = None, tg_user=None, posts: Optional[list] = None) -> tuple[str, bytes, list]:
    """
    Строит полный психологический портрет пользователя на основе:
    - bio (about)
    - постов пользователя в основном канале (main_channel_id)
    - постов в личном канале (если есть)
    - анализа фото профиля (LLM)
    Всегда анализирует фото, если оно есть.
    Возвращает итоговое summary для вставки в контекст истории.
    """
    client = await get_client()
    user = tg_user if tg_user is not None else await client.get_entity(user_id)
    bio = getattr(user, 'about', '') or ''
    
    # Получаем все посты сразу, если они не переданы
    if posts is None:
        main_posts = []
        if main_channel_id:
            try:
                main_posts = await get_user_posts_in_channel(main_channel_id, user_id)
            except Exception as e:
                logging.warning(f"[get_full_psychological_summary] Не удалось получить посты пользователя в основном канале: {e}")
        
        try:
            personal = await get_personal_channel_posts(user_id)
            personal_posts = personal.get("posts", [])
            photo_summaries = personal.get("photo_summaries", [])
        except Exception as e:
            logging.warning(f"[get_full_psychological_summary] Не удалось получить личные посты/фото: {e}")
            personal_posts = []
            photo_summaries = []
    else:
        main_posts = posts
        personal_posts = []
        photo_summaries = []

    # Формируем текст для анализа
    all_posts = main_posts + personal_posts
    posts_text = "\n".join(all_posts)
    
    # Генерируем summary
    summary = await openai_psychological_summary(text=(bio + "\n" + posts_text), image_url=None)
    
    # Добавляем summary по фото, если есть
    if photo_summaries:
        # Для vision — используем последнее фото (можно расширить до нескольких)
        # Для полного анализа можно добавить несколько image_url — сейчас поддерживается только один
        last_photo_bytes = None
        async for photo in client.iter_profile_photos(user_id, limit=1):
            bioio = BytesIO()
            await client.download_media(photo, file=bioio)
            bioio.seek(0)
            img_bytes = bioio.read()
            img_b64 = base64.b64encode(img_bytes).decode()
            last_photo_bytes = img_bytes
            break
    llm_input = bio + '\n'.join(main_posts + personal_posts)
    logging.warning(f"LLM INPUT for user {user_id}: {llm_input[:500]}")
    if 'img_b64' in locals():
        logging.warning(f"LLM IMAGE for user {user_id}: есть фото (base64 длина {len(img_b64)})")
    # Если нет текста и фото — логируем и возвращаем None
    if not llm_input.strip() and 'img_b64' not in locals():
        export_dir = os.getenv('TELEGRAM_EXPORT_PATH', '.')
        no_data_log = os.path.join(export_dir, 'users_skipped_no_data.log')
        with open(no_data_log, 'a', encoding='utf-8') as logf:
            logf.write(f"{user_id}\n")
        logging.warning(f"User {user_id} пропущен: нет текста и фото для анализа.")
        return None, None, []
    
    # Определяем потоки reLove на основе постов
    from relove_bot.utils.relove_streams import detect_relove_streams_by_posts
    streams_result = await detect_relove_streams_by_posts(main_posts + personal_posts)
    streams = streams_result.get('completed', [])
    
    # Повторные попытки для LLM
    max_llm_attempts = 3
    for attempt in range(1, max_llm_attempts + 1):
        try:
            llm = LLM()
            try:
                result = await asyncio.wait_for(
                    llm.analyze_content(
                        text=llm_input,
                        image_base64=img_b64 if 'img_b64' in locals() else None,
                        system_prompt=(
                            "Ты — профессиональный психолог и эксперт по анализу личности. "
                            "Сделай краткий психологический анализ личности пользователя на русском языке по тексту и/или фото. "
                            "Если данных мало, анализируй только то, что есть. Не пиши никаких отказов, комментариев о невозможности анализа или просьб предоставить больше данных. Просто дай анализ."
                        ),
                        max_tokens=512
                    ),
                    timeout=60
                )
            except asyncio.TimeoutError:
                logging.error(f"Таймаут при обработке LLM для user {user_id}")
                return None
            logging.warning(f"LLM RAW RESPONSE for user {user_id}: {result['raw_response']}")
            logging.warning(f"LLM SUMMARY for user {user_id}: {result['summary']}")
            return result["summary"], last_photo_bytes, streams
        except Exception as e:
            logging.error(f"Попытка {attempt}/{max_llm_attempts} — Ошибка LLM для user {user_id}: {e}")
            import asyncio
            if attempt < max_llm_attempts:
                await asyncio.sleep(5)
            else:
                # Специальный отлов ошибки баланса OpenAI/OpenRouter
                if (hasattr(e, 'status_code') and getattr(e, 'status_code', None) == 402) or 'Insufficient credits' in str(e):
                    logging.error(f"[get_full_psychological_summary] Недостаточно кредитов для LLM/OpenAI/OpenRouter! Пополните баланс: https://openrouter.ai/settings/credits")
                else:
                    logging.error(f"[get_full_psychological_summary] Ошибка LLM: {e}")
                return None


async def get_personal_channel_entity(user_id: int):
    """
    Прямое получение entity личного канала пользователя через GetFullUserRequest.personal_channel_id.
    Возвращает entity канала или None, если не найден.
    """
    client = await get_client()
    try:
        full_user = await client(GetFullUserRequest(user_id))
        pc_id = getattr(full_user.full_user, 'personal_channel_id', None)
        if pc_id:
            entity = await client.get_entity(pc_id)
            return entity
        return None
    except Exception as e:
        logging.warning(f"[get_personal_channel_entity] Ошибка получения личного канала: {e}")
        return None

async def get_user_posts_in_channel(channel_id_or_username: str, user_id: int, limit: int = 1000) -> List[str]:
    client = await get_client()
    posts = []
    async for msg in client.iter_messages(channel_id_or_username, from_user=user_id, limit=limit):
        if msg.text:
            posts.append(msg.text)
    return posts

async def get_personal_channel_id(user_id: int) -> Optional[int]:
    """
    Получает ID личного канала пользователя через GetFullUserRequest (если привязан).
    """
    client = await get_client()
    try:
        full_user = await client(GetFullUserRequest(user_id))
        pc_id = getattr(full_user.full_user, 'personal_channel_id', None)
        return pc_id
    except Exception as e:
        logging.warning(f"[get_personal_channel_id] Ошибка получения personal_channel_id: {e}")
        return None

async def get_personal_channel_posts(user_id: int, limit: int = 100):
    """
    Получает посты из личного канала пользователя (через personal_channel_id или fallback по username/bio).
    """
    client = await get_client()
    user = await client.get_entity(user_id)
    posts = []
    channel_link = None

    # 1. Прямое получение через personal_channel_id
    try:
        entity = await get_personal_channel_entity(user_id)
        if entity:
            channel_link = entity.username
    except Exception as e:
        logging.info(f"[get_personal_channel_posts] Не удалось получить личный канал через personal_channel_id: {e}")

    # 2. Если не нашли через personal_channel_id, ищем в bio
    if not channel_link:
        bio = getattr(user, 'about', '') or ''
        if bio:
            # Ищем @username или t.me/username
            match = re.search(r'(@\w+)|(t\.me/\w+)', bio)
            if match:
                username = match.group(1)[1:] if match.group(1) else match.group(2).split('/')[-1]
                try:
                    entity = await client.get_entity(username)
                    if hasattr(entity, 'broadcast') or hasattr(entity, 'megagroup'):
                        channel_link = username
                except Exception as e:
                    logging.info(f"[get_personal_channel_posts] Не удалось получить канал по username {username}: {e}")

    # Получаем посты только если нашли канал
    if channel_link:
        try:
            async for msg in client.iter_messages(channel_link, limit=limit):
                if msg.text:
                    posts.append(msg.text)
        except Exception as e:
            logging.warning(f"[get_personal_channel_posts] Не удалось получить посты из {channel_link}: {e}")

    # Фото профиля -> анализ через LLM
    photo_summaries = []
    # Получаем только последнее фото профиля
    async for photo in client.iter_profile_photos(user_id, limit=1):
        bio = BytesIO()
        await client.download_media(photo, file=bio)
        bio.seek(0)
        img_bytes = bio.read()
        summary = await analyze_photo_via_llm(img_bytes)
        photo_summaries.append(summary)
        break

    return {"posts": posts, "photo_summaries": photo_summaries}

async def get_user_profile_summary(user_id: int) -> str:
    """
    Получает психологический портрет пользователя.
    
    Args:
        user_id: ID пользователя
    
    Returns:
        Строка с психологическим портретом
    """
    try:
        client = await get_bot_client()
        
        user = await client.get_entity(user_id)
        if user:
            return await get_full_psychological_summary(user_id, tg_user=user)
        return None
    finally:
        if client:
            await client.disconnect()

from relove_bot.db.models import GenderEnum

async def get_user_gender(user_id: int, client=None) -> GenderEnum:
    """
    Определяет пол пользователя.
    
    Args:
        user_id: ID пользователя
        client: Существующий клиент Telethon (опционально)
    
    Returns:
        Перечисление GenderEnum с полом (male, female, unknown)
    """
    try:
        if not client:
            client = await get_bot_client()
        
        user_info = await get_full_user(user_id, client=client)
        if user_info:
            gender = await detect_gender(user_info, client=client)
            return GenderEnum(gender)
        return GenderEnum.unknown
    except Exception as e:
        logger.error(f"Ошибка при определении пола пользователя {user_id}: {e}")
        return GenderEnum.unknown

async def get_channel_participants_count(channel_id_or_username: str):
    """
    Получает общее количество участников в канале.
    
    Args:
        channel_id_or_username: ID или username канала
    
    Returns:
        Количество участников в канале
    """
    try:
        client = await get_bot_client()
        
        # Получаем информацию о канале
        channel = await client.get_entity(channel_id_or_username)
        
        # Получаем полную информацию о канале
        full_channel = await client(GetFullChannelRequest(channel))
        
        # Возвращаем количество участников
        return full_channel.full_chat.participants_count
    except Exception as e:
        logger.error(f"Ошибка при получении количества участников канала: {e}")
        raise
    finally:
        if client:
            await client.disconnect()

async def get_full_user(user_id: int, client=None):
    """
    Получает полную информацию о пользователе через GetFullUserRequest.
    
    Args:
        user_id: ID пользователя
        client: Существующий клиент Telethon (опционально)
    
    Returns:
        Объект User с информацией о пользователе
    """
    try:
        if not client:
            client = await get_bot_client()
        full_user = await client(GetFullUserRequest(user_id))
        
        # Возвращаем объект User
        return full_user.users[0]
    except Exception as e:
        logger.error(f"Ошибка при получении полной информации о пользователе {user_id}: {e}")
        raise

async def get_channel_users(channel_id_or_username: str, batch_size: int = 200):
    """
    Асинхронно получает всех пользователей из канала порциями.
    
    Args:
        channel_id_or_username: ID или username канала
        batch_size: размер пакета для получения участников (максимум 200)
    
    Returns:
        Асинхронный генератор, который возвращает ID пользователей
    """
    try:
        client = await get_bot_client()
        
        # Получаем информацию о канале
        channel = await client.get_entity(channel_id_or_username)
        logger.info(f"Получена информация о канале: {channel}")
        
        # Инициализируем параметры пагинации
        offset = 0
        total_count = await get_channel_participants_count(channel)
        
        while offset < total_count:
            # Получаем участников с текущим смещением
            participants = await client(GetParticipantsRequest(
                channel=channel,
                filter=ChannelParticipantsSearch(''),
                offset=offset,
                limit=batch_size,
                hash=0
            ))
            
            # Обрабатываем полученных пользователей
            for user in participants.users:
                yield user.id
                
                # Делаем паузу между пользователями
                await asyncio.sleep(0.5)
            
            # Обновляем смещение
            offset += batch_size
            
            # Делаем паузу между батчами
            await asyncio.sleep(1.0)
    except Exception as e:
        logger.error(f"Ошибка при получении пользователей из канала: {e}")
        raise
    finally:
        if client:
            await client.disconnect()