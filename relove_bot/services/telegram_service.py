import asyncio
import base64
import logging
import os
import re
import sys
import time
from typing import Optional, Any, Dict, List, Tuple, Union, AsyncGenerator

from telethon import TelegramClient, events
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.functions.channels import GetParticipantRequest, GetParticipantsRequest, GetFullChannelRequest, GetChannelsRequest
from telethon.tl.types import ChannelParticipantsSearch, Channel, Message, User, UserProfilePhoto
from telethon.errors import ChatAdminRequiredError, ChannelPrivateError, UserNotParticipantError
from tqdm.asyncio import tqdm
from io import BytesIO

from pydantic import SecretStr
from relove_bot.config import settings
from relove_bot.rag.llm import LLM
from relove_bot.utils.api_rate_limiter import APIRateLimiter

# Инициализируем кэш и лимитер для модуля
cache = {}
rate_limiter = APIRateLimiter(
    max_requests_per_minute=60,  # Лимит для Telegram API
    max_requests_per_day=5000
)

_client = None

# Экспортируем сервис как объект
telegram_service = sys.modules[__name__]

async def get_client():
    """
    Returns a Telegram client in user mode.
    Uses the session specified in settings.
    """
    global _client
    if _client is None:
        # Получаем значения из настроек с правильной обработкой SecretStr
        api_id = int(settings.tg_api_id)
        api_hash = settings.tg_api_hash.get_secret_value() if hasattr(settings.tg_api_hash, 'get_secret_value') else str(settings.tg_api_hash)
        session_name = settings.tg_session.get_secret_value() if hasattr(settings.tg_session, 'get_secret_value') else str(settings.tg_session)
        
        _client = TelegramClient(
            session=session_name,
            api_id=api_id,
            api_hash=api_hash,
            device_model='reLove Bot',
            system_version='1.0',
            app_version='1.0',
            lang_code='en',
            system_lang_code='en',
        )
    return _client

async def get_bot_client():
    """
    Returns a Telegram client in bot mode.
    Uses the bot token from the environment variables.
    """
    global _client
    try:
        if _client is None:
            # Получаем значения из настроек
            bot_token = os.getenv('BOT_TOKEN')
            api_id = int(os.getenv('TG_API_ID', 0))
            api_hash = os.getenv('TG_API_HASH', '')
            
            if not bot_token:
                logger.error("BOT_TOKEN environment variable is not set")
                raise ValueError("BOT_TOKEN environment variable is not set")
            
            logger.info(f"Initializing Telegram client with API ID: {api_id}")
            _client = TelegramClient('bot', api_id, api_hash)
            
            logger.info("Starting client with bot token...")
            await _client.start(bot_token=bot_token)
            
            # Проверяем успешность подключения
            if not _client.is_connected():
                logger.error("Failed to connect to Telegram")
                raise ConnectionError("Failed to connect to Telegram")
            
            logger.info("Successfully connected to Telegram")
            
        return _client
    except Exception as e:
        logger.error(f"Error in get_bot_client: {e}")
        raise

async def start_client():
    """
    Initializes and starts the Telegram client if it's not already started.
    """
    global _client
    if _client is None:
        _client = await get_client()
    if not _client.is_connected():
        try:
            await _client.start()
            if not await _client.is_user_authorized():
                # If not authorized, we'll need to log in
                await _client.send_code_request(settings.phone_number.get_secret_value())
                # Here you would typically ask for the code and sign in
                # For now, we'll just raise an error
                raise RuntimeError("User not authorized. Please log in first.")
            logging.info("Telethon client started and authorized")
        except Exception as e:
            logging.error(f"Failed to start Telegram client: {e}")
            _client = None
            raise

logger = logging.getLogger(__name__)

# Экспортируем сервис как объект
telegram_service = sys.modules[__name__]

async def get_channel_participants_count(channel_id_or_username: str) -> int:
    """
    Получает количество участников в канале.
    
    Args:
        channel_id_or_username: ID или username канала
        
    Returns:
        Количество участников в канале
    """
    try:
        client = await get_client()
        channel = await client.get_entity(channel_id_or_username)
        
        if not isinstance(channel, Channel):
            logger.error(f"Сущность {channel_id_or_username} не является каналом")
            return 0
            
        # Получаем количество участников
        full_channel = await client(GetFullChannelRequest(channel))
        total_users = full_channel.full_chat.participants_count
        
        logger.info(f"Получено количество участников в канале {channel_id_or_username}: {total_users}")
        return total_users
        
    except Exception as e:
        logger.error(f"Ошибка при получении количества участников канала {channel_id_or_username}: {e}")
        return 0

async def get_channel_users(channel_id_or_username: str, batch_size: int = 200) -> AsyncGenerator[int, None]:
    """
    Получает пользователей из канала максимально быстро, без задержек и повторных попыток.
    Args:
        channel_id_or_username: ID или username канала
        batch_size: Размер пакета для получения пользователей
    Yields:
        ID пользователя
    """
    client = await get_client()
    channel = await client.get_entity(channel_id_or_username)
    if not isinstance(channel, Channel):
        logger.error(f"Сущность {channel_id_or_username} не является каналом")
        return
    offset = 0
    while True:
        participants = await client(GetParticipantsRequest(
            channel=channel,
            filter=ChannelParticipantsSearch(''),
            offset=offset,
            limit=batch_size,
            hash=0
        ))
        if not participants.users:
            break
        for user in participants.users:
            yield user.id
        offset += len(participants.users)

