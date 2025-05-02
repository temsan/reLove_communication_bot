"""
Утилиты для определения пола пользователя.
"""
import base64
from io import BytesIO
from relove_bot.services.llm_service import LLMService
from relove_bot.services.telegram_service import get_client
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

    # 2. Проверяем фото через LLM
    if not photo_bytes:
        client = await get_client()
        async for photo in client.iter_profile_photos(user_id, limit=1):
            bioio = BytesIO()
            await client.download_media(photo, file=bioio)
            bioio.seek(0)
            photo_bytes = bioio.read()
            break

    if photo_bytes:
        llm_service = LLMService()
        try:
            result = await llm_service.analyze_photo_gender(photo_bytes)
            if result and result.get('gender') in ['male', 'female']:
                return result['gender']
        except Exception as e:
            logging.error(f"Ошибка при анализе фото: {e}")

    # 3. Если фото не помогло, проверяем био и посты
    try:
        bio = getattr(tg_user, 'about', '')
        if bio:
            llm_service = LLMService()
            result = await llm_service.analyze_text_gender(bio)
            if result and result.get('gender') in ['male', 'female']:
                return result['gender']
            guessed_gender = detector.get_gender(tg_user.first_name)
            if guessed_gender in ['male', 'female']:
                return guessed_gender
    except Exception as e:
        logger.error(f"[detect_gender] Ошибка LLM: {e}")
    return 'unknown'
