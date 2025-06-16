import asyncio
import logging
import json
import re
from typing import List, Dict, Any, Optional
from relove_bot.services.llm_service import llm_service
from relove_bot.config import settings
from relove_bot.services.prompts import (
    STREAMS_ANALYSIS_PROMPT,
    STREAMS_INTERACTION_PROMPT
)

logger = logging.getLogger(__name__)

async def detect_relove_streams(user, summary=None):
    """
    Определяет список пройденных потоков reLove для пользователя по summary или полям профиля.
    Возвращает список строк (названия потоков).
    """
    if not summary:
        summary = getattr(user, 'profile_summary', None) or ''
    prompt = f"Определи, какие потоки reLove прошёл пользователь на основе его профиля. Перечисли только названия потоков через запятую.\nПрофиль: {summary}"
    try:
        streams_str = await llm_service.analyze_text(prompt, system_prompt="Определи потоки пользователя", max_tokens=16)
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
        
        # Получаем структурированный ответ
        result_str = await llm_service.analyze_text(
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

async def get_user_streams(user_id: int) -> List[str]:
    """
    Получает потоки пользователя из базы данных.
    
    Args:
        user_id: ID пользователя
        
    Returns:
        List[str]: Список потоков пользователя
    """
    try:
        # Получаем профиль пользователя
        profile = await get_user_profile(user_id)
        if not profile:
            return []
            
        # Анализируем текстовые поля
        text_parts = []
        if profile.first_name:
            text_parts.append(f"Имя: {profile.first_name}")
        if profile.last_name:
            text_parts.append(f"Фамилия: {profile.last_name}")
        if profile.username:
            text_parts.append(f"Логин: @{profile.username}")
        if profile.bio:
            text_parts.append(f"О себе: {profile.bio}")
            
        if not text_parts:
            return []
            
        prompt = "\n".join(text_parts)
        streams_str = await llm_service.analyze_text(prompt, system_prompt=STREAMS_ANALYSIS_PROMPT, max_tokens=16)
        
        if not streams_str:
            return []
            
        # Разбиваем строку на потоки
        streams = [s.strip() for s in streams_str.split(',')]
        return [s for s in streams if s]
        
    except Exception as e:
        logger.error(f"Ошибка при получении потоков пользователя: {e}", exc_info=True)
        return []

async def get_user_interests(user_id: int) -> List[str]:
    """
    Получает интересы пользователя через LLM
    """
    try:
        # Добавляем задержку перед запросом
        await asyncio.sleep(3)
        
        prompt = f"Перечисли интересы пользователя {user_id} в формате списка. Используй только русские слова."
        logger.info(f"Отправляем запрос на получение интересов для пользователя {user_id}")
        result = await llm_service.analyze_text(prompt)
        
        # Пробуем распарсить результат
        if result:
            interests = [s.strip() for s in result.split(',')]
            return interests
            
        return []
        
    except Exception as e:
        logger.error(f"Ошибка при получении интересов пользователя {user_id}: {e}")
        if 'Rate limit' in str(e) or 'exceeded' in str(e):
            logger.warning(f"Превышение лимита API при получении интересов пользователя {user_id}, увеличиваем задержку")
            await asyncio.sleep(30)
        return []
