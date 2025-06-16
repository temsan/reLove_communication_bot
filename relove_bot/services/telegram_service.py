import asyncio
import base64
import logging
import os
import re
import sys
import time
import traceback
from typing import Optional, Any, Dict, List, Tuple, Union, AsyncGenerator, Set

from telethon import TelegramClient, events
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.functions.channels import GetParticipantRequest, GetParticipantsRequest, GetFullChannelRequest, GetChannelsRequest
from telethon.tl.types import (
    ChannelParticipantsSearch, Channel, Message, User, UserProfilePhoto, 
    User as TelegramUser, ChannelParticipantsRecent, ChannelParticipantsAdmins,
    ChannelParticipantsBots
)
from telethon.errors import ChatAdminRequiredError, ChannelPrivateError, UserNotParticipantError, FloodWaitError
from tqdm.asyncio import tqdm
from io import BytesIO

from pydantic import SecretStr
from relove_bot.config import settings
from relove_bot.utils.api_rate_limiter import APIRateLimiter
from relove_bot.db.models import GenderEnum
from relove_bot.services.prompts import (
    PSYCHOLOGICAL_ANALYSIS_PROMPT,
    PHOTO_ANALYSIS_PROMPT,
    GENDER_PHOTO_ANALYSIS_PROMPT
)
from relove_bot.utils.telegram_client import get_client
from relove_bot.utils.interests import get_user_streams, STREAMS
from relove_bot.services.llm_service import llm_service

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
    Гарантирует подключение и авторизацию.
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
    if not _client.is_connected():
        await _client.connect()
    if not await _client.is_user_authorized():
        raise RuntimeError("Telegram client is not authorized. Пожалуйста, выполните авторизацию через scripts/auth_telegram.py")
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

async def analyze_photo(self, photo_bytes: bytes, analysis_type: str = "gender") -> str:
    """
    Анализирует фотографию профиля пользователя.
    
    Args:
        photo_bytes: Байты фотографии
        analysis_type: Тип анализа ("gender" или "psychological")
        
    Returns:
        str: Результат анализа или пустая строка в случае ошибки
    """
    try:
        # Проверяем кэш
        cache_key = f"photo_analysis_{analysis_type}_{hash(photo_bytes)}"
        if cache_key in cache:
            logger.info(f"Используем кэшированный анализ фото")
            return cache[cache_key]
            
        # Конвертируем фото в base64
        img_b64 = base64.b64encode(photo_bytes).decode('utf-8')
        
        # Выбираем промпт в зависимости от типа анализа
        if analysis_type == "gender":
            system_prompt = GENDER_PHOTO_ANALYSIS_PROMPT
            max_tokens = 10
        else:  # psychological
            system_prompt = "Кратко опиши психологические черты пользователя по фото профиля."
            max_tokens = 128
            
        # Ждем, пока не будет превышен лимит
        await rate_limiter.wait_for_limit(f"llm_{settings.openai_api_key.get_secret_value()[:5]}")
            
        result = await llm_service.analyze_text(
            prompt="",
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            image_base64=img_b64
        )
        
        # Кэшируем результат
        cache[cache_key] = result
        logger.info(f"Кэширован результат анализа фото")
            
        return result
        
    except Exception as e:
        logger.error(f"Ошибка при анализе фото: {e}")
        return "Не удалось проанализировать фото"

async def analyze_message(self, message: str) -> str:
    """
    Анализирует сообщение пользователя.
    
    Args:
        message: Текст сообщения
        
    Returns:
        str: Результат анализа или пустая строка в случае ошибки
    """
    try:
        result = await self.llm.analyze_content(
            text=message,
            system_prompt=PSYCHOLOGICAL_ANALYSIS_PROMPT,
            max_tokens=64
        )
        
        if not result or 'error' in result:
            return ''
            
        return result.get('summary', '').strip()
        
    except Exception as e:
        logger.error(f"Ошибка при анализе сообщения: {e}", exc_info=True)
        return ''

