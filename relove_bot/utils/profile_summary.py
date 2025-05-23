"""
Утилиты для получения и анализа summary профиля пользователя.
"""

import logging
from typing import Optional
from relove_bot.services.llm_service import LLMService
from relove_bot.services.telegram_service import get_client, get_full_psychological_summary

logger = logging.getLogger(__name__)

async def get_user_profile_summary(user_id: int, main_channel_id: Optional[str] = None) -> Optional[str]:
    """
    Получает и анализирует summary профиля пользователя.
    
    Args:
        user_id: ID пользователя
        main_channel_id: ID основного канала для получения постов
        
    Returns:
        Строка с summary профиля или None в случае ошибки
    """
    try:
        client = await get_client()
        logger.debug(f'Attempting to get entity for user_id: {user_id}')
        entity = await client.get_entity(int(user_id))
        
        # Получаем полный психологический портрет
        summary, _, _ = await get_full_psychological_summary(user_id, main_channel_id, entity)
        
        return summary
    except Exception as e:
        logger.error(f"Ошибка при получении summary для пользователя {user_id}: {e}")
        return None