async def analyze_photo_via_llm(photo_bytes: bytes) -> str:
    """
    Отправляет фото в OpenAI Vision (через LLM.analyze_content) и возвращает summary.
    """
    try:
        # Проверяем кэш
        cache_key = f"photo_analysis_{hash(photo_bytes)}"
        if cache_key in cache:
            logger.info(f"Используем кэшированный анализ фото")
            return cache[cache_key]
            
        img_b64 = base64.b64encode(photo_bytes).decode()
        llm = LLM()
        
        # Ждем, пока не будет превышен лимит
        await rate_limiter.wait_for_limit(f"llm_{settings.openai_api_key.get_secret_value()[:5]}")
            
        result = await llm.analyze_content(
            image_base64=img_b64,
            system_prompt="Кратко опиши психологические черты пользователя по фото профиля.",
            max_tokens=128
        )
        
        # Кэшируем результат
        cache[cache_key] = result["summary"]
        logger.info(f"Кэширован результат анализа фото")
            
        return result["summary"]
        
    except Exception as e:
        logger.error(f"Ошибка при анализе фото: {e}")
        return "Не удалось проанализировать фото"

async def openai_psychological_summary(text: str, image_url: str = None) -> str:
    """
    Отправляет текст и/или фото в LLM.analyze_content и возвращает психологический портрет пользователя.
    """
    llm = LLM()
    prompt = "Ты — профессиональный психолог. Проанализируй личность пользователя по представленному тексту и/или фото. Дай краткий, информативный портрет."
    try:
        result = await llm.analyze_content(
            text=text,
            image_url=image_url,
            system_prompt=prompt,
            max_tokens=256
        )
        return result["summary"]
    except Exception as e:
        logging.error(f"Ошибка при генерации психологического профиля: {e}")
        return None

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
    logger.debug(f'Attempting to get entity for user_id: {user_id}')
    user = tg_user if tg_user is not None else await client.get_entity(int(user_id))
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
    
    # Собираем информацию о пользователе для передачи в LLM
    user_info = {}
    if tg_user:
        if hasattr(tg_user, 'first_name'):
            user_info['first_name'] = tg_user.first_name
        if hasattr(tg_user, 'last_name') and tg_user.last_name:
            user_info['last_name'] = tg_user.last_name
        if hasattr(tg_user, 'username') and tg_user.username:
            user_info['username'] = tg_user.username
    
    # Генерируем summary только на основе текста
    summary = await openai_psychological_summary(text=(bio + "\n" + posts_text), image_url=None)
    
    # Инициализируем переменные для фото (оставляем None, так как анализ фото отключен)
    last_photo_bytes = None
    img_b64 = None
    
    # Пропускаем загрузку и анализ фотографий, так как API не поддерживает анализ изображений
    logger.debug(f"Анализ фотографий отключен для пользователя {user_id}")
    
    # Возвращаем пустой список для streams, так как анализ фото отключен
    streams = []
    # Собираем все посты и биографию
    all_posts = main_posts + personal_posts
    
    # Ограничиваем общее количество символов (примерно 20K токенов для подстраховки)
    max_chars = 80000  # Примерно 20K токенов с запасом
    
    # Обрезаем посты, если они слишком длинные
    truncated_posts = []
    total_chars = 0
    
    for post in all_posts:
        if total_chars + len(post) > max_chars:
            # Добавляем только часть поста, чтобы не превысить лимит
            remaining_chars = max(0, max_chars - total_chars)
            if remaining_chars > 100:  # Если осталось достаточно места для осмысленного фрагмента
                truncated_posts.append(post[:remaining_chars] + '... [текст обрезан]')
            break
        truncated_posts.append(post)
        total_chars += len(post)
    
    # Формируем финальный текст для LLM
    llm_input = bio + '\n'.join(truncated_posts)
    
    logging.warning(f"LLM INPUT for user {user_id}: {llm_input[:500]}...")
    if img_b64 is not None:
        logging.warning(f"LLM IMAGE for user {user_id}: есть фото (base64 длина {len(img_b64)})")
    
    # Если нет текста и фото — логируем и возвращаем None
    if not llm_input.strip() and img_b64 is None:
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
    max_llm_attempts = settings.llm_attempts
    for attempt in range(1, max_llm_attempts + 1):
        try:
            llm = LLM()
            try:
                result = await asyncio.wait_for(
                    llm.analyze_content(
                        text=llm_input,
                        image_base64=img_b64 if img_b64 is not None else None,
                        system_prompt=PSYCHOLOGICAL_ANALYSIS_PROMPT,
                        max_tokens=2048,
                        user_info=user_info
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
            if attempt < max_llm_attempts:
                # await asyncio.sleep(5)
                pass
            else:
                # Специальный отлов ошибки баланса OpenAI/OpenRouter
                if (hasattr(e, 'status_code') and getattr(e, 'status_code', None) == 402) or 'Insufficient credits' in str(e):
                    logging.error(f"[get_full_psychological_summary] Недостаточно кредитов для LLM/OpenAI/OpenRouter! Пополните баланс: https://openrouter.ai/settings/credits")
                else:
                    logging.error(f"[get_full_psychological_summary] Ошибка LLM: {e}")
                return None, None, []

async def get_full_user(user_id: int) -> Optional[User]:
    """
    Получает полную информацию о пользователе.
    """
    try:
        # Получаем полную информацию о пользователе
        full_user = await asyncio.wait_for(
            (await get_client())(GetFullUserRequest(user_id)),
            timeout=30
        )
        
        if not full_user or not full_user.user:
            logger.warning(f"Не удалось получить полную информацию о пользователе {user_id}")
            return None
            
        # Получаем информацию о канале
        try:
            channel = await asyncio.wait_for(
                (await get_client())(GetChannelRequest(full_user.user.id)),
                timeout=30
            )
        except asyncio.CancelledError:
            logger.warning(f"Задача получения канала для пользователя {user_id} была отменена")
            return None
            
        return full_user.user
    except asyncio.TimeoutError:
        logger.warning(f"Timeout при получении информации о пользователе {user_id}")
        return None
    except asyncio.CancelledError:
        logger.warning(f"Задача получения пользователя {user_id} была отменена")
        return None
    except Exception as e:
        logger.error(f"Ошибка при получении информации о пользователе {user_id}: {e}")
        return None




async def get_user_psychological_summary(user_id: int, tg_user: User, bio: str, posts_text: str) -> Tuple[Optional[str], Optional[bytes], List[str]]:
    """
    Получает психологический профайл пользователя с помощью LLM.
    
    Args:
        user_id: ID пользователя
        tg_user: Объект пользователя Telethon
        bio: Биография пользователя
        posts_text: Текст постов пользователя
        
    Returns:
        Кортеж (summary, photo_bytes, streams)
    """
    try:
        # Собираем информацию о пользователе для передачи в LLM
        user_info = {}
        if tg_user:
            if hasattr(tg_user, 'first_name'):
                user_info['first_name'] = tg_user.first_name
            if hasattr(tg_user, 'last_name') and tg_user.last_name:
                user_info['last_name'] = tg_user.last_name
            if hasattr(tg_user, 'username') and tg_user.username:
                user_info['username'] = tg_user.username

        # Генерируем summary
        summary = await openai_psychological_summary(text=(bio + "\n" + posts_text), image_url=None)
        return summary, None, []
    except Exception as e:
        logging.error(f"Ошибка при получении психологического профиля: {e}")
        return None, None, []

async def get_personal_channel_entity(user_id: int) -> Optional[Channel]:
    """Получает сущность персонального канала пользователя."""
    try:
        # Получаем полную информацию о пользователе
        full_user = await get_full_user(user_id)
        if full_user:
            channel = await asyncio.wait_for(
                (await get_client())(GetChannelRequest(full_user.id)),
                timeout=30
            )
            return channel
        else:
            return None
    except Exception as e:
        logger.error(f"Ошибка при получении информации о пользователе {user_id}: {e}")
        return None




async def get_user_posts_in_channel(channel_id_or_username: str, user_id: int, limit: int = 1000) -> List[str]:
    """
    Получает посты пользователя в указанном канале.
    
    Args:
        channel_id_or_username: ID или username канала
        user_id: ID пользователя, чьи посты нужно получить
        limit: максимальное количество постов для получения
        
    Returns:
        Список текстов постов пользователя
    """
    client = await get_client()
    posts = []
    
    try:
        # Проверяем, что у нас есть доступ к каналу
        try:
            channel = await client.get_entity(channel_id_or_username)
            logger.info(f"Получаем посты пользователя {user_id} из канала {getattr(channel, 'title', 'N/A')} (ID: {getattr(channel, 'id', 'N/A')})")
        except Exception as e:
            logger.warning(f"Не удалось получить доступ к каналу {channel_id_or_username}: {e}")
            return []
        
        # Получаем посты с обработкой ошибок
        try:
            async for msg in client.iter_messages(channel_id_or_username, from_user=user_id, limit=limit):
                try:
                    if msg and hasattr(msg, 'text') and msg.text:
                        posts.append(msg.text)
                except Exception as e:
                    logger.warning(f"Ошибка при обработке сообщения: {e}")
                    continue
                    
        except Exception as e:
            logger.warning(f"Ошибка при получении сообщений из канала {channel_id_or_username}: {e}")
            return []
            
    except Exception as e:
        logger.error(f"Неизвестная ошибка при получении постов пользователя {user_id} из канала {channel_id_or_username}: {e}")
        return []
        
    logger.info(f"Получено {len(posts)} постов пользователя {user_id} из канала {channel_id_or_username}")
    return posts

    client = None
    try:
        client = await get_client()
        full_user = await client(GetFullUserRequest(user_id))
        pc_id = getattr(full_user.full_user, 'personal_channel_id', None)
        if pc_id:
            logger.debug(f"Найден персональный канал {pc_id} для пользователя {user_id}")
        return pc_id
    except Exception as e:
        logger.warning(f"Не удалось получить персональный канал для пользователя {user_id}: {e}")
        return None
    finally:
        if client and client.is_connected():
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

async def get_user_profile_summary(user_id: int, main_channel_id: Optional[str] = None) -> tuple:
    """
    Получает психологический портрет пользователя.
    
    Args:
        user_id: ID пользователя
        main_channel_id: ID основного канала (опционально)
    
    Returns:
        Кортеж (summary, photo_bytes, streams) или (None, None, []) в случае ошибки
    """
    client = None
    try:
        client = await get_bot_client()
        if not client or not client.is_connected():
            logger.error("Не удалось подключиться к клиенту Telegram")
            return None, None, []
            
        user = await client.get_entity(user_id)
        if not user:
            logger.error(f"Пользователь {user_id} не найден")
            return None, None, []
            
        logger.debug(f"Получение профиля пользователя {user_id} (username: {getattr(user, 'username', 'N/A')})")
        
        result = await get_full_psychological_summary(user_id, main_channel_id=main_channel_id, tg_user=user)
        if not result or len(result) != 3:
            logger.error(f"Некорректный формат результата для пользователя {user_id}")
            return None, None, []
            
        summary, photo_bytes, streams = result
        
        # Проверяем типы возвращаемых значений
        if not isinstance(summary, str) or not isinstance(streams, list):
            logger.error(f"Некорректные типы данных в результате для пользователя {user_id}")
            return None, None, []
            
        # Проверяем, что photo_bytes - это bytes или None
        if photo_bytes is not None and not isinstance(photo_bytes, (bytes, bytearray)):
            logger.warning(f"Некорректный тип photo_bytes для пользователя {user_id}, преобразуем в None")
            photo_bytes = None
            
        return summary, photo_bytes, streams
        
    except Exception as e:
        logger.error(f"Ошибка при получении профиля пользователя {user_id}: {e}", exc_info=True)
        return None, None, []
        
    finally:
        if client:
            try:
                # is_connected is a synchronous method, don't use await
                if client.is_connected():
                    await client.disconnect()
            except Exception as e:
                logger.warning(f"Ошибка при отключении клиента: {e}")

from relove_bot.db.models import GenderEnum
from relove_bot.services.prompts import PSYCHOLOGICAL_ANALYSIS_PROMPT

def _determine_gender_from_name(name: str) -> Optional[GenderEnum]:
    """
    Определяет пол по имени.
    
    Args:
        name: Имя для анализа
        
    Returns:
        GenderEnum или None, если не удалось определить
    """
    if not name:
        return None
        
    # Мужские окончания имен
    male_endings = ['й', 'н', 'т', 'р', 'с', 'в', 'д', 'л', 'г', 'к', 'м', 'п']
    # Женские окончания имен
    female_endings = ['а', 'я', 'ь', 'ия']
    
    # Проверяем окончание имени
    last_char = name[-1].lower()
    if last_char in male_endings:
        return GenderEnum.male
    elif last_char in female_endings:
        return GenderEnum.female
        
    return None

async def get_user_gender(user_id: int, client=None, tg_user=None) -> GenderEnum:
    """
    Определяет пол пользователя.
    
    Использует комбинированный подход:
    1. Анализ текстовых полей (имя, фамилия, логин, био)
    2. Анализ фотографии профиля (если доступна)
    
    Args:
        user_id: ID пользователя
        client: Существующий клиент Telethon (опционально)
        tg_user: Объект пользователя Telethon (опционально)
    
    Returns:
        Перечисление GenderEnum с полом (MALE, FEMALE, UNKNOWN)
    """
    logger.info(f"Определение пола для пользователя {user_id}...")
    
    try:
        if not client:
            client = await get_bot_client()
        
        # Если пользователь не передан, получаем его
        if tg_user is None:
            try:
                tg_user = await client.get_entity(user_id)
                logger.debug(f"Получены данные пользователя {user_id}")
            except Exception as e:
                logger.warning(f"Не удалось получить данные пользователя {user_id}: {e}")
                return None
        
        # Получаем информацию о пользователе
        first_name = getattr(tg_user, 'first_name', '')
        last_name = getattr(tg_user, 'last_name', '')
        username = getattr(tg_user, 'username', '')
        bio = getattr(tg_user, 'bio', '')
        
        logger.debug(f"Информация о пользователе {user_id}: имя='{first_name}', фамилия='{last_name}', username='{username}'")
        
        # Получаем фото профиля, если есть
        img_b64 = None
        last_photo_bytes = None
        try:
            async for photo in client.iter_profile_photos(user_id, limit=1):
                bioio = BytesIO()
                await client.download_media(photo, file=bioio)
                bioio.seek(0)
                photo_bytes = bioio.read()
                if photo_bytes:
                    logger.debug(f"Получено фото профиля пользователя {user_id} (размер: {len(photo_bytes)} байт)")
                break
        except Exception as e:
            logger.debug(f"Не удалось получить фото профиля пользователя {user_id}: {e}")
        
        # Используем новый сервис для определения пола
        from relove_bot.services.llm_service import llm_service
        
        try:
            gender = await llm_service.analyze_gender(
                first_name=first_name,
                last_name=last_name,
                username=username,
                bio=bio,
                photo_bytes=photo_bytes
            )
            
            logger.info(f"Определен пол пользователя {user_id}: {gender}")
            return gender
            
        except Exception as e:
            logger.error(f"Ошибка при определении пола пользователя {user_id}: {e}", exc_info=True)
            
    except Exception as e:
        logger.error(f"Критическая ошибка при определении пола пользователя {user_id}: {e}", exc_info=True)
    
    logger.info("Не удалось определить пол пользователя, используется значение по умолчанию: unknown")
    return GenderEnum.unknown

async def get_channel_participants_count(channel_id_or_username: str):
    """
    Получает общее количество участников в канале.
    
    Args:
        channel_id_or_username: ID или username канала
    
    Returns:
        Количество участников в канале
    """
    client = await get_bot_client()
    
    try:
        # Получаем информацию о канале
        channel = await client.get_entity(channel_id_or_username)
        
        # Получаем полную информацию о канале
        full_channel = await client(GetFullChannelRequest(channel))
        
        # Возвращаем количество участников
        return full_channel.full_chat.participants_count
    except Exception as e:
        logger.error(f"Ошибка при получении количества участников канала: {e}")
        raise

async def get_full_user(user_id: int, client=None):
    """
    Получает полную информацию о пользователе через GetFullUserRequest.
    
    Args:
        user_id: ID пользователя
        client: Существующий клиент Telethon (опционально)
    
    Returns:
        Объект User с информацией о пользователе или None, если пользователь не найден
    """
    max_retries = settings.llm_attempts
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            if not client or not client.is_connected():
                client = await get_client()
                if not client.is_connected():
                    await client.start()
                if not await client.is_user_authorized():
                    raise RuntimeError("User not authorized. Please log in first.")
            
            # Получаем канал и общее количество участников
            channel = await client.get_entity(channel_id_or_username)
            if channel is None or not isinstance(channel, Channel):
                logger.error(f"Не удалось получить канал по идентификатору: {channel_id_or_username}")
                raise ValueError(f"Некорректный идентификатор канала: {channel_id_or_username}")
            channel_name = getattr(channel, 'title', str(getattr(channel, 'id', 'N/A')))
            
            # Получаем общее количество участников для прогресс-бара
            full_chat = await client(GetFullChannelRequest(channel=channel))
            total_users = getattr(full_chat.full_chat, 'participants_count', 0)
            
            # Инициализируем прогресс-бар
            if show_progress and total_users > 0:
                pbar = tqdm(
                    total=total_users,
                    desc=f"{channel_name[:20]}..." if len(channel_name) > 20 else channel_name,
                    unit="польз.",
                    bar_format='{l_bar}{bar:50}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]',
                    ncols=120,
                    ascii=' =',
                    miniters=1,
                    dynamic_ncols=True,
                    leave=False,
                    position=0
                )
            
            # Используем итератор участников канала с пагинацией
            async for user in client.iter_participants(channel, limit=None, aggressive=False):
                # Добавляем небольшую задержку между запросами
                # await asyncio.sleep(1)  # 1 секунда задержки между запросами
                try:
                    # Пропускаем ботов и удаленные аккаунты
                    if getattr(user, 'bot', False) or getattr(user, 'deleted', False):
                        if pbar is not None:
                            pbar.total -= 1
                            pbar.refresh()
                        continue
                        
                    logger.debug(f"Обработка пользователя: {getattr(user, 'username', '')} (ID: {getattr(user, 'id', 'N/A')})")
                    
                    # Если функция используется как генератор, возвращаем ID пользователя
                    user_id = user.id
                    yield user_id
                    
                    # Обновляем прогресс-бар для каждого обработанного пользователя
                    if show_progress and pbar is not None:
                        pbar.update(1)
                        processed += 1
                        pbar.set_postfix_str(f"Обработано: {processed}", refresh=True)
                    
                    # Добавляем небольшую задержку каждые batch_size пользователей
                    if processed % batch_size == 0:
                        # await asyncio.sleep(0.5)
                        # Обновляем описание каждые 100 пользователей
                        if processed % 100 == 0 and pbar is not None:
                            pbar.set_description(f"{channel_name[:15]}..." if len(channel_name) > 15 else channel_name)
                        
                except Exception as e:
                    user_id = getattr(user, 'id', 'N/A')
                    username = getattr(user, 'username', 'N/A')
                    
                    # Пропускаем логирование ошибок о лимитах API
                    if "A wait of" in str(e) and "seconds is required" in str(e):
                        wait_time = int(str(e).split("A wait of ")[1].split(" seconds")[0])
                        logger.warning(f"Достигнут лимит запросов. Ожидание {wait_time} секунд...")
                        # await asyncio.sleep(wait_time)
                        continue
                    
                    # Для других ошибок логируем только первые 10 символов ID
                    error_id = str(user_id)[:10] + '...' if len(str(user_id)) > 10 else user_id
                    logger.error(f"Ошибка при обработке пользователя {username} (ID: {error_id}): {str(e)[:100]}...")
                    
                    if pbar is not None:
                        pbar.update(1)
                        
                    # Добавляем дополнительную задержку после ошибки
                    # await asyncio.sleep(2)
                    continue
                    
            # Если дошли сюда, значит, все участники обработаны успешно
            if pbar is not None:
                pbar.close()
            return  # Выходим при успешном завершении
            
        except Exception as e:
            retry_count += 1
            if pbar is not None:
                pbar.close()
                pbar = None
                
            if retry_count > max_retries:
                logger.error(f"Превышено максимальное количество попыток ({max_retries}) при получении пользователей из канала: {e}")
                break
                
            wait_time = 1 * retry_count  # Минимальная задержка между попытками
            logger.warning(f"Повторная попытка {retry_count}/{max_retries} через {wait_time} сек...")
            await asyncio.sleep(wait_time)
            continue

async def get_personal_channel_entity(user_id: int) -> Optional[Channel]:
    """Получает сущность персонального канала пользователя."""
    try:
        # Получаем полную информацию о пользователе
        full_user = await get_full_user(user_id)
        if full_user:
            channel = await asyncio.wait_for(
                (await get_client())(GetChannelRequest(full_user.id)),
                timeout=30
            )
            return channel
        else:
            return None
    except Exception as e:
        logger.error(f"Ошибка при получении информации о пользователе {user_id}: {e}")
        return None




async def get_user_posts_in_channel(channel_id_or_username: str, user_id: int, limit: int = 1000) -> List[str]:
    """
    Получает посты пользователя в указанном канале.
    
    Args:
        channel_id_or_username: ID или username канала
        user_id: ID пользователя, чьи посты нужно получить
        limit: максимальное количество постов для получения
        
    Returns:
        Список текстов постов пользователя
    """
    client = await get_client()
    posts = []
    
    try:
        # Проверяем, что у нас есть доступ к каналу
        try:
            channel = await client.get_entity(channel_id_or_username)
            logger.info(f"Получаем посты пользователя {user_id} из канала {getattr(channel, 'title', 'N/A')} (ID: {getattr(channel, 'id', 'N/A')})")
        except Exception as e:
            logger.warning(f"Не удалось получить доступ к каналу {channel_id_or_username}: {e}")
            return []
        
        # Получаем посты с обработкой ошибок
        try:
            async for msg in client.iter_messages(channel_id_or_username, from_user=user_id, limit=limit):
                try:
                    if msg and hasattr(msg, 'text') and msg.text:
                        posts.append(msg.text)
                except Exception as e:
                    logger.warning(f"Ошибка при обработке сообщения: {e}")
                    continue
                    
        except Exception as e:
            logger.warning(f"Ошибка при получении сообщений из канала {channel_id_or_username}: {e}")
            return []
            
    except Exception as e:
        logger.error(f"Неизвестная ошибка при получении постов пользователя {user_id} из канала {channel_id_or_username}: {e}")
        return []
        
    logger.info(f"Получено {len(posts)} постов пользователя {user_id} из канала {channel_id_or_username}")
    return posts

    client = None
    try:
        client = await get_client()
        full_user = await client(GetFullUserRequest(user_id))
        pc_id = getattr(full_user.full_user, 'personal_channel_id', None)
        if pc_id:
            logger.debug(f"Найден персональный канал {pc_id} для пользователя {user_id}")
        return pc_id
    except Exception as e:
        logger.warning(f"Не удалось получить персональный канал для пользователя {user_id}: {e}")
        return None
    finally:
        if client and client.is_connected():
            await client.disconnect()
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

async def get_user_profile_summary(user_id: int, main_channel_id: Optional[str] = None) -> tuple:
    """
    Получает психологический портрет пользователя.
    
    Args:
        user_id: ID пользователя
        main_channel_id: ID основного канала (опционально)
    
    Returns:
        Кортеж (summary, photo_bytes, streams) или (None, None, []) в случае ошибки
    """
    client = None
    try:
        client = await get_bot_client()
        if not client or not client.is_connected():
            logger.error("Не удалось подключиться к клиенту Telegram")
            return None, None, []
            
        user = await client.get_entity(user_id)
        if not user:
            logger.error(f"Пользователь {user_id} не найден")
            return None, None, []
            
        logger.debug(f"Получение профиля пользователя {user_id} (username: {getattr(user, 'username', 'N/A')})")
        
        result = await get_full_psychological_summary(user_id, main_channel_id=main_channel_id, tg_user=user)
        if not result or len(result) != 3:
            logger.error(f"Некорректный формат результата для пользователя {user_id}")
            return None, None, []
            
        summary, photo_bytes, streams = result
        
        # Проверяем типы возвращаемых значений
        if not isinstance(summary, str) or not isinstance(streams, list):
            logger.error(f"Некорректные типы данных в результате для пользователя {user_id}")
            return None, None, []
            
        # Проверяем, что photo_bytes - это bytes или None
        if photo_bytes is not None and not isinstance(photo_bytes, (bytes, bytearray)):
            logger.warning(f"Некорректный тип photo_bytes для пользователя {user_id}, преобразуем в None")
            photo_bytes = None
            
        return summary, photo_bytes, streams
        
    except Exception as e:
        logger.error(f"Ошибка при получении профиля пользователя {user_id}: {e}", exc_info=True)
        return None, None, []
        
    finally:
        if client:
            try:
                # is_connected is a synchronous method, don't use await
                if client.is_connected():
                    await client.disconnect()
            except Exception as e:
                logger.warning(f"Ошибка при отключении клиента: {e}")

from relove_bot.db.models import GenderEnum
from relove_bot.services.prompts import PSYCHOLOGICAL_ANALYSIS_PROMPT

def _determine_gender_from_name(name: str) -> Optional[GenderEnum]:
    """
    Определяет пол по имени.
    
    Args:
        name: Имя для анализа
        
    Returns:
        GenderEnum или None, если не удалось определить
    """
    if not name:
        return None
        
    # Мужские окончания имен
    male_endings = ['й', 'н', 'т', 'р', 'с', 'в', 'д', 'л', 'г', 'к', 'м', 'п']
    # Женские окончания имен
    female_endings = ['а', 'я', 'ь', 'ия']
    
    # Проверяем окончание имени
    last_char = name[-1].lower()
    if last_char in male_endings:
        return GenderEnum.male
    elif last_char in female_endings:
        return GenderEnum.female
        
    return None

async def get_user_gender(user_id: int, client=None, tg_user=None) -> GenderEnum:
    """
    Определяет пол пользователя.
    
    Использует комбинированный подход:
    1. Анализ текстовых полей (имя, фамилия, логин, био)
    2. Анализ фотографии профиля (если доступна)
    
    Args:
        user_id: ID пользователя
        client: Существующий клиент Telethon (опционально)
        tg_user: Объект пользователя Telethon (опционально)
    
    Returns:
        Перечисление GenderEnum с полом (MALE, FEMALE, UNKNOWN)
    """
    logger.info(f"Определение пола для пользователя {user_id}...")
    
    try:
        if not client:
            client = await get_bot_client()
        
        # Если пользователь не передан, получаем его
        if tg_user is None:
            try:
                tg_user = await client.get_entity(user_id)
                logger.debug(f"Получены данные пользователя {user_id}")
            except Exception as e:
                logger.warning(f"Не удалось получить данные пользователя {user_id}: {e}")
                return None
        
        # Получаем информацию о пользователе
        first_name = getattr(tg_user, 'first_name', '')
        last_name = getattr(tg_user, 'last_name', '')
        username = getattr(tg_user, 'username', '')
        bio = getattr(tg_user, 'bio', '')
        
        logger.debug(f"Информация о пользователе {user_id}: имя='{first_name}', фамилия='{last_name}', username='{username}'")
        
        # Получаем фото профиля, если есть
        img_b64 = None
        last_photo_bytes = None
        try:
            async for photo in client.iter_profile_photos(user_id, limit=1):
                bioio = BytesIO()
                await client.download_media(photo, file=bioio)
                bioio.seek(0)
                photo_bytes = bioio.read()
                if photo_bytes:
                    logger.debug(f"Получено фото профиля пользователя {user_id} (размер: {len(photo_bytes)} байт)")
                break
        except Exception as e:
            logger.debug(f"Не удалось получить фото профиля пользователя {user_id}: {e}")
        
        # Используем новый сервис для определения пола
        from relove_bot.services.llm_service import llm_service
        
        try:
            gender = await llm_service.analyze_gender(
                first_name=first_name,
                last_name=last_name,
                username=username,
                bio=bio,
                photo_bytes=photo_bytes
            )
            
            logger.info(f"Определен пол пользователя {user_id}: {gender}")
            return gender
            
        except Exception as e:
            logger.error(f"Ошибка при определении пола пользователя {user_id}: {e}", exc_info=True)
            
    except Exception as e:
        logger.error(f"Критическая ошибка при определении пола пользователя {user_id}: {e}", exc_info=True)
    
    logger.info("Не удалось определить пол пользователя, используется значение по умолчанию: unknown")
    return GenderEnum.unknown

async def get_channel_participants_count(channel_id_or_username: str):
    """
    Получает общее количество участников в канале.
    
    Args:
        channel_id_or_username: ID или username канала
    
    Returns:
        Количество участников в канале
    """
    client = await get_bot_client()
    
    try:
        # Получаем информацию о канале
        channel = await client.get_entity(channel_id_or_username)
        
        # Получаем полную информацию о канале
        full_channel = await client(GetFullChannelRequest(channel))
        
        # Возвращаем количество участников
        return full_channel.full_chat.participants_count
    except Exception as e:
        logger.error(f"Ошибка при получении количества участников канала: {e}")
        raise

async def get_full_user(user_id: int, client=None):
    """
    Получает полную информацию о пользователе через GetFullUserRequest.
    
    Args:
        user_id: ID пользователя
        client: Существующий клиент Telethon (опционально)
    
    Returns:
        Объект User с информацией о пользователе или None, если пользователь не найден
    """
    max_retries = settings.llm_attempts
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            if not client or not client.is_connected():
                client = await get_client()
                if not client.is_connected():
                    await client.start()
                if not await client.is_user_authorized():
                    raise RuntimeError("User not authorized. Please log in first.")
            
            # Получаем полную информацию о пользователе
            full_user = await client(GetFullUserRequest(user_id))
            
            if not full_user or not full_user.users:
                logger.warning(f"Пользователь с ID {user_id} не найден")
                return None
                
            # Возвращаем объект User
            return full_user.users[0]
            
        except Exception as e:
            retry_count += 1
            if retry_count >= max_retries:
                if 'A wait of' in str(e) and 'seconds is required' in str(e):
                    wait_time = int(re.search(r'A wait of (\d+) seconds', str(e)).group(1))
                    hours, remainder = divmod(wait_time, 3600)
                    minutes, seconds = divmod(remainder, 60)
                    formatted_time = f"{hours} часов, {minutes} минут, {seconds} секунд"
                    logger.error(f"Необходимо подождать {formatted_time} перед повторной попыткой.")
                    await asyncio.sleep(wait_time)
                    continue
                logger.error(f"Ошибка при получении информации о пользователе {user_id} (попытка {retry_count}/{max_retries}): {e}")
                return None
                
            wait_time = 5 * retry_count
            logger.warning(f"Повторная попытка {retry_count}/{max_retries} через {wait_time} секунд...")
            # await asyncio.sleep(wait_time)
    
    return None

async def get_channel_users(channel_id_or_username: str, batch_size: int = 200, max_retries: int = 3, show_progress: bool = True):
    """
    Асинхронно получает всех пользователей из канала порциями.
    
    Args:
        channel_id_or_username: ID или username канала
        batch_size: размер пакета для получения участников (максимум 200)
        max_retries: максимальное количество повторных попыток при ошибках
        show_progress: показывать ли индикатор выполнения
    
    Yields:
        int: ID пользователей из канала
    """
    client = None
    retry_count = 0
    processed_count = 0
    total_users = 0
    pbar = None
    start_time = time.time()
    processed = 0
    
    while retry_count <= max_retries:
        try:
            if not client or not client.is_connected():
                client = await get_client()
                if not client.is_connected():
                    await client.start()
                if not await client.is_user_authorized():
                    raise RuntimeError("User not authorized. Please log in first.")
            
            # Получаем канал и общее количество участников
            channel = await client.get_entity(channel_id_or_username)
            if channel is None or not isinstance(channel, Channel):
                logger.error(f"Не удалось получить канал по идентификатору: {channel_id_or_username}")
                raise ValueError(f"Некорректный идентификатор канала: {channel_id_or_username}")
            channel_name = getattr(channel, 'title', str(getattr(channel, 'id', 'N/A')))
            
            # Получаем общее количество участников для прогресс-бара
            full_chat = await client(GetFullChannelRequest(channel=channel))
            total_users = getattr(full_chat.full_chat, 'participants_count', 0)
            
            # Инициализируем прогресс-бар
            if show_progress and total_users > 0:
                pbar = tqdm(
                    total=total_users,
                    desc=f"{channel_name[:20]}..." if len(channel_name) > 20 else channel_name,
                    unit="польз.",
                    bar_format='{l_bar}{bar:50}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]',
                    ncols=120,
                    ascii=' =',
                    miniters=1,
                    dynamic_ncols=True,
                    leave=False,
                    position=0
                )
            
            # Используем итератор участников канала с пагинацией
            async for user in client.iter_participants(channel, limit=None, aggressive=False):
                # Добавляем небольшую задержку между запросами
                # await asyncio.sleep(1)  # 1 секунда задержки между запросами
                try:
                    # Пропускаем ботов и удаленные аккаунты
                    if getattr(user, 'bot', False) or getattr(user, 'deleted', False):
                        if pbar is not None:
                            pbar.total -= 1
                            pbar.refresh()
                        continue
                        
                    logger.debug(f"Обработка пользователя: {getattr(user, 'username', '')} (ID: {getattr(user, 'id', 'N/A')})")
                    
                    # Если функция используется как генератор, возвращаем ID пользователя
                    user_id = user.id
                    yield user_id
                    
                    # Обновляем прогресс-бар для каждого обработанного пользователя
                    if show_progress and pbar is not None:
                        pbar.update(1)
                        processed += 1
                        pbar.set_postfix_str(f"Обработано: {processed}", refresh=True)
                    
                    # Добавляем небольшую задержку каждые batch_size пользователей
                    if processed % batch_size == 0:
                        # await asyncio.sleep(0.5)
                        # Обновляем описание каждые 100 пользователей
                        if processed % 100 == 0 and pbar is not None:
                            pbar.set_description(f"{channel_name[:15]}..." if len(channel_name) > 15 else channel_name)
                        
                except Exception as e:
                    user_id = getattr(user, 'id', 'N/A')
                    username = getattr(user, 'username', 'N/A')
                    
                    # Пропускаем логирование ошибок о лимитах API
                    if "A wait of" in str(e) and "seconds is required" in str(e):
                        wait_time = int(str(e).split("A wait of ")[1].split(" seconds")[0])
                        logger.warning(f"Достигнут лимит запросов. Ожидание {wait_time} секунд...")
                        # await asyncio.sleep(wait_time)
                        continue
                    
                    # Для других ошибок логируем только первые 10 символов ID
                    error_id = str(user_id)[:10] + '...' if len(str(user_id)) > 10 else user_id
                    logger.error(f"Ошибка при обработке пользователя {username} (ID: {error_id}): {str(e)[:100]}...")
                    
                    if pbar is not None:
                        pbar.update(1)
                        
                    # Добавляем дополнительную задержку после ошибки
                    # await asyncio.sleep(2)
                    continue
                    
            # Если дошли сюда, значит, все участники обработаны успешно
            if pbar is not None:
                pbar.close()
            return  # Выходим при успешном завершении
            
        except Exception as e:
            retry_count += 1
            if pbar is not None:
                pbar.close()
                pbar = None
                
            if retry_count > max_retries:
                logger.error(f"Превышено максимальное количество попыток ({max_retries}) при получении пользователей из канала: {e}")
                break
                
            wait_time = 5 * retry_count  # Экспоненциальная задержка
            logger.warning(f"Повторная попытка {retry_count}/{max_retries} через {wait_time} сек...")
            # await asyncio.sleep(wait_time)
            continue

async def get_personal_channel_entity(user_id: int) -> Optional[Channel]:
    """Получает сущность персонального канала пользователя."""
    try:
        # Получаем полную информацию о пользователе
        full_user = await get_full_user(user_id)
        if full_user:
            channel = await asyncio.wait_for(
                (await get_client())(GetChannelRequest(full_user.id)),
                timeout=30
            )
            return channel
        else:
            return None
    except Exception as e:
        logger.error(f"Ошибка при получении информации о пользователе {user_id}: {e}")
        return None




async def get_user_posts_in_channel(channel_id_or_username: str, user_id: int, limit: int = 1000) -> List[str]:
    """
    Получает посты пользователя в указанном канале.
    
    Args:
        channel_id_or_username: ID или username канала
        user_id: ID пользователя, чьи посты нужно получить
        limit: максимальное количество постов для получения
        
    Returns:
        Список текстов постов пользователя
    """
    client = await get_client()
    posts = []
    
    try:
        # Проверяем, что у нас есть доступ к каналу
        try:
            channel = await client.get_entity(channel_id_or_username)
            logger.info(f"Получаем посты пользователя {user_id} из канала {getattr(channel, 'title', 'N/A')} (ID: {getattr(channel, 'id', 'N/A')})")
        except Exception as e:
            logger.warning(f"Не удалось получить доступ к каналу {channel_id_or_username}: {e}")
            return []
        
        # Получаем посты с обработкой ошибок
        try:
            async for msg in client.iter_messages(channel_id_or_username, from_user=user_id, limit=limit):
                try:
                    if msg and hasattr(msg, 'text') and msg.text:
                        posts.append(msg.text)
                except Exception as e:
                    logger.warning(f"Ошибка при обработке сообщения: {e}")
                    continue
                    
        except Exception as e:
            logger.warning(f"Ошибка при получении сообщений из канала {channel_id_or_username}: {e}")
            return []
            
    except Exception as e:
        logger.error(f"Неизвестная ошибка при получении постов пользователя {user_id} из канала {channel_id_or_username}: {e}")
        return []
        
    logger.info(f"Получено {len(posts)} постов пользователя {user_id} из канала {channel_id_or_username}")
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