"""
Утилиты для получения и анализа интересов пользователя.
"""

import logging
from typing import List, Optional, Dict
import openai

from relove_bot.config import settings
from relove_bot.services.llm_service import llm_service
from relove_bot.services.prompts import (
    PSYCHOLOGICAL_ANALYSIS_PROMPT,
    INTERESTS_ANALYSIS_PROMPT
)

logger = logging.getLogger(__name__)

# Инициализация OpenAI клиента
openai_client = openai.AsyncOpenAI(api_key=settings.openai_api_key.get_secret_value())

# Константы для потоков
STREAMS = [
    "Женский",
    "Мужской",
    "Смешанный",
    "Путь героя"
]

async def get_user_streams(summary: str) -> list:
    """
    Определяет потоки пользователя на основе его высказываний.
    Возвращает список потоков.
    """
    if not summary or len(summary.strip()) < 10:
        return []

    try:
        # Формируем промпт для определения потоков
        prompt = f"""
        Проанализируй высказывания человека и определи:
        1. Какие потоки он уже прошел (из списка: {', '.join(STREAMS)})
        2. К какому потоку у него есть интерес (из того же списка)
        
        Обрати внимание на:
        - Упоминания о прохождении потоков
        - Интерес к определенным темам и практикам
        - Стиль мышления и общения
        - Ценности и убеждения
        - Профессиональную деятельность
        
        Верни только список в формате:
        Пройденные потоки: [список]
        Интерес к потоку: [один поток]
        
        Текст для анализа:
        {summary}
        """

        # Используем глобальный экземпляр LLMService
        response_text = await llm_service.analyze_text(
            prompt=prompt,
            system_prompt="Ты - эксперт по анализу текста и определению психологических типов людей. Твоя задача - определить пройденные потоки и интерес к потокам на основе высказываний человека.",
            max_tokens=200
        )
        
        # Извлекаем пройденные потоки
        completed_streams = []
        if "Пройденные потоки:" in response_text:
            completed_part = response_text.split("Пройденные потоки:")[1].split("Интерес к потоку:")[0]
            completed_streams = [s.strip() for s in completed_part.strip('[]').split(',')]
            completed_streams = [s for s in completed_streams if s in STREAMS]
        
        # Извлекаем интерес к потоку
        interest_stream = None
        if "Интерес к потоку:" in response_text:
            interest_part = response_text.split("Интерес к потоку:")[1]
            interest_stream = interest_part.strip('[]').strip()
            if interest_stream not in STREAMS:
                interest_stream = None
        
        # Формируем итоговый список
        streams = completed_streams
        if interest_stream and interest_stream not in streams:
            streams.append(interest_stream)
        
        if not streams:
            logger.warning(f"Не удалось определить потоки из текста: {response_text}")
            return []
            
        return streams

    except Exception as e:
        logger.error(f"Ошибка при определении потоков: {str(e)}")
        return []

async def analyze_user_interests(user_id: int, posts: List[str]) -> Dict[str, float]:
    """
    Анализирует интересы пользователя на основе его постов.
    
    Args:
        user_id: ID пользователя
        posts: Список постов пользователя
        
    Returns:
        Dict[str, float]: Словарь с интересами и их весами
    """
    try:
        if not posts:
            return {}
            
        # Объединяем посты в один текст
        text = "\n\n".join(posts)
        
        # Анализируем текст
        result = await llm_service.analyze_text(
            text=text,
            system_prompt=INTERESTS_ANALYSIS_PROMPT,
            max_tokens=64
        )
        
        if not result:
            return {}
            
        # Парсим результат
        interests = {}
        for line in result.split('\n'):
            if ':' in line:
                interest, weight = line.split(':')
                try:
                    interests[interest.strip()] = float(weight.strip())
                except ValueError:
                    continue
                    
        return interests
        
    except Exception as e:
        logger.error(f"Ошибка при анализе интересов пользователя: {e}", exc_info=True)
        return {}
