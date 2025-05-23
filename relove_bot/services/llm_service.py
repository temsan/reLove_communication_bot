"""
Модуль для работы с LLM (Large Language Model).
"""
import asyncio
import base64
import logging
from typing import Optional, Dict, Any, List
from enum import Enum
import json
import aiohttp
from relove_bot.config import settings
import re

from relove_bot.rag.llm import LLM
from relove_bot.db.models import GenderEnum
from relove_bot.utils.api_rate_limiter import APIRateLimiter

logger = logging.getLogger(__name__)

class LLMService:
    def __init__(self):
        """Инициализирует сервис для работы с LLM"""
        self.api_key = settings.openai_api_key
        self.api_base = settings.openai_api_base
        self.model = settings.model_name
        self.attempts = settings.llm_attempts
        self.cache = {}  # Добавляем кэш
        self.rate_limiter = APIRateLimiter(max_requests_per_minute=20, max_requests_per_day=1000)
        
        # Инициализируем LLM
        from relove_bot.rag.llm import LLM
        self.llm = LLM()
        
        # Отладочный вывод настроек
        logger.info("=== Настройки LLMService ===")
        logger.info(f"API Key: {self.api_key.get_secret_value()[:5]}..." if self.api_key else "API Key: None")
        logger.info(f"API Base: {self.api_base}")
        logger.info(f"Модель: {self.model}")
        logger.info(f"Попыток: {self.attempts}")
        logger.info("==========================")
        
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
        photo_bytes: bytes = None
    ) -> GenderEnum:
        """
        Определяет пол пользователя на основе текстовых полей и фотографии.
        
        Приоритет определения:
        1. По текстовым полям (имя, фамилия, логин, био)
        2. По фотографии (если предоставлена)
        
        Args:
            first_name: Имя пользователя
            last_name: Фамилия пользователя
            username: Имя пользователя в Telegram
            bio: Описание профиля пользователя
            photo_bytes: Байты фотографии профиля
            
        Returns:
            GenderEnum: Определенный пол пользователя
        """
        # 1. Пытаемся определить по текстовым полям
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
        
        # Возвращаем женский пол по умолчанию, если не удалось определить
        return GenderEnum.female
        
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
        # Подготавливаем текст для анализа
        text_parts = []
        if first_name:
            text_parts.append(f"Имя: {first_name}")
        if last_name:
            text_parts.append(f"Фамилия: {last_name}")
        if username:
            text_parts.append(f"Логин: @{username}")
        if bio:
            text_parts.append(f"О себе: {bio}")
            
        if not text_parts:
            return None
            
        prompt = "\n".join(text_parts)
        
        system_prompt = """
        Ты эксперт по определению пола по текстовым данным. 
        Проанализируй предоставленную информацию о пользователе и определи его пол.
        
        Инструкции:
        1. Анализируй только предоставленные данные
        2. Учитывай имена, фамилии и их окончания
        3. Обращай внимание на гендерные маркеры в тексте
        4. Если пол неоднозначен, верни 'unknown'
        
        Верни только одно слово: 'male', 'female' или 'unknown'.
        """
        
        try:
            result = await self.llm.analyze_content(
                text=prompt,
                system_prompt=system_prompt,
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
            
            system_prompt = """
            Ты эксперт по анализу фотографий. Определи пол человека на фотографии.
            
            Инструкции:
            1. Проанализируй лицо на фотографии
            2. Определи пол (мужской/женский)
            3. Если не уверен, верни 'unknown'
            
            Верни только одно слово: 'male', 'female' или 'unknown'.
            """
            
            result = await self.llm.analyze_content(
                text="",
                image_base64=img_b64,
                system_prompt=system_prompt,
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
        Анализирует текст с помощью модели через OpenRouter
        
        Args:
            prompt: Текст для анализа
            system_prompt: Системный промпт
            max_tokens: Максимальное количество токенов в ответе
            user_info: Дополнительная информация о пользователе (имя, фамилия, логин)
            
        Returns:
            str: Ответ модели или пустая строка в случае ошибки
        """
        if not system_prompt:
            system_prompt = """
You are an expert in gender analysis. Your task is to determine the gender of a person based on their profile information.

Instructions:
1. Analyze the provided information (username, first name, last name, and profile summary)
2. Return ONLY one word: 'male' or 'female' based on your analysis

Important:
- Focus on clear indicators of gender
- Return only the requested word
- Do not provide explanations or additional text
"""
        
        try:
            result = await self.llm.analyze_content(
                text=prompt,
                system_prompt=system_prompt,
                max_tokens=max_tokens
            )
            
            if not result or 'error' in result:
                error_msg = result.get('error', 'Unknown error') if isinstance(result, dict) else 'Empty response'
                logger.error(f"Ошибка при анализе текста: {error_msg}")
                return ''
                
            return result.get('summary', '').strip()
            
        except Exception as e:
            logger.error(f"Исключение при анализе текста: {str(e)}", exc_info=True)
            return ''

    async def analyze_image(self, image_base64: str, prompt: str, max_tokens: int = 64, user_info: dict = None) -> str:
        """
        Анализирует изображение с помощью LLM
        
        Args:
            image_base64: Изображение в формате base64
            prompt: Промпт для анализа изображения
            max_tokens: Максимальное количество токенов в ответе
            user_info: Дополнительная информация о пользователе (имя, фамилия, логин)
            
        Returns:
            str: Результат анализа или пустая строка в случае ошибки
        """
        try:
            if not image_base64:
                logger.warning("Пустое изображение для анализа")
                return ''
                
            result = await self.llm.analyze_content(
                image_base64=image_base64,
                text=None,
                system_prompt=prompt,
                max_tokens=max_tokens,
                user_info=user_info
            )
            
            if not result or 'error' in result:
                error_msg = result.get('error', 'Unknown error') if isinstance(result, dict) else 'Empty response'
                logger.error(f"Ошибка при анализе изображения: {error_msg}")
                return ''
                
            return result.get('summary', '').strip()
            
        except Exception as e:
            logger.error(f"Исключение при анализе изображения: {str(e)}", exc_info=True)
            return ''
        
    async def analyze_photo_gender(self, image_base64: str, user_info: dict = None) -> str:
        """
        Анализирует пол на фотографии с помощью LLM.
        
        Args:
            image_base64: Фотография в формате base64
            user_info: Дополнительная информация о пользователе (имя, фамилия, логин)
            
        Returns:
            str: 'male', 'female' или 'unknown' если не удалось определить
        """
        system_prompt = """
        Ты эксперт по анализу фотографий. Определи пол человека на фотографии.
        Верни только одно слово: 'male', 'female' или 'unknown' если не можешь определить.
        """
        
        if not image_base64:
            logger.warning("Пустое изображение для анализа")
            return 'unknown'
        
        try:
            result = await self.llm.analyze_content(
                image_base64=image_base64,
                system_prompt=system_prompt,
                max_tokens=10,
                user_info=user_info
            )
            
            if not result or 'error' in result:
                error_msg = result.get('error', 'Empty response') if isinstance(result, dict) else 'Empty response'
                logger.error(f"Ошибка API при анализе фото: {error_msg}")
                return 'unknown'
            
            # Получаем текст ответа
            gender = None
            if isinstance(result, dict):
                # Проверяем разные возможные ключи с ответом
                if 'summary' in result and result['summary']:
                    gender = result['summary'].strip().lower()
                elif 'choices' in result and result['choices'] and len(result['choices']) > 0:
                    # Обработка формата OpenAI
                    choice = result['choices'][0]
                    if 'message' in choice and 'content' in choice['message']:
                        gender = choice['message']['content'].strip().lower()
                    elif 'text' in choice:
                        gender = choice['text'].strip().lower()
            
            if not gender:
                logger.warning(f"Некорректный формат ответа при анализе фото: {result}")
                return 'unknown'
            
            # Нормализуем ответ
            gender = gender.strip('\"\'').lower()
            if 'male' in gender:
                return 'male'
            elif 'female' in gender:
                return 'female'
            
            logger.warning(f"Не удалось определить пол из ответа: {gender}")
            return 'unknown'
            
        except Exception as e:
            logger.error(f"Ошибка при анализе фото: {str(e)}", exc_info=True)
            return 'unknown'

    async def get_user_gender(self, user_id: int) -> Optional[GenderEnum]:
        """Определяет пол пользователя через LLM"""
        try:
            llm = LLM()
            
            # Добавляем задержку перед запросом
            await asyncio.sleep(3)
            
            prompt = f"Определи пол пользователя по его ID {user_id}. В ответе используй только одно слово: 'male' или 'female'."
            logger.info(f"Отправляем запрос на определение пола для пользователя {user_id}")
            result = await llm.generate_text(prompt)
            
            # Пробуем определить пол из ответа
            if 'female' in result.lower():
                logger.info(f"Определен пол пользователя {user_id}: female")
                return GenderEnum.female
            elif 'male' in result.lower():
                logger.info(f"Определен пол пользователя {user_id}: male")
                return GenderEnum.male
                
            logger.warning(f"Не удалось определить пол пользователя {user_id} из ответа: {result}")
            return None
            
        except Exception as e:
            logger.error(f"Ошибка при определении пола пользователя {user_id}: {e}")
            if 'Rate limit' in str(e) or 'exceeded' in str(e):
                logger.warning(f"Превышение лимита API при определении пола пользователя {user_id}, увеличиваем задержку")
                await asyncio.sleep(30)
            return None

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
