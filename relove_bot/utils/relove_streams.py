import asyncio
import logging
import json
import re
from typing import List, Dict, Any, Optional
from relove_bot.services.llm_service import LLMService
from relove_bot.config import settings

logger = logging.getLogger(__name__)

async def detect_relove_streams(user, summary=None):
    """
    Определяет список пройденных потоков reLove для пользователя по summary или полям профиля.
    Возвращает список строк (названия потоков).
    """
    if not summary:
        summary = getattr(user, 'profile_summary', None) or ''
    prompt = f"Определи, какие потоки reLove прошёл пользователь на основе его профиля. Перечисли только названия потоков через запятую.\nПрофиль: {summary}"
    llm = LLMService()
    try:
        streams_str = await llm.analyze_text(prompt, system_prompt="Определи потоки пользователя", max_tokens=16)
        streams = [s.strip().capitalize() for s in streams_str.split(',') if s.strip()]
        logger.info(f"Обнаружены потоки для user {getattr(user, 'id', None)}: {streams}")
        return streams
    except Exception as e:
        logger.warning(f"Не удалось определить потоки reLove для пользователя {getattr(user, 'id', None)}: {e}")
        return []

async def detect_relove_streams_by_posts(posts: list) -> dict:
    """
    Определяет потоки reLove по постам пользователя.
    Возвращает словарь с двумя списками:
    - 'interest': потоки, которые упоминались или проявлен интерес
    - 'completed': потоки, которые пользователь явно проходил
    """
    if not posts:
        return {'interest': [], 'completed': []}
    
    try:
        posts_text = '\n'.join(str(p) for p in posts if p)
        
        # Получаем список доступных потоков из настроек
        valid_streams = settings.relove_streams
        
        # Создаем структурированный запрос с четким описанием формата вывода
        system_prompt = f"""Ты помощник, который анализирует посты пользователя и определяет его взаимодействие с потоками reLove. 
Отвечай ТОЛЬКО в формате JSON с полями:
- interest: список потоков, которые упоминались или к которым проявлен интерес
- completed: список потоков, которые пользователь явно проходил

Доступные потоки: {valid_streams}

Пример ответа:
{{
  "interest": ["{valid_streams[1]}"],
  "completed": ["{valid_streams[0]}"]
}}"""
        
        prompt = f"""Проанализируй посты пользователя и определи:
1. Какие потоки reLove упоминались или к ним проявлен интерес
2. Какие потоки пользователь явно проходил (есть признаки завершения/участия)

Посты пользователя:
{posts_text}

Ответ в формате JSON:"""
        
        llm = LLMService()
        
        # Получаем структурированный ответ
        result_str = await llm.analyze_text(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=128
        )
        
        # Обрабатываем ответ
        import json
        
        try:
            # Парсим JSON из ответа
            if isinstance(result_str, dict):
                result = result_str
            else:
                # Пытаемся извлечь JSON из текстового ответа
                import re
                json_match = re.search(r'\{.*\}', result_str, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group(0))
                else:
                    result = json.loads(result_str)
            
            # Нормализуем результаты
            def normalize_streams(streams):
                if not isinstance(streams, list):
                    if isinstance(streams, str):
                        streams = [s.strip() for s in streams.split(',')]
                    else:
                        streams = []
                return [s.strip().capitalize() for s in streams if s and isinstance(s, str) and s.strip()]
            
            interest = normalize_streams(result.get('interest', []))
            completed = normalize_streams(result.get('completed', []))
            
            # Фильтруем только допустимые потоки
            valid_streams = settings.relove_streams
            interest = [s for s in interest if s in valid_streams]
            completed = [s for s in completed if s in valid_streams]
            
            logger.info(f"Потоки по постам: интерес={interest}, прохождение={completed}")
            return {'interest': interest, 'completed': completed}
            
        except (json.JSONDecodeError, AttributeError) as e:
            logger.warning(f"Не удалось распарсить ответ от LLM: {e}. Ответ: {result_str}")
            return {'interest': [], 'completed': []}
            
    except Exception as e:
        logger.warning(f"Не удалось определить потоки reLove по постам: {e}", exc_info=True)
        return {'interest': [], 'completed': []}
