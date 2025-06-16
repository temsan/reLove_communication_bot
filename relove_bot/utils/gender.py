"""
Утилиты для определения пола пользователя.
"""
import base64
from io import BytesIO
from relove_bot.services.llm_service import llm_service
from relove_bot.services.telegram_service import get_client
from relove_bot.db.models import GenderEnum
import logging
from gender_guesser.detector import Detector
import asyncio

logger = logging.getLogger(__name__)

async def detect_gender(tg_user) -> str:
    """
    Определяет пол пользователя через LLM
    """
    try:
        # Добавляем задержку перед запросом
        await asyncio.sleep(3)
        
        prompt = f"Определи пол пользователя по его профилю. В ответе используй только одно слово: 'male' или 'female'."
        logger.info(f"Отправляем запрос на определение пола для пользователя {tg_user.id}")
        result = await llm_service.analyze_text(prompt)
        
        # Пробуем определить пол из ответа
        if 'female' in result.lower():
            logger.info(f"Определен пол пользователя {tg_user.id}: female")
            return GenderEnum.female
        elif 'male' in result.lower():
            logger.info(f"Определен пол пользователя {tg_user.id}: male")
            return GenderEnum.male
            
        logger.warning(f"Не удалось определить пол пользователя {tg_user.id} из ответа: {result}")
        return GenderEnum.female
        
    except Exception as e:
        logger.error(f"Ошибка при определении пола пользователя {tg_user.id}: {e}")
        if 'Rate limit' in str(e) or 'exceeded' in str(e):
            logger.warning(f"Превышение лимита API при определении пола пользователя {tg_user.id}, увеличиваем задержку")
            await asyncio.sleep(30)
        return GenderEnum.female