async def openai_psychological_summary(text: str, image_url: str = None) -> str:
    """
    Отправляет текст и/или фото в LLM.analyze_content и возвращает психологический портрет пользователя
    в стиле "Безжалостное Зеркало Правды".
    """
    from . import prompts
    
    # Получаем промпт в стиле "Безжалостное Зеркало Правды"
    prompt = prompts._get_text_prompt(text)
    
    try:
        result = await llm_service.analyze_text(
            prompt=text,
            system_prompt=prompt,
            max_tokens=1024,  # Увеличиваем лимит токенов для более развернутого анализа
            image_url=image_url
        )
        return result
    except Exception as e:
        logging.error(f"Ошибка при генерации психологического профиля: {e}")
        return "Не удалось сгенерировать анализ. Пожалуйста, попробуйте позже."

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
                (await get_client())(GetFullChannelRequest(full_user.id)),
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

async def get_user_profile_summary(client: TelegramClient, user_id: int, user_username: str = None) -> Tuple[str, GenderEnum, List[str]]:
    """
    Получает и анализирует профиль пользователя.
    Возвращает кортеж (summary, gender, streams).
    """
    try:
        # Получаем информацию о пользователе
        user = await client.get_entity(user_id)
        if not user:
            logger.error(f"Не удалось получить информацию о пользователе {user_id}")
            return None, None, []

        # Собираем информацию из профиля
        bio = user.about if hasattr(user, 'about') and user.about else ""
        first_name = user.first_name if hasattr(user, 'first_name') and user.first_name else ""
        last_name = user.last_name if hasattr(user, 'last_name') and user.last_name else ""
        
        # Получаем последние посты пользователя
        posts_text = ""
        try:
            # Получаем посты из личных сообщений
            async for message in client.iter_messages(user, limit=10):
                if message.text:
                    posts_text += f"Сообщение: {message.text}\n"
            
            # Получаем посты из каналов, где пользователь активен
            if user_username:
                try:
                    async for dialog in client.iter_dialogs():
                        if dialog.is_channel or dialog.is_group:
                            try:
                                # Ищем сообщения, связанные с потоками
                                async for message in client.iter_messages(dialog.entity, from_user=user, limit=10):
                                    if message.text and any(stream.lower() in message.text.lower() for stream in ["женский", "мужской", "смешанный", "путь героя", "поток"]):
                                        posts_text += f"Пост в {dialog.name}: {message.text}\n"
                            except Exception as e:
                                logger.debug(f"Не удалось получить сообщения из {dialog.name}: {str(e)}")
                except Exception as e:
                    logger.warning(f"Ошибка при получении постов из каналов: {str(e)}")
        except Exception as e:
            logger.error(f"Ошибка при получении постов пользователя {user_id}: {str(e)}")

        # Формируем текст для анализа
        text_for_analysis = f"Имя: {first_name} {last_name}\n"
        if bio:
            text_for_analysis += f"О себе: {bio}\n"
        if posts_text:
            text_for_analysis += f"Высказывания:\n{posts_text}"

        # Генерируем summary
        summary = await openai_psychological_summary(text=text_for_analysis, image_url=None)
        if not summary or len(summary.strip()) < 10:
            logger.warning(f"Не удалось сгенерировать summary для пользователя {user_id}")
            return None, None, []

        # Определяем пол
        gender = await get_user_gender(summary)
        
        # Определяем потоки
        streams = await get_user_streams(summary)
        
        return summary, gender, streams

    except Exception as e:
        logger.error(f"Ошибка при получении профиля пользователя {user_id}: {str(e)}")
        return None, None, []

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
    return GenderEnum.female

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

async def get_full_user(user_id: int) -> Optional[User]:
    """Получает полную информацию о пользователе."""
    try:
        logger.info(f"[DEBUG] get_full_user: пытаюсь получить пользователя {user_id}")
        client = await get_client()
        
        try:
            logger.info(f"[DEBUG] get_full_user: запрашиваю entity для {user_id}")
            user = await client.get_entity(user_id)
            if not user:
                logger.error(f"[DEBUG] get_full_user: пользователь {user_id} не найден")
                return None
                
            # Получаем полную информацию о пользователе
            full_user = await client(GetFullUserRequest(user))
            if not full_user:
                logger.error(f"[DEBUG] get_full_user: не удалось получить полную информацию о пользователе {user_id}")
                return None
                
            # Возвращаем сам объект пользователя, а не UserFull
            return user
            
        except FloodWaitError as e:
            wait_time = e.seconds
            logger.warning(f"Достигнут лимит запросов. Ожидание {wait_time} секунд...")
            await asyncio.sleep(wait_time)
            return await get_full_user(user_id)  # Рекурсивный вызов после ожидания
            
    except Exception as e:
        logger.error(f"[DEBUG] get_full_user: ошибка при получении пользователя {user_id}: {e}")
        logger.error(str(e))
        logger.error(traceback.format_exc())
        return None

