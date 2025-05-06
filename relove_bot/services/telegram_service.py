import asyncio
import base64
import logging
import os
import re
import sys
from typing import Optional, Any, Dict, List, Tuple, Union

from telethon import TelegramClient, events
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.functions.channels import GetParticipantRequest, GetParticipantsRequest, GetFullChannelRequest
from telethon.tl.types import ChannelParticipantsSearch, Channel, Message, User, UserProfilePhoto
from telethon.errors import ChatAdminRequiredError, ChannelPrivateError, UserNotParticipantError
from tqdm.asyncio import tqdm
from io import BytesIO

from pydantic import SecretStr
from relove_bot.config import settings
from relove_bot.rag.llm import LLM

API_ID = settings.tg_api_id
API_HASH = settings.tg_api_hash if not isinstance(settings.tg_api_hash, SecretStr) else settings.tg_api_hash.get_secret_value()
SESSION = settings.tg_session.get_secret_value() if isinstance(settings.tg_session, SecretStr) else settings.tg_session

_client = None

async def get_client():
    """
    Returns a Telegram client in user mode.
    Uses the session specified in settings.
    """
    global _client
    if _client is None:
        _client = TelegramClient(
            session=SESSION,
            api_id=int(API_ID),
            api_hash=str(API_HASH),
            device_model='reLove Bot',
            system_version='1.0',
            app_version='1.0',
            lang_code='en',
            system_lang_code='en',
        )
    return _client

