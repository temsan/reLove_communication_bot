import asyncio
import base64
import json
import logging
from openai import AsyncOpenAI
from ..utils.rate_limiter import llm_rate_limiter
from transformers import AutoTokenizer, AutoModelForCausalLM, AutoModelForSequenceClassification, pipeline, BitsAndBytesConfig
from huggingface_hub import login, InferenceClient
from relove_bot.config import settings
import torch
from relove_bot.services.prompts import (
    RAG_SUMMARY_PROMPT,
    RAG_ASSISTANT_PROMPT
)
from typing import Dict, Any
import openai

logger = logging.getLogger(__name__)

class LLM:
    async def generate_text(self, prompt: str, max_tokens: int = 500, temperature: float = 0.7) -> str:
        """
        Генерирует текст на основе промпта с использованием выбранного провайдера.
        
        Args:
            prompt: Текст промпта
            max_tokens: Максимальное количество токенов в ответе
            temperature: Температура генерации (от 0.0 до 1.0)
            
        Returns:
            Сгенерированный текст
        """
        if not prompt or not prompt.strip():
            return ""
            
        try:
            return await self._generate_with_openai(prompt, max_tokens, temperature)
        except Exception as e:
            logger.error(f"Ошибка при генерации текста: {e}")
            return ""
            
    async def _generate_with_openai(self, prompt: str, max_tokens: int, temperature: float) -> str:
        """Генерация текста с помощью OpenAI API."""
        try:
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            
            # Проверяем структуру ответа
            if not response or not hasattr(response, 'choices') or not response.choices:
                logger.error("Пустой ответ от OpenAI API")
                return ""
                
            # Получаем первый выбор
            choice = response.choices[0]
            if not hasattr(choice, 'message') or not choice.message:
                logger.error("Некорректная структура ответа от OpenAI API")
                return ""
                
            # Получаем контент сообщения
            content = choice.message.content
            if not content:
                logger.error("Пустой контент в ответе от OpenAI API")
                return ""
                
            return content
            
        except Exception as e:
            logger.error(f"Ошибка при генерации текста с OpenAI: {e}")
            return ""
            
    async def _generate_with_hf_api(self, prompt: str, max_tokens: int, temperature: float) -> str:
        """Генерация текста с помощью HuggingFace API."""
        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.client.text_generation(
                    prompt,
                    max_new_tokens=max_tokens,
                    temperature=temperature,
                    return_full_text=False
                )
            )
            return response
        except Exception as e:
            logger.error(f"Ошибка при генерации текста с HuggingFace API: {e}")
            return ""
            
    async def _generate_with_local(self, prompt: str, max_tokens: int, temperature: float) -> str:
        """Генерация текста с локальной моделью."""
        if not hasattr(self, 'model') or not self.model:
            raise RuntimeError("Локальная модель не загружена")
            
        try:
            inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)
            
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=max_tokens,
                    temperature=temperature,
                    do_sample=True,
                    pad_token_id=self.tokenizer.eos_token_id
                )
                
            # Декодируем только сгенерированную часть (исключая промпт)
            generated = outputs[0][inputs.input_ids.shape[-1]:]
            return self.tokenizer.decode(generated, skip_special_tokens=True)
        except Exception as e:
            logger.error(f"Ошибка при локальной генерации текста: {e}")
            return ""
            
    def __init__(self):
        self.model_name = settings.model_name
        self.client = None
        self.tokenizer = None
        self.model = None
        
        # OpenAI/OpenRouter/Groq API
        self.client = AsyncOpenAI(
            api_key=settings.llm_api_key.get_secret_value(),
            base_url=settings.llm_api_base,
            default_headers={
                "HTTP-Referer": "https://github.com/relove-bot",
                "X-Title": "reLove Bot",
                "Content-Type": "application/json"
            }
        )
        # Для HuggingFace и local — отдельная инициализация ниже при необходимости

    async def generate(self, prompt: str, max_tokens: int = 100) -> str:
        raise NotImplementedError("Метод generate поддерживается только для локального режима")

    @llm_rate_limiter
    async def _analyze_content_api(
        self,
        content: str,
        model: str = None,
        max_tokens: int = 512,
        temperature: float = 0.4,
        system_prompt: str = RAG_SUMMARY_PROMPT,
        timeout: int = 60
    ) -> dict:
        """
        Анализ контента через API.
        
        Args:
            content: Текст для анализа
            model: Имя модели для использования
            max_tokens: Максимальное количество токенов
            temperature: Температура генерации
            system_prompt: Системный промпт
            timeout: Таймаут в секундах
            
        Returns:
            dict: Результат анализа
        """
        try:
            response = await self.client.chat.completions.create(
                model=model or self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": content}
                ],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Ошибка при анализе контента: {e}")
            return ""

    async def analyze_content(
        self,
        content: str,
        model: str = None,
        max_tokens: int = 512,
        temperature: float = 0.4,
        system_prompt: str = RAG_SUMMARY_PROMPT,
        timeout: int = 60
    ) -> dict:
        """
        Анализ контента.
        
        Args:
            content: Текст для анализа
            model: Имя модели для использования
            max_tokens: Максимальное количество токенов
            temperature: Температура генерации
            system_prompt: Системный промпт
            timeout: Таймаут в секундах
            
        Returns:
            dict: Результат анализа
        """
        try:
            result = await self._analyze_content_api(
                content=content,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system_prompt=system_prompt,
                timeout=timeout
            )
            return result
        except Exception as e:
            logger.error(f"Ошибка при анализе контента: {e}")
            return {
                "summary": "",
                "usage": {"total_tokens": 0},
                "finish_reason": "error",
                "error": str(e)
            }

    async def _analyze_content_local(
        self,
        content: str,
        model: str = None,
        max_tokens: int = 512,
        temperature: float = 0.4,
        system_prompt: str = RAG_SUMMARY_PROMPT
    ) -> dict:
        """
        Анализ через локальную модель
        
        Args:
            content: Текст для анализа
            model: Имя модели для использования
            max_tokens: Максимальное количество токенов
            temperature: Температура генерации
            system_prompt: Системный промпт
            
        Returns:
            dict: Словарь с ключами:
                - summary (str): Текст ответа
                - usage (dict): Информация об использовании токенов
                - finish_reason (str): Причина завершения
        """
        if not content:
            return {
                'summary': '',
                'usage': {},
                'finish_reason': 'error',
                'error': 'Text is required for analysis'
            }

        try:
            # Формируем промпт
            prompt = f"""
            {system_prompt}

            Text:
            {content}
            """

            # Используем локальную модель
            if not hasattr(self, 'generator'):
                raise RuntimeError("Локальная модель не инициализирована")
                
            # Генерируем ответ
            response = self.generator(
                prompt,
                max_length=max_tokens,
                num_return_sequences=1,
                temperature=temperature,
                do_sample=True,
                top_p=0.9,
                top_k=50,
                return_full_text=False
            )
            
            # Извлекаем сгенерированный текст
            if isinstance(response, list) and len(response) > 0:
                generated_text = response[0].get('generated_text', '')
            else:
                generated_text = str(response)
                
            return {
                'summary': generated_text.strip(),
                'usage': {},
                'finish_reason': 'stop',
                'raw_response': response
            }
            
        except Exception as e:
            logger.error(f"Ошибка при локальном анализе контента: {str(e)}", exc_info=True)
            return {
                'summary': '',
                'usage': {},
                'finish_reason': 'error',
                'error': str(e)
            }

    async def generate_summary(self, text: str, model: str = None, max_tokens: int = 256) -> str:
        """
        Генерирует краткое содержание текста.

        Args:
            text: Текст для суммаризации
            model: Модель для использования (если отличается от настройки по умолчанию)
            max_tokens: Максимальное количество токенов в ответе

        Returns:
            str: Сгенерированное краткое содержание или пустая строка в случае ошибки
        """
        if not text:
            logger.warning("Пустой текст для генерации краткого содержания")
            return ''
            
        try:
            result = await self.analyze_content(
                text=text,
                model=model,
                max_tokens=max_tokens,
                system_prompt="""
                Сгенерируй краткое содержание следующего текста.
                Сосредоточься на ключевых моментах и идеях.
                Будь краток и информативен.
                """
            )
            
            if not result:
                logger.warning("Пустой ответ от analyze_content")
                return ''
                
            # Обрабатываем разные форматы ответа
            if isinstance(result, dict):
                if 'summary' in result:
                    return result['summary'].strip()
                elif 'choices' in result and len(result['choices']) > 0:
                    return result['choices'][0].get('message', {}).get('content', '').strip()
                else:
                    logger.warning(f"Неожиданный формат ответа: {result}")
                    return ''
            elif isinstance(result, str):
                return result.strip()
            else:
                logger.warning(f"Неожиданный тип ответа: {type(result)}")
                return ''
                
        except Exception as e:
            logger.error(f"Ошибка при генерации краткого содержания: {str(e)}", exc_info=True)
            return ''

    async def generate_rag_answer(self, context: str, question: str, model: str = None, max_tokens: int = 256) -> str:
        """
        Генерирует ответ на вопрос на основе контекста.

        Args:
            context: Контекст для анализа
            question: Вопрос пользователя
            model: Модель для использования (если отличается от настройки по умолчанию)
            max_tokens: Максимальное количество токенов в ответе

        Returns:
            str: Сгенерированный ответ или пустая строка в случае ошибки
        """
        if not context or not question:
            logger.warning("Пустой контекст или вопрос для генерации ответа")
            return ''
            
        try:
            prompt = (
                f"Контекст пользователя:\n{context}\n\n"
                f"Вопрос пользователя: {question}\n"
                f"Ответь максимально полезно, учитывая только контекст."
            )
            
            result = await self.analyze_content(
                text=prompt,
                model=model,
                max_tokens=max_tokens,
                system_prompt="Ты ассистент, отвечай только на основе контекста."
            )
            
            if not result:
                logger.warning("Пустой ответ от analyze_content")
                return ''
                
            # Обрабатываем разные форматы ответа
            if isinstance(result, dict):
                if 'summary' in result:
                    return result['summary'].strip()
                elif 'choices' in result and len(result['choices']) > 0:
                    return result['choices'][0].get('message', {}).get('content', '').strip()
                else:
                    logger.warning(f"Неожиданный формат ответа: {result}")
                    return ''
            elif isinstance(result, str):
                return result.strip()
            else:
                logger.warning(f"Неожиданный тип ответа: {type(result)}")
                return ''
                
        except Exception as e:
            logger.error(f"Ошибка при генерации ответа: {str(e)}", exc_info=True)
            return ''

    async def get_assistant_response(
        self,
        query: str,
        context: str,
        system_prompt: str = RAG_ASSISTANT_PROMPT
    ) -> str:
        """
        Получает ответ ассистента на основе контекста.
        
        Args:
            query: Вопрос пользователя
            context: Контекст для ответа
            system_prompt: Системный промпт
            
        Returns:
            str: Ответ ассистента или пустая строка в случае ошибки
        """
        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Контекст:\n{context}\n\nВопрос: {query}"}
            ]
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=256
            )
            
            if not response.choices:
                return ''
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Ошибка при получении ответа ассистента: {e}", exc_info=True)
            return ''
