"""
Утилиты для определения пола пользователя.
"""
import base64
from io import BytesIO
from relove_bot.services.llm_service import LLMService
from relove_bot.services.telegram_service import get_client
from relove_bot.db.models import GenderEnum
import logging
from gender_guesser.detector import Detector

logger = logging.getLogger(__name__)

async def detect_gender(tg_user) -> str:
    """
    Определяет пол пользователя с помощью LLM на основе текстовых данных и фото профиля.
    Возвращает 'male' или 'female'.
    """
    # Проверяем, является ли пользователь ботом
    if getattr(tg_user, 'bot', False):
        logger.debug(f"Пользователь {getattr(tg_user, 'id', 'unknown')} является ботом, возвращаем female")
        return GenderEnum.female
        
    llm_service = LLMService()
    
    # Собираем всю доступную информацию о пользователе
    user_info = {
        'first_name': getattr(tg_user, 'first_name', ''),
        'last_name': getattr(tg_user, 'last_name', ''),
        'username': getattr(tg_user, 'username', ''),
        'bio': getattr(tg_user, 'about', '')
    }
    
    try:
        # Пробуем определить по текстовым данным
        gender = await llm_service._analyze_text_gender(
            first_name=user_info['first_name'],
            last_name=user_info['last_name'],
            username=user_info['username'],
            bio=user_info['bio']
        )
        if gender is not None:
            logger.debug(f"Пол определен по текстовым данным: {gender}")
            return gender
            
        # Если по тексту не определили, пробуем по фото
        client = await get_client()
        async for photo in client.iter_profile_photos(tg_user.id, limit=1):
            bioio = BytesIO()
            await client.download_media(photo, file=bioio)
            bioio.seek(0)
            photo_bytes = bioio.read()
            
            if photo_bytes:
                photo_base64 = base64.b64encode(photo_bytes).decode('utf-8')
                gender = await llm_service.analyze_photo_gender(photo_base64)
                if gender in ['male', 'female']:
                    logger.debug(f"Пол определен по фото: {gender}")
                    return GenderEnum[gender]
            break
            
    except Exception as e:
        logger.error(f"Ошибка при определении пола пользователя {getattr(tg_user, 'id', 'unknown')}: {e}", exc_info=True)
    
    logger.debug(f"Не удалось определить пол для пользователя {getattr(tg_user, 'id', 'unknown')}, используется значение по умолчанию: female")
    return GenderEnum.female