async def get_channel_users(channel_id_or_username: str, batch_size: int = 100, max_retries: int = 3, show_progress: bool = True):
    """Получает список пользователей канала с возможностью пакетной загрузки.
    
    Args:
        channel_id_or_username: ID или username канала
        batch_size: Количество пользователей в одной пачке
        max_retries: Максимальное количество попыток при ошибках
        show_progress: Показывать прогресс-бар
        
    Yields:
        int: ID пользователя
    """
    if not channel_id_or_username:
        logger.error("Ошибка: не указан channel_id_or_username")
        raise ValueError("Необходимо указать ID или username канала")
        
    client = None
    retry_count = 0
    processed = 0
    pbar = None
    channel_name = str(channel_id_or_username)
    
    # Список символов для поиска
    search_chars = (
        'abcdefghijklmnopqrstuvwxyz'  # английский алфавит
        'абвгдеёжзийклмнопрстуфхцчшщъыьэюя'  # русский алфавит
        '0123456789'  # цифры
    )
    
    while retry_count <= max_retries:
        try:
            # Инициализация клиента с проверкой подключения
            if client is None or not client.is_connected():
                client = await get_client()
                if not client.is_connected():
                    await client.start()
                if not await client.is_user_authorized():
                    raise RuntimeError("User not authorized. Please log in first.")
            
            # Получаем канал с обработкой ошибок
            try:
                channel = await client.get_entity(channel_id_or_username)
                if channel is None or not isinstance(channel, Channel):
                    error_msg = f"Некорректный идентификатор канала: {channel_id_or_username} (получен тип: {type(channel)})"
                    logger.error(error_msg)
                    raise ValueError(error_msg)
                
                channel_name = getattr(channel, 'title', 'Без названия')
                channel_id = getattr(channel, 'id', 'N/A')
                logger.info(f"Успешно получили сущность канала: {channel_name} (ID: {channel_id})")
                
            except Exception as e:
                error_msg = f"Ошибка при получении сущности канала {channel_id_or_username}: {e}"
                logger.error(error_msg)
                logger.error(f"Тип ошибки: {type(e).__name__}")
                logger.error(f"Полный traceback: {traceback.format_exc()}")
                raise RuntimeError(error_msg) from e
            
            # Получаем общее количество участников для прогресс-бара
            total_users = 0
            try:
                full_chat = await client(GetFullChannelRequest(channel=channel))
                total_users = getattr(full_chat.full_chat, 'participants_count', 0)
                logger.info(f"Всего участников в канале {channel_name}: {total_users}")
            except Exception as e:
                logger.warning(f"Не удалось получить количество участников: {e}")
                logger.warning("Будет отображаться только прогресс обработки")
            
            # Инициализируем прогресс-бар с упрощенным форматом
            if show_progress:
                try:
                    pbar = tqdm(
                        total=total_users if total_users > 0 else None,
                        desc=f"{channel_name[:20]}..." if len(channel_name) > 20 else channel_name,
                        unit="польз.",
                        bar_format='{l_bar}{bar:50}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]',
                        ncols=120,
                        ascii=' =',
                        miniters=1,
                        dynamic_ncols=True,
                        leave=False,
                        position=0
                    )
                    # Добавляем начальное сообщение о статусе
                    pbar.set_description(f"{pbar.desc} (сбор)")
                except Exception as e:
                    logger.error(f"Ошибка при инициализации прогресс-бара: {e}")
                    pbar = None
            
            # Обрабатываем пользователей порциями
            total_processed = 0
            current_batch = []
            consecutive_errors = 0
            max_consecutive_errors = 10
            
            try:
                # Используем GetParticipantsRequest для получения всех участников
                offset = 0
                limit = 200  # Максимальный размер одной выборки
                
                # Список фильтров для получения разных типов участников
                filters = [
                    ChannelParticipantsAdmins(),
                    ChannelParticipantsBots(),
                    ChannelParticipantsRecent()  # Недавние участники
                ]
                
                # Добавляем фильтры поиска по каждому символу
                for char in search_chars:
                    filters.append(ChannelParticipantsSearch(char))
                
                for filter_type in filters:
                    offset = 0  # Сбрасываем offset для каждого фильтра
                    
                    while True:
                        try:
                            # Проверяем подключение и переподключаемся при необходимости
                            if not client.is_connected():
                                logger.warning("Соединение потеряно. Переподключение...")
                                await client.connect()
                                if not await client.is_user_authorized():
                                    raise RuntimeError("User not authorized after reconnection")
                            
                            # Получаем участников с текущим фильтром
                            participants = await client(GetParticipantsRequest(
                                channel=channel,
                                filter=filter_type,
                                offset=offset,
                                limit=limit,
                                hash=0
                            ))
                            
                            if not participants or not hasattr(participants, 'users') or not participants.users:
                                break
                                
                            for user in participants.users:
                                try:
                                    # Проверяем, что у пользователя есть ID
                                    if not hasattr(user, 'id') or not user.id:
                                        continue
                                    
                                    # Добавляем пользователя в текущую пачку
                                    current_batch.append(user)
                                    total_processed += 1
                                    processed += 1
                                    
                                    # Обновляем прогресс-бар
                                    if pbar is not None:
                                        try:
                                            pbar.update(1)
                                            pbar.set_postfix_str(f"Обработано: {pbar.n}")
                                        except Exception as pb_error:
                                            logger.warning(f"Ошибка при обновлении прогресс-бара: {pb_error}")
                                    
                                    # Если набрали нужное количество пользователей, возвращаем их
                                    if len(current_batch) >= batch_size:
                                        for batch_user in current_batch:
                                            yield batch_user.id
                                        current_batch = []
                                        # Добавляем небольшую задержку между пачками
                                        await asyncio.sleep(0.5)  # Увеличиваем задержку до 500мс
                                        
                                except Exception as e:
                                    logger.warning(f"Ошибка при обработке пользователя: {e}")
                                    continue
                            
                            offset += len(participants.users)
                            if len(participants.users) < limit:
                                break
                                
                            # Добавляем задержку между запросами
                            await asyncio.sleep(0.5)  # Увеличиваем задержку до 500мс
                                
                        except Exception as e:
                            logger.error(f"Ошибка при получении участников: {e}")
                            retry_count += 1
                            if retry_count > max_retries:
                                break
                            await asyncio.sleep(1)  # Уменьшаем задержку до 1 секунды
                            continue
                
                # Обрабатываем оставшихся пользователей
                if current_batch:
                    for batch_user in current_batch:
                        yield batch_user.id
                
                logger.info(f"Все пользователи обработаны. Всего: {total_processed}")
                return
                
            except Exception as e:
                logger.error(f"Ошибка при получении пользователей: {e}")
                retry_count += 1
                if retry_count > max_retries:
                    logger.error(f"Достигнуто максимальное количество попыток ({max_retries}). Прерываем.")
                    break
                
                await asyncio.sleep(1)  # Уменьшаем задержку до 1 секунды
                logger.info(f"Повторная попытка {retry_count}/{max_retries}...")
            
            # Закрываем прогресс-бар после завершения
            if pbar is not None:
                pbar.close()
                
            logger.info(f"Обработка пользователей канала завершена. Всего обработано: {total_processed}")
            return
            
        except Exception as e:
            error_msg = str(e).lower()
            logger.error(f"Ошибка при итерации по пользователям: {e}", exc_info=True)
            
            if "a wait of" in error_msg and "seconds is required" in error_msg:
                try:
                    wait_match = re.search(r'a wait of (\d+) seconds', error_msg)
                    if wait_match:
                        wait_time = min(5, int(int(wait_match.group(1)) / 2))  # Ограничиваем время ожидания до 5 секунд
                        logger.warning(f"Достигнут лимит запросов. Ожидание {wait_time} секунд...")
                        if pbar is not None:
                            try:
                                pbar.set_description(f"{pbar.desc.split(' (')[0]} (ожидание {wait_time}с)")
                            except Exception:
                                pass
                        await asyncio.sleep(wait_time)
                        continue
                except Exception as wait_err:
                    logger.error(f"Ошибка при обработке времени ожидания: {wait_err}")
            
            retry_count += 1
            
            if retry_count > max_retries:
                error_msg = f"Превышено максимальное количество попыток ({max_retries}) при обработке канала {channel_name}"
                logger.error(error_msg)
                if pbar is not None:
                    try:
                        pbar.set_description(f"{pbar.desc.split(' (')[0]} (ошибка)")
                    except Exception:
                        pass
                break
            
            await asyncio.sleep(1)  # Уменьшаем задержку до 1 секунды
            logger.warning(f"Повторная попытка {retry_count}/{max_retries}...")
            
            if pbar is not None:
                try:
                    pbar.set_description(f"{pbar.desc.split(' (')[0]} (повтор {retry_count}/{max_retries})")
                except Exception:
                    pass
    
    error_msg = f"Не удалось обработать канал {channel_name} после {max_retries} попыток"
    logger.error(error_msg)
    
    if client is not None:
        try:
            if client.is_connected():
                await client.disconnect()
                logger.info("Соединение с Telegram успешно закрыто")
        except Exception as e:
            logger.error(f"Ошибка при отключении клиента: {e}")
        finally:
            client = None
    
    raise RuntimeError(f"{error_msg}. Обработано пользователей: {processed}")

