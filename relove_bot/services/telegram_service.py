import logging
import re
from io import BytesIO
from typing import Optional, List, Dict, Any
from telethon import TelegramClient
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.types import User, Channel, Message
from relove_bot.config import settings

# --- Конфиг ---
from pydantic import SecretStr

API_ID = settings.tg_api_id.get_secret_value() if isinstance(settings.tg_api_id, SecretStr) else settings.tg_api_id
API_HASH = settings.tg_api_hash.get_secret_value() if isinstance(settings.tg_api_hash, SecretStr) else settings.tg_api_hash
SESSION = settings.tg_session.get_secret_value() if isinstance(settings.tg_session, SecretStr) else settings.tg_session

client = TelegramClient(SESSION, int(API_ID), str(API_HASH))

async def start_client():
    if not client.is_connected():
        await client.start()
        logging.info("Telethon client started")

import base64
from relove_bot.rag.llm import LLM

async def analyze_photo_via_llm(photo_bytes: bytes) -> str:
    """
    Отправляет фото в OpenAI Vision (через LLM.analyze_content) и возвращает summary.
    """
    img_b64 = base64.b64encode(photo_bytes).decode()
    llm = LLM()
    result = await llm.analyze_content(image_base64=img_b64, system_prompt="Опиши психологические черты пользователя по фото профиля.", max_tokens=256)
    return result["summary"]

async def openai_psychological_summary(text: str, image_url: str = None) -> str:
    """
    Отправляет текст и/или фото в LLM.analyze_content и возвращает психологический портрет пользователя.
    """
    llm = LLM()
    prompt = "Ты — профессиональный психолог и эксперт по анализу личности. Проанализируй личность пользователя по представленному тексту и/или фото."
    result = await llm.analyze_content(text=text, image_url=image_url, system_prompt=prompt, max_tokens=512)
    return result["summary"]

async def get_full_psychological_summary(user_id: int, main_channel_id: Optional[str] = None, tg_user=None) -> str:
    """
    Строит полный психологический портрет пользователя на основе:
    - bio (about)
    - постов пользователя в основном канале (main_channel_id)
    - постов в личном канале (если есть)
    - анализа фото профиля (LLM)
    Всегда анализирует фото, если оно есть.
    Возвращает итоговое summary для вставки в контекст истории.
    """
    user = tg_user if tg_user is not None else await client.get_entity(user_id)
    bio = getattr(user, 'about', '') or ''
    main_posts = []
    if main_channel_id:
        try:
            main_posts = await get_user_posts_in_channel(main_channel_id, user_id)
        except Exception as e:
            logging.warning(f"[get_full_psychological_summary] Не удалось получить посты пользователя в основном канале: {e}")
    personal_posts = []
    photo_summaries = []
    try:
        personal = await get_personal_channel_posts(user_id)
        personal_posts = personal.get("posts", [])
        photo_summaries = personal.get("photo_summaries", [])
    except Exception as e:
        logging.warning(f"[get_full_psychological_summary] Не удалось получить личные посты/фото: {e}")
    # Анализируем все фото профиля (если есть)
    if not photo_summaries:
        # Если get_personal_channel_posts не дал фото — пробуем напрямую
        async for photo in client.iter_profile_photos(user_id):
            bioio = BytesIO()
            await client.download_media(photo, file=bioio)
            bioio.seek(0)
            img_bytes = bioio.read()
            summary = await analyze_photo_via_llm(img_bytes)
            photo_summaries.append(summary)
    # Собираем всё для LLM
    llm = LLM()
    llm_input = (
        f"Биография пользователя:\n{bio}\n"
        f"Посты пользователя в основном канале:\n{chr(10).join(main_posts)}\n"
        f"Посты пользователя в личном канале:\n{chr(10).join(personal_posts)}\n"
        f"Фото профиля проанализированы автоматически."
    )
    # Вызов LLM для получения психологического портрета (всегда с фото, если есть хотя бы одно)
    image_url = None
    if photo_summaries:
        # Для vision — используем последнее фото (можно расширить до нескольких)
        # Для полного анализа можно добавить несколько image_url — сейчас поддерживается только один
        # Поэтому берём последнее фото пользователя
        async for photo in client.iter_profile_photos(user_id, limit=1):
            bioio = BytesIO()
            await client.download_media(photo, file=bioio)
            bioio.seek(0)
            img_bytes = bioio.read()
            import base64
            img_b64 = base64.b64encode(img_bytes).decode()
            break
    logging.warning(f"LLM INPUT for user {user_id}: {llm_input[:500]}")
    if 'img_b64' in locals():
        logging.warning(f"LLM IMAGE for user {user_id}: есть фото (base64 длина {len(img_b64)})")
    try:
        result = await llm.analyze_content(
            text=llm_input,
            image_base64=img_b64 if 'img_b64' in locals() else None,
            system_prompt=(
                "Ты — профессиональный психолог и эксперт по анализу личности. "
                "Сделай краткий психологический анализ личности пользователя на русском языке по тексту и/или фото. "
                "Если данных мало, анализируй только то, что есть. Не пиши никаких отказов, комментариев о невозможности анализа или просьб предоставить больше данных. Просто дай анализ."
            ),
            max_tokens=512
        )
        logging.warning(f"LLM RAW RESPONSE for user {user_id}: {result['raw_response']}")
        logging.warning(f"LLM SUMMARY for user {user_id}: {result['summary']}")
        return result["summary"]
    except Exception as e:
        # Специальный отлов ошибки баланса OpenAI/OpenRouter
        if (hasattr(e, 'status_code') and getattr(e, 'status_code', None) == 402) or 'Insufficient credits' in str(e):
            logging.error(f"[get_full_psychological_summary] Недостаточно кредитов для LLM/OpenAI/OpenRouter! Пополните баланс: https://openrouter.ai/settings/credits")
        else:
            logging.error(f"[get_full_psychological_summary] Ошибка LLM: {e}")
        raise