async def get_bot_client():
    """
    Returns a Telegram client in user mode.
    Uses the same session as get_client() but ensures it's started.
    """
    global _client
    if _client is None:
        _client = await get_client()
    if not _client.is_connected():
        await _client.start()
    return _client

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
    max_llm_attempts = settings.llm_attempts
    for attempt in range(1, max_llm_attempts + 1):
        try:
            llm = LLM()
            try:
                result = await asyncio.wait_for(
                    llm.analyze_content(
                        text=llm_input,
                        image_base64=img_b64 if 'img_b64' in locals() else None,
                        system_prompt=(
                            "Ты — Зеркало Безжалостной Правды, непреклонный ИИ-психотерапевт, обученный судебно-психологическому анализу. "
                            "Твоя цель — не утешать, а выявлять и обнажать бессознательные паттерны, защитные механизмы и саморазрушительное поведение. "
                            "Сочетай точность психологического анализа с прямотой радикальной честности.\n\n"
                            "ФАЗА 1 - ФОРЕНЗИЧЕСКИЙ АНАЛИЗ:\n"
                            "Проанализируй языковые паттерны, выбор слов, стиль общения и заявленные проблемы. Ищи:\n"
                            "* Повторяющиеся шаблоны мышления и логические ошибки\n"
                            "* Стратегии избегания эмоций и защитные механизмы\n"
                            "* Нарративы само-жертвования, замаскированные под интроспекцию\n"
                            "* Перфекционизм, угодничество и поиск одобрения\n"
                            "* Когнитивный диссонанс между заявленными ценностями и действиями\n"
                            "* Проекцию, рационализацию и другие защитные механизмы\n\n"
                            "ФАЗА 2 - ДОСТАВКА ЖЕСТКОЙ ПРАВДЫ:\n"
                            "На основе анализа дай прямую психологическую оценку, которая:\n"
                            "* Напрямую обращается к корневым психологическим паттернам\n"
                            "* Называет конкретные саморазрушительные модели поведения и их истоки\n"
                            "* Выявляет ловушки эго, которые удерживают пользователя на месте\n"
                            "* Связывает эти паттерны с практическими последствиями в жизни\n\n"
                            "Структура ответа:\n"
                            "1. ОТРАЖЕНИЕ В ЗЕРКАЛЕ: Основные наблюдаемые паттерны\n"
                            "2. АРХИТЕКТУРА ЗАЩИТ: Психологические структуры, поддерживающие эти паттерны\n"
                            "3. ПОСЛЕДСТВИЯ: Как эти паттерны влияют на жизнь и рост пользователя\n"
                            "4. ПУТЬ ПРЕОБРАЖЕНИЯ: Конкретные точки осознания для выхода из цикла\n\n"
                            "Ограничения:\n"
                            "- Не предлагай пустых утешений или духовного байпаса\n"
                            "- Не смягчай сложные истины\n"
                            "- Не ставь клинические диагнозы\n"
                            "- Сохраняй баланс между жестокой честностью и терапевтической целью\n"
                            "- Анализируй только предоставленные данные, без домыслов"
                        ),
                        max_tokens=512,
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
    client = None
    try:
        client = await get_bot_client()
        if not client or not client.is_connected():
            logger.error("Не удалось подключиться к клиенту Telegram")
            return None
            
        user = await client.get_entity(user_id)
        if user:
            return await get_full_psychological_summary(user_id, tg_user=user)
        return None
    except Exception as e:
        logger.error(f"Ошибка при получении профиля пользователя {user_id}: {e}")
        return None
    finally:
        if client:
            try:
                # is_connected is a synchronous method, don't use await
                if client.is_connected():
                    await client.disconnect()
            except Exception as e:
                logger.warning(f"Ошибка при отключении клиента: {e}")

from relove_bot.db.models import GenderEnum

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
        return GenderEnum.MALE
    elif last_char in female_endings:
        return GenderEnum.FEMALE
        
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
                return GenderEnum.UNKNOWN
        
        # Получаем информацию о пользователе
        first_name = getattr(tg_user, 'first_name', '')
        last_name = getattr(tg_user, 'last_name', '')
        username = getattr(tg_user, 'username', '')
        bio = getattr(tg_user, 'bio', '')
        
        logger.debug(f"Информация о пользователе {user_id}: имя='{first_name}', фамилия='{last_name}', username='{username}'")
        
        # Получаем фото профиля, если есть
        photo_bytes = None
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
    
    logger.info("Не удалось определить пол пользователя, используется значение по умолчанию: UNKNOWN")
    return GenderEnum.UNKNOWN

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
                logger.error(f"Ошибка при получении информации о пользователе {user_id} (попытка {retry_count}/{max_retries}): {e}")
                return None
                
            wait_time = 5 * retry_count
            logger.warning(f"Повторная попытка {retry_count}/{max_retries} через {wait_time} секунд...")
            await asyncio.sleep(wait_time)
    
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
    
    while retry_count <= max_retries:
        try:
            if not client or not client.is_connected():
                client = await get_client()  # Используем пользовательский клиент
                if not client.is_connected():
                    await client.start()
                if not await client.is_user_authorized():
                    raise RuntimeError("User not authorized. Please log in first.")
            
            # Получаем канал и общее количество участников
            try:
                channel = await client.get_entity(channel_id_or_username)
                logger.info(f"Получен канал: {getattr(channel, 'title', 'N/A')} (ID: {getattr(channel, 'id', 'N/A')})")
                
                # Получаем общее количество участников для прогресс-бара
                if show_progress:
                    try:
                        full_chat = await client(GetFullChannelRequest(channel=channel))
                        total_users = getattr(full_chat.full_chat, 'participants_count', 0)
                        logger.info(f"Всего участников в канале: {total_users}")
                        if total_users > 0:
                            pbar = tqdm(total=total_users, desc="Получение пользователей", unit="польз.")
                        else:
                            logger.warning("Не удалось определить общее количество участников, прогресс-бар отключен")
                    except Exception as e:
                        logger.warning(f"Не удалось получить количество участников: {e}, прогресс-бар отключен")
                        total_users = 0
                
            except Exception as e:
                logger.error(f"Ошибка при получении канала {channel_id_or_username}: {e}")
                raise
            
            # Используем итератор участников канала с пагинацией
            async for user in client.iter_participants(channel, limit=None, aggressive=True):
                try:
                    # Пропускаем ботов и удаленные аккаунты
                    if getattr(user, 'bot', False) or getattr(user, 'deleted', False):
                        if pbar is not None:
                            pbar.update(1)
                        continue
                        
                    user_id = getattr(user, 'id', None)
                    if user_id:
                        yield user_id
                        processed_count += 1
                        
                        # Обновляем прогресс-бар, если он активен
                        if pbar is not None:
                            pbar.update(1)
                            pbar.set_postfix({"Обработано": processed_count})
                        elif processed_count % 100 == 0:  # Логируем прогресс каждые 100 пользователей
                            logger.info(f"Обработано пользователей: {processed_count}")
                        
                        # Добавляем небольшую задержку каждые batch_size пользователей
                        if processed_count % batch_size == 0:
                            logger.info(f"Обработано {processed_count} пользователей...")
                            await asyncio.sleep(1)
                        
                except Exception as e:
                    logger.error(f"Ошибка при обработке пользователя: {e}")
                    if pbar is not None:
                        pbar.update(1)
                    continue
                    
            # Если дошли сюда, значит, все участники обработаны успешно
            if pbar is not None:
                pbar.close()
            logger.info(f"Всего обработано пользователей: {processed_count}")
            return  # Выходим при успешном завершении
            
        except Exception as e:
            retry_count += 1
            if pbar is not None:
                pbar.close()
                
            if retry_count > max_retries:
                logger.error(f"Превышено максимальное количество попыток ({max_retries}) при получении пользователей из канала: {e}", exc_info=True)
                break
                
            wait_time = 5 * retry_count  # Экспоненциальная задержка
            logger.warning(f"Попытка {retry_count}/{max_retries} не удалась. Повторная попытка через {wait_time} секунд...")
            await asyncio.sleep(wait_time)
            continue