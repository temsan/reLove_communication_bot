"""
Утилиты для получения и анализа интересов пользователя.
"""

import logging
from typing import Optional, List
from relove_bot.services.llm_service import LLMService
from relove_bot.services.telegram_service import get_client, get_user_posts_in_channel

logger = logging.getLogger(__name__)

async def get_user_streams(user_id: int, main_channel_id: Optional[str] = None) -> list:
    """
    Возвращает пустой список интересов.
    
    Args:
        user_id: ID пользователя
        main_channel_id: ID основного канала (не используется)
        
    Returns:
        Пустой список, так как получение интересов временно отключено
    """
    return []