async def get_personal_channel_posts(user_id: int) -> dict:
    """Получает посты из личного канала пользователя."""
    try:
        client = await get_client()
        full_user = await get_full_user(user_id)
        if full_user:
            try:
                channel = await client(GetFullChannelRequest(full_user.id))
                if channel:
                    posts = []
                    photo_summaries = []
                    async for message in client.iter_messages(channel, limit=100):
                        if message.text:
                            posts.append(message.text)
                        if message.photo:
                            try:
                                photo_bytes = await message.download_media(bytes)
                                if photo_bytes:
                                    photo_summaries.append(photo_bytes)
                            except Exception as e:
                                logger.warning(f"Не удалось загрузить фото: {e}")
                    return {"posts": posts, "photo_summaries": photo_summaries}
            except FloodWaitError as e:
                wait_time = e.seconds
                logger.warning(f"Достигнут лимит запросов. Ожидание {wait_time} секунд...")
                await asyncio.sleep(wait_time)
                return await get_personal_channel_posts(user_id)  # Рекурсивный вызов после ожидания
    except Exception as e:
        logger.warning(f"Не удалось получить посты из личного канала: {e}")
    return {"posts": [], "photo_summaries": []}

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

async def get_relove_channel_posts(limit: int = 50) -> List[Dict[str, Any]]:
    """
    Получает последние посты из канала reLove.
    
    Args:
        limit: Количество последних постов для получения
        
    Returns:
        List[Dict[str, Any]]: Список постов с их содержимым и метаданными
    """
    try:
        client = await get_client()
        channel = await client.get_entity("reloveinfo")
        
        posts = []
        async for message in client.iter_messages(channel, limit=limit):
            if message.text:  # Пропускаем посты без текста
                post = {
                    'id': message.id,
                    'date': message.date,
                    'text': message.text,
                    'views': message.views,
                    'forwards': message.forwards,
                    'reactions': message.reactions.count if message.reactions else 0
                }
                posts.append(post)
        
        return posts
    except Exception as e:
        logger.error(f"Ошибка при получении постов из канала reLove: {e}")
        return []

async def analyze_relove_channel_content() -> Dict[str, Any]:
    """
    Анализирует контент канала reLove для определения основных тем и концепций.
    
    Returns:
        Dict[str, Any]: Словарь с основными темами и концепциями
    """
    try:
        posts = await get_relove_channel_posts(limit=100)
        
        # Объединяем все тексты постов
        all_text = "\n".join(post['text'] for post in posts)
        
        # Анализируем контент с помощью LLM
        analysis_prompt = """
        Проанализируй контент канала reLove и определи:
        1. Основные темы и концепции
        2. Стиль и тон общения
        3. Ключевые термины и их значения
        4. Эмоциональный окрас контента
        5. Целевую аудиторию
        6. Основные ценности и принципы
        
        Представь результат в структурированном виде.
        """
        
        analysis = await llm_service.analyze_text(
            prompt=all_text,
            system_prompt=analysis_prompt,
            max_tokens=500
        )
        
        return {
            'posts_count': len(posts),
            'analysis': analysis,
            'sample_posts': posts[:5]  # Первые 5 постов для примера
        }
    except Exception as e:
        logger.error(f"Ошибка при анализе контента канала reLove: {e}")
        return {}