"""
Модуль для работы с LLM (Large Language Model).
"""
import asyncio
import base64
import logging
import json
import re
from typing import Optional, Dict, Any, List
from enum import Enum
import aiohttp

from relove_bot.config import settings
from relove_bot.rag.llm import LLM
from relove_bot.db.models import GenderEnum
from relove_bot.utils.api_rate_limiter import APIRateLimiter
from relove_bot.services.prompts import (
    GENDER_TEXT_ANALYSIS_PROMPT,
    GENDER_PHOTO_ANALYSIS_PROMPT,
    PSYCHOLOGICAL_ANALYSIS_PROMPT,
    get_analysis_prompt
)

logger = logging.getLogger(__name__)

class LLMService:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LLMService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Инициализирует сервис для работы с LLM"""
        if self._initialized:
            return
            
        self.api_key = settings.openai_api_key
        self.api_base = settings.openai_api_base
        self.model = settings.model_name
        self.attempts = settings.llm_attempts
        self.cache = {}  # Добавляем кэш
        self.rate_limiter = APIRateLimiter(max_requests_per_minute=20, max_requests_per_day=1000)
        
        # Инициализируем LLM
        self.llm = LLM()
        
        # Отладочный вывод настроек
        logger.info("=== Настройки LLMService ===")
        logger.info(f"API Key: {self.api_key.get_secret_value()[:5]}..." if self.api_key else "API Key: None")
        logger.info(f"API Base: {self.api_base}")
        logger.info(f"Модель: {self.model}")
        logger.info(f"Попыток: {self.attempts}")
        logger.info("==========================")
        
        self._initialized = True
        
    async def generate_text(self, prompt: str, max_tokens: int = 1000, temperature: float = 0.7, model: str = None) -> str:
        """Генерирует текст через LLM"""
        try:
            # Проверяем кэш
            cache_key = f"prompt_{hash(prompt)}_{max_tokens}_{temperature}_{model or self.model}"
            if cache_key in self.cache:
                logger.info(f"Используем кэшированный ответ для: {prompt[:50]}...")
                return self.cache[cache_key]
            
            # Ждем, пока не будет превышен лимит
            await self.rate_limiter.wait_for_limit(self.api_key.get_secret_value())
            
            # Логируем детали запроса
            logger.info("=== Детали запроса к LLM ===")
            logger.info(f"URL: {self.api_base}/chat/completions")
            logger.info(f"Модель: {model or self.model}")
            logger.info(f"Размер промпта: {len(prompt)} символов")
            logger.info("==========================")
            
            # Отправляем запрос с повторными попытками
            max_retries = 3
            retry_delay = 5
            for attempt in range(max_retries):
                try:
                    payload = {
                        "model": model or self.model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": temperature,
                        "max_tokens": max_tokens
                    }
                    
                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            f"{self.api_base}/chat/completions",
                            headers={
                                "Authorization": f"Bearer {self.api_key.get_secret_value()}",
                                "Content-Type": "application/json",
                                "HTTP-Referer": "https://relove.com",
                                "X-Title": "reLove Bot"
                            },
                            json=payload,
                            timeout=30  # Увеличиваем таймаут
                        ) as response:
                            # Проверяем статус ответа
                            if response.status != 200:
                                error_msg = await response.json().get('error', {}).get('message', 'Unknown error')
                                if 'Rate limit' in error_msg:
                                    logger.warning(f"Превышение лимита API, попытка {attempt + 1}/{max_retries}")
                                    await asyncio.sleep(retry_delay * (attempt + 1))
                                    continue
                                raise ValueError(f"Ошибка API: {error_msg}")
                            
                            result = await response.json()
                            
                            # Проверяем наличие ответа
                            if not result or not result.get('choices'):
                                raise ValueError("Пустой ответ от API")
                            
                            # Кэшируем результат
                            self.cache[cache_key] = result['choices'][0]['message']['content']
                            return result['choices'][0]['message']['content']
                            
                except Exception as e:
                    if attempt == max_retries - 1:
                        logger.error(f"Ошибка при генерации текста после {max_retries} попыток: {str(e)}", exc_info=True)
                        raise
                    logger.warning(f"Ошибка при попытке {attempt + 1}/{max_retries}: {str(e)}")
                    await asyncio.sleep(retry_delay * (attempt + 1))
                    continue
            
        except Exception as e:
            logger.error(f"Ошибка при генерации текста: {str(e)}", exc_info=True)
            raise

    async def analyze_gender(
        self,
        first_name: str = None,
        last_name: str = None,
        username: str = None,
        bio: str = None,
        photo_bytes: bytes = None,
        user_id: int = None
    ) -> GenderEnum:
        """
        Определяет пол пользователя на основе текстовых полей и фотографии.
        
        Приоритет определения:
        1. По текстовым полям (имя, фамилия, логин, био)
        2. По фотографии (если предоставлена)
        3. По ID пользователя (если предоставлен)
        
        Args:
            first_name: Имя пользователя
            last_name: Фамилия пользователя
            username: Имя пользователя в Telegram
            bio: Описание профиля пользователя
            photo_bytes: Байты фотографии профиля
            user_id: ID пользователя в Telegram
            
        Returns:
            GenderEnum: Определенный пол пользователя
        """
        # 1. Пытаемся определить по текстовым полям
        if any([first_name, last_name, username, bio]):
            text_gender = await self._analyze_text_gender(
                first_name=first_name,
                last_name=last_name,
                username=username,
                bio=bio
            )
            if text_gender is not None:
                return text_gender
                
        # 2. Если не удалось определить по тексту и есть фото, пробуем по фото
        if photo_bytes:
            try:
                photo_gender = await self._analyze_photo_gender(photo_bytes)
                if photo_gender is not None:
                    return photo_gender
            except Exception as e:
                logger.error(f"Ошибка при анализе фото: {e}", exc_info=True)
                
        # 3. Если есть ID пользователя, пробуем определить по нему
        if user_id:
            try:
                # Добавляем задержку перед запросом
                await asyncio.sleep(3)
                
                prompt = f"Определи пол пользователя по его ID {user_id}. В ответе используй только одно слово: 'male' или 'female'."
                logger.info(f"Отправляем запрос на определение пола для пользователя {user_id}")
                result = await self.analyze_text(prompt)
                
                if 'female' in result.lower():
                    return GenderEnum.female
                elif 'male' in result.lower():
                    return GenderEnum.male
            except Exception as e:
                logger.error(f"Ошибка при определении пола по ID: {e}", exc_info=True)
        
        return None

    async def _analyze_text_gender(
        self,
        first_name: str = None,
        last_name: str = None,
        username: str = None,
        bio: str = None
    ) -> GenderEnum:
        """
        Анализирует текстовые поля для определения пола.
        
        Args:
            first_name: Имя пользователя
            last_name: Фамилия пользователя
            username: Имя пользователя в Telegram
            bio: Описание профиля пользователя
            
        Returns:
            GenderEnum: Определенный пол пользователя
        """
        try:
            # Формируем промпт для анализа
            prompt = f"""
            Имя: {first_name or ''}
            Фамилия: {last_name or ''}
            Логин: {username or ''}
            Описание: {bio or ''}
            
            Определи пол пользователя. В ответе используй только одно слово: 'male' или 'female'.
            """
            
            # Отправляем запрос к LLM
            result = await self.llm.analyze_content(
                text=prompt,
                system_prompt=GENDER_TEXT_ANALYSIS_PROMPT,
                max_tokens=10
            )
            
            if not result or 'error' in result:
                return None
                
            gender_text = result.get('summary', '').strip().lower()
            
            if 'male' in gender_text:
                return GenderEnum.male
            elif 'female' in gender_text:
                return GenderEnum.female
                
        except Exception as e:
            logger.error(f"Ошибка при анализе текстового пола: {e}", exc_info=True)
            
        return None
        
    async def _analyze_photo_gender(self, photo_bytes: bytes) -> GenderEnum:
        """
        Анализирует фотографию для определения пола.
        
        Args:
            photo_bytes: Байты фотографии
            
        Returns:
            GenderEnum: Определенный пол пользователя
        """
        try:
            # Конвертируем фото в base64
            img_b64 = base64.b64encode(photo_bytes).decode('utf-8')
            
            # Отправляем запрос к LLM
            result = await self.llm.analyze_content(
                text=img_b64,
                system_prompt=GENDER_PHOTO_ANALYSIS_PROMPT,
                max_tokens=10
            )
            
            if not result or 'error' in result:
                return None
                
            gender_text = result.get('summary', '').strip().lower()
            
            if 'male' in gender_text:
                return GenderEnum.male
            elif 'female' in gender_text:
                return GenderEnum.female
                
        except Exception as e:
            logger.error(f"Ошибка при анализе фото: {e}", exc_info=True)
            
        return None

    async def analyze_text(self, prompt: str, system_prompt: str = None, max_tokens: int = 64, user_info: dict = None) -> str:
        """
        Анализирует текст через LLM.
        
        Args:
            prompt: Текст для анализа
            system_prompt: Системный промпт
            max_tokens: Максимальное количество токенов
            user_info: Информация о пользователе
            
        Returns:
            str: Результат анализа
        """
        try:
            # Формируем промпт для анализа
            analysis_prompt = get_analysis_prompt(prompt, system_prompt)
            
            # Отправляем запрос к LLM
            result = await self.llm.analyze_content(
                text=analysis_prompt,
                system_prompt=system_prompt or PSYCHOLOGICAL_ANALYSIS_PROMPT,
                max_tokens=max_tokens
            )
            
            if not result or 'error' in result:
                return ''
                
            return result.get('summary', '').strip()
            
        except Exception as e:
            logger.error(f"Ошибка при анализе текста: {e}", exc_info=True)
            return ''

    async def analyze_image(self, image_base64: str, prompt: str, max_tokens: int = 64, user_info: dict = None) -> str:
        """
        Анализирует изображение через LLM.
        
        Args:
            image_base64: Изображение в формате base64
            prompt: Промпт для анализа
            max_tokens: Максимальное количество токенов
            user_info: Информация о пользователе
            
        Returns:
            str: Результат анализа
        """
        try:
            # Формируем промпт для анализа
            analysis_prompt = get_analysis_prompt(prompt, PSYCHOLOGICAL_ANALYSIS_PROMPT)
            
            # Отправляем запрос к LLM
            result = await self.llm.analyze_content(
                text=analysis_prompt,
                system_prompt=PSYCHOLOGICAL_ANALYSIS_PROMPT,
                max_tokens=max_tokens,
                image_base64=image_base64
            )
            
            if not result or 'error' in result:
                return ''
                
            return result.get('summary', '').strip()
            
        except Exception as e:
            logger.error(f"Ошибка при анализе изображения: {e}", exc_info=True)
            return ''

    async def get_user_interests(self, user_id: int) -> List[str]:
        """Получает интересы пользователя через LLM"""
        try:
            llm = LLM()
            
            # Добавляем задержку перед запросом
            await asyncio.sleep(3)
            
            prompt = f"Перечисли интересы пользователя {user_id} в формате списка. Используй только русские слова."
            logger.info(f"Отправляем запрос на получение интересов для пользователя {user_id}")
            result = await llm.generate_text(prompt)
            
            # Пробуем извлечь интересы из ответа
            interests = []
            if result:
                # Просто разбиваем по запятым и пробелам
                interests = [i.strip() for i in result.split(',') if i.strip()]
                logger.info(f"Получены интересы пользователя {user_id}: {interests}")
            else:
                logger.warning(f"Пустой ответ от LLM при получении интересов для пользователя {user_id}")
                
            return interests
            
        except Exception as e:
            logger.error(f"Ошибка при получении интересов пользователя {user_id}: {e}")
            if 'Rate limit' in str(e) or 'exceeded' in str(e):
                logger.warning(f"Превышение лимита API при получении интересов пользователя {user_id}, увеличиваем задержку")
                await asyncio.sleep(30)
            return []

    async def analyze(self, prompt: str, context: str = None) -> dict:
        """Анализирует контент через LLM"""
        try:
            if context:
                full_prompt = f"{prompt}\n\nКонтекст:\n{context}"
            else:
                full_prompt = prompt
            result = await self.llm.analyze_content(
                text=full_prompt,
                max_tokens=1000,
                temperature=0.7
            )
            if not result or 'error' in result:
                return {}
            return result
        except Exception as e:
            logger.error(f"Ошибка при анализе контента: {e}", exc_info=True)
            return {}

# Создаем глобальный экземпляр LLMService после определения класса
llm_service = LLMService()

def get_llm_service() -> LLMService:
    """Возвращает экземпляр LLMService"""
    return llm_service