async def get_personal_channel_entity(user_id: int):
    """
    Прямое получение entity личного канала пользователя через GetFullUserRequest.personal_channel_id.
    Возвращает entity канала или None, если не найден.
    """
    try:
        full = await client(GetFullUserRequest(user_id))
        pc_id = getattr(full.full_user, 'personal_channel_id', None)
        if pc_id:
            entity = await client.get_entity(pc_id)
            return entity
        return None
    except Exception as e:
        logging.warning(f"[get_personal_channel_entity] Ошибка получения личного канала: {e}")
        return None

async def get_user_posts_in_channel(channel_id_or_username: str, user_id: int, limit: int = 100) -> List[str]:
    posts = []
    async for msg in client.iter_messages(channel_id_or_username, from_user=user_id, limit=limit):
        if msg.text:
            posts.append(msg.text)
    return posts

async def get_personal_channel_id(user_id: int) -> Optional[int]:
    """
    Получает ID личного канала пользователя через GetFullUserRequest (если привязан).
    """
    try:
        full = await client(GetFullUserRequest(user_id))
        pc_id = getattr(full.full_user, 'personal_channel_id', None)
        return pc_id
    except Exception as e:
        logging.warning(f"[get_personal_channel_id] Ошибка получения personal_channel_id: {e}")
        return None

async def get_personal_channel_posts(user_id: int, limit: int = 100) -> Dict[str, Any]:
    """
    Получает посты из личного канала пользователя (через personal_channel_id или fallback по username/bio).
    """
    posts = []
    channel_link = None
    # 1. Пробуем через personal_channel_id
    pc_id = await get_personal_channel_id(user_id)
    if pc_id:
        channel_link = pc_id
    else:
        # 2. Fallback: username пользователя
        user = await client.get_entity(user_id)
        if getattr(user, 'username', None):
            candidate = user.username
            try:
                entity = await client.get_entity(candidate)
                if hasattr(entity, 'broadcast') or hasattr(entity, 'megagroup'):
                    channel_link = candidate
            except Exception as e:
                logging.info(f"[get_personal_channel_posts] Не удалось получить канал по username {candidate}: {e}")
        # 3. Fallback: ищем ссылку на канал в bio
        if not channel_link:
            bio = getattr(user, 'about', '') or ''
            match = re.search(r'(t\.me\/(\w+))|(@\w+)', bio)
            if match:
                username = match.group(2) or (match.group(0)[1:] if match.group(0).startswith('@') else None)
                if username:
                    try:
                        entity = await client.get_entity(username)
                        if hasattr(entity, 'broadcast') or hasattr(entity, 'megagroup'):
                            channel_link = username
                    except Exception as e:
                        logging.info(f"[get_personal_channel_posts] Не удалось получить канал по ссылке из bio {username}: {e}")
    # Получаем посты
    if channel_link:
        try:
            async for msg in client.iter_messages(channel_link, limit=limit):
                if msg.text:
                    posts.append(msg.text)
        except Exception as e:
            logging.warning(f"[get_personal_channel_posts] Не удалось получить посты из {channel_link}: {e}")
    # Фото профиля -> анализ через LLM
    photo_summaries = []
    async for photo in client.iter_profile_photos(user_id):
        bio = BytesIO()
        await client.download_media(photo, file=bio)
        bio.seek(0)
        img_bytes = bio.read()
        summary = await analyze_photo_via_llm(img_bytes)
        photo_summaries.append(summary)
    return {"posts": posts, "photo_summaries": photo_summaries}

async def get_channel_users(channel_id_or_username: str) -> List[int]:
    users = set()
    async for user in client.iter_participants(channel_id_or_username):
        users.add(user.id)
    return list(users)
