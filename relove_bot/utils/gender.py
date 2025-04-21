"""
Утилиты для определения пола пользователя.
"""
import base64
from io import BytesIO
from relove_bot.services.llm_service import LLMService
from relove_bot.services.telegram_service import client
import logging
from gender_guesser.detector import Detector

logger = logging.getLogger(__name__)

async def detect_gender(tg_user) -> str:
    """
    Определяет пол пользователя только по данным Telegram entity (tg_user) и фото.
    Возвращает 'male', 'female' или 'unknown'.
    """
    llm_service = LLMService()
    detector = Detector()
    # Извлекаем все полезные поля из tg_user
    profile_info = []
    if hasattr(tg_user, 'first_name') and tg_user.first_name:
        profile_info.append(f"Имя: {tg_user.first_name}")
    if hasattr(tg_user, 'last_name') and tg_user.last_name:
        profile_info.append(f"Фамилия: {tg_user.last_name}")
    if hasattr(tg_user, 'username') and tg_user.username:
        profile_info.append(f"Username: {tg_user.username}")
    if hasattr(tg_user, 'bio') and tg_user.bio:
        profile_info.append(f"Bio: {tg_user.bio}")
    if hasattr(tg_user, 'about') and tg_user.about:
        profile_info.append(f"About: {tg_user.about}")
    if hasattr(tg_user, 'description') and tg_user.description:
        profile_info.append(f"Description: {tg_user.description}")
    prompt = (
        "Определи пол пользователя только по данным Telegram-профиля и фото. "
        "Ответь только одним словом: 'male', 'female' или 'unknown'.\n"
        + "\n".join(profile_info)
    )

    img_b64 = None
    user_id = getattr(tg_user, 'id', None)
    if user_id is not None:
        try:
            async for photo in client.iter_profile_photos(user_id, limit=1):
                bioio = BytesIO()
                await client.download_media(photo, file=bioio)
                bioio.seek(0)
                img_bytes = bioio.read()
                img_b64 = base64.b64encode(img_bytes).decode()
                break
        except Exception as e:
            logger.error(f"[detect_gender] Ошибка при получении фото: {e}")

    try:
        if img_b64:
            value = (await llm_service.analyze_image(img_b64, prompt, max_tokens=6)).lower()
        else:
            value = (await llm_service.analyze_text(prompt, system_prompt="Определи пол по Telegram-профилю и фото. Ответь 'male', 'female' или 'unknown' одним словом. Если не уверен, ответь 'unknown'.", max_tokens=6)).lower()
        if 'female' in value or 'жен' in value:
            return 'female'
        if 'male' in value or 'муж' in value:
            return 'male'
        # Fallback по имени
        if hasattr(tg_user, 'first_name') and tg_user.first_name:
            guessed_gender = detector.get_gender(tg_user.first_name)
            if guessed_gender in ['male', 'female']:
                return guessed_gender
    except Exception as e:
        logger.error(f"[detect_gender] Ошибка LLM: {e}")
    return 'unknown'
