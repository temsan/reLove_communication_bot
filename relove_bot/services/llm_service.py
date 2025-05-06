"""
Модуль для работы с LLM (Large Language Model).
"""
import asyncio
import base64
import logging
from typing import Optional, Dict, Any, List
from enum import Enum

from relove_bot.rag.llm import LLM
from relove_bot.db.models import GenderEnum

logger = logging.getLogger(__name__)

class LLMService:
    def __init__(self):
        self.llm = LLM()
        
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
        
        if text_gender != GenderEnum.UNKNOWN:
            return text_gender
            
        # 2. Если не удалось определить по тексту и есть фото, пробуем по фото
        if photo_bytes:
            try:
                photo_gender = await self._analyze_photo_gender(photo_bytes)
                if photo_gender != GenderEnum.UNKNOWN:
                    return photo_gender
            except Exception as e:
                logger.error(f"Ошибка при анализе фото: {e}", exc_info=True)
        
        return GenderEnum.UNKNOWN
        
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
            return GenderEnum.UNKNOWN
            
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
                return GenderEnum.UNKNOWN
                
            gender_text = result.get('summary', '').strip().lower()
            
            if 'male' in gender_text:
                return GenderEnum.MALE
            elif 'female' in gender_text:
                return GenderEnum.FEMALE
                
        except Exception as e:
            logger.error(f"Ошибка при анализе текстового пола: {e}", exc_info=True)
            
        return GenderEnum.UNKNOWN
        
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
                return GenderEnum.UNKNOWN
                
            gender_text = result.get('summary', '').strip().lower()
            
            if 'male' in gender_text:
                return GenderEnum.MALE
            elif 'female' in gender_text:
                return GenderEnum.FEMALE
                
        except Exception as e:
            logger.error(f"Ошибка при анализе фото: {e}", exc_info=True)
            
        return GenderEnum.UNKNOWN

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
2. Return ONLY one word: 'male' or 'female'
3. If you cannot determine the gender with high confidence, return 'unknown'

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
