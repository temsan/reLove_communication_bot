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
            if self.provider == 'openai':
                return await self._generate_with_openai(prompt, max_tokens, temperature)
            elif self.provider == 'huggingface':
                return await self._generate_with_hf_api(prompt, max_tokens, temperature)
            elif self.provider == 'local':
                return await self._generate_with_local(prompt, max_tokens, temperature)
            else:
                raise ValueError(f"Unsupported provider: {self.provider}")
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
        self.provider = settings.model_provider
        self.model_name = settings.model_name
        self.client = None
        self.tokenizer = None
        self.model = None
        
        if self.provider == 'openai':
            # Используем OpenRouter.ai в качестве API
            self.client = AsyncOpenAI(
                api_key=settings.openai_api_key.get_secret_value(),
                base_url=settings.openai_api_base,
                default_headers={
                    "HTTP-Referer": "https://github.com/relove-bot",
                    "X-Title": "reLove Bot",
                    "Content-Type": "application/json"
                }
            )
        elif self.provider == 'huggingface':
            # Используем HuggingFace API
            try:
                hf_token = settings.hugging_face_token.get_secret_value()
                login(token=hf_token)
                self.client = InferenceClient(token=hf_token)
            except Exception as e:
                logger.error(f"Ошибка при инициализации HuggingFace: {e}")
                raise
        elif self.provider == 'local':
            # Используем локальную модель
            try:
                hf_token = settings.hugging_face_token.get_secret_value() if settings.hugging_face_token else None
            except AttributeError:
                hf_token = None

            # Загрузка токенизатора и модели
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name, token=hf_token)
            
            # Настройка параметров загрузки модели
            if torch.cuda.is_available():
                # Настройки для GPU
                self.model = AutoModelForCausalLM.from_pretrained(
                    self.model_name,
                    device_map="auto",
                    torch_dtype=torch.float16,
                    low_cpu_mem_usage=True,
                    token=hf_token
                )
                self.generator = pipeline(
                    "text-generation",
                    model=self.model,
                    tokenizer=self.tokenizer,
                    device=0  # Используем GPU
                )
            else:
                # Настройки для CPU
                self.model = AutoModelForCausalLM.from_pretrained(
                    self.model_name,
                    device_map=None,
                    torch_dtype=torch.float32,
                    token=hf_token
                )
                self.generator = pipeline(
                    "text-generation",
                    model=self.model,
                    tokenizer=self.tokenizer,
                    device=-1  # Используем CPU
                )
            self.client = None
        else:
            raise ValueError(f"Unknown model provider: {self.provider}")

    async def generate(self, prompt: str, max_tokens: int = 100) -> str:
        if self.provider == 'local':
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            data = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}]
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers=headers,
                    json=data
                ) as response:
                    result = await response.json()
                    return result["choices"][0]["message"]["content"]
        else:
            raise ValueError("Generate method is only supported for local provider")

    async def analyze_content(
        self,
        text: str = None,
        image_url: str = None,
        image_base64: str = None,
        model: str = None,
        max_tokens: int = 512,
        temperature: float = 0.4,
        system_prompt: str = RAG_SUMMARY_PROMPT,
        timeout: int = 60,
        user_info: dict = None
    ) -> dict:
        """
        Универсальный анализ: текст, изображение или оба сразу.
        
        Args:
            text: Текст для анализа
            image_url: URL изображения (если есть)
            image_base64: Изображение в формате base64 (если есть)
            model: Имя модели для использования (если отличается от настройки по умолчанию)
            max_tokens: Максимальное количество токенов в ответе
            temperature: Температура генерации (0-1)
            system_prompt: Системный промпт
            timeout: Таймаут в секундах
            
        Returns:
            dict: Словарь с ключами:
                - summary (str): Текст ответа
                - usage (dict): Информация об использовании токенов
                - finish_reason (str): Причина завершения
                - raw_response: Сырой ответ от API
                - error (str, optional): Сообщение об ошибке, если произошла ошибка
        """
        try:
            # Проверяем, что хотя бы один из параметров передан
            if not any([text, image_url, image_base64]):
                raise ValueError("Необходимо указать хотя бы один из параметров: text, image_url или image_base64")

            # Обрабатываем image_base64 в зависимости от его типа
            processed_image_base64 = None
            if image_base64:
                if isinstance(image_base64, bytes):
                    # Если пришли байты, кодируем в base64 строку
                    processed_image_base64 = base64.b64encode(image_base64).decode('utf-8')
                elif isinstance(image_base64, str):
                    # Если строка, проверяем на наличие префикса data:image/
                    if 'base64,' in image_base64:
                        processed_image_base64 = image_base64.split('base64,', 1)[1]
                    else:
                        processed_image_base64 = image_base64
                else:
                    logger.warning(f"Неподдерживаемый тип image_base64: {type(image_base64)}")

            # Сохраняем информацию о пользователе для использования в API
            if user_info:
                self.user_info = user_info
                
            # Выбираем метод анализа в зависимости от провайдера
            if self.provider == 'local':
                result = await self._analyze_content_local(
                    text=text,
                    system_prompt=system_prompt,
                    max_tokens=max_tokens
                )
            else:
                result = await self._analyze_content_api(
                    text=text,
                    image_url=image_url,
                    image_base64=processed_image_base64,
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system_prompt=system_prompt,
                    timeout=timeout
                )
            
            # Проверяем, что результат не пустой
            if not result or not isinstance(result, dict):
                error_msg = f"Получен пустой или некорректный ответ от модели: {result}"
                logger.error(error_msg)
                return {
                    'summary': '',
                    'usage': {},
                    'finish_reason': 'error',
                    'error': error_msg
                }
            
            # Логируем информацию об использовании токенов, если доступна
            if 'usage' in result and result['usage']:
                usage = result['usage']
                logger.debug(f"Использовано токенов: {usage.get('total_tokens', 'N/A')} "
                           f"(prompt: {usage.get('prompt_tokens', 'N/A')}, "
                           f"completion: {usage.get('completion_tokens', 'N/A')})")
            
            return result
            
        except Exception as e:
            error_msg = f"Ошибка при анализе контента: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            # Проверяем, есть ли дополнительные детали об ошибке
            error_details = str(e)
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                try:
                    error_data = e.response.json()
                    if 'error' in error_data and 'message' in error_data['error']:
                        error_details += f"\n{error_data['error']['message']}"
                    else:
                        error_details += f"\nResponse: {e.response.text}"
                except:
                    error_details += f"\nResponse: {e.response.text}"
            
            return {
                'summary': '',
                'usage': {},
                'finish_reason': 'error',
                'error': error_details
            }

    @llm_rate_limiter
    async def _analyze_content_api(
        self,
        text: str = None,
        image_url: str = None,
        image_base64: str = None,
        model: str = None,
        max_tokens: int = 512,
        temperature: float = 0.4,
        system_prompt: str = RAG_SUMMARY_PROMPT,
        timeout: int = 60
    ) -> dict:
        """
        Анализ через API (OpenAI или HuggingFace)
        
        Returns:
            dict: Словарь с ключами:
                - summary (str): Текст ответа
                - usage (dict): Информация об использовании токенов
                - finish_reason (str): Причина завершения
                - raw_response: Сырой ответ от API
        """
        try:
            messages = []
            
            # Добавляем системный промпт, если он задан
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            
            # Создаем контент для пользовательского сообщения
            content_parts = []
            
            # Добавляем текст, если он есть
            if text:
                content_parts.append({"type": "text", "text": text})
            
            # Добавляем информацию о пользователе в текст, если есть изображение
            user_info = []
            if hasattr(self, 'user_info'):
                if self.user_info.get('first_name'):
                    user_info.append(f"Имя: {self.user_info['first_name']}")
                if self.user_info.get('last_name'):
                    user_info.append(f"Фамилия: {self.user_info['last_name']}")
                if self.user_info.get('username'):
                    user_info.append(f"Логин: @{self.user_info['username']}")
            
            # Добавляем текст с информацией о пользователе, если нет другого текста, но есть изображение
            if not text and (image_url or image_base64):
                prompt_text = "Проанализируй фотографию пользователя"
                if user_info:
                    prompt_text += " " + ", ".join(user_info)
                content_parts.append({"type": "text", "text": prompt_text})
            
            # Добавляем изображение, если есть
            if image_base64:
                try:
                    # Убедимся, что image_base64 - строка и не содержит префикс data:image/...
                    if isinstance(image_base64, str):
                        # Проверяем, что строка не пустая
                        if not image_base64.strip():
                            logger.warning("Пустая строка image_base64")
                        else:
                            content_parts.append({
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_base64}"
                                }
                            })
                    else:
                        logger.warning(f"Неподдерживаемый тип image_base64: {type(image_base64)}")
                except Exception as e:
                    logger.error(f"Ошибка при обработке изображения: {str(e)}", exc_info=True)
                    raise ValueError(f"Ошибка обработки изображения: {str(e)}") from e
            elif image_url:
                content_parts.append({
                    "type": "image_url",
                    "image_url": {"url": image_url}
                })
            
            if not content_parts:
                raise ValueError("Необходимо указать text и/или image_url/image_base64 для анализа.")
            
            # Формируем сообщение с правильной структурой
            messages.append({
                "role": "user",
                "content": content_parts
            })
            model = model or self.model_name
            
            # Убедимся, что модель в правильном формате для OpenRouter
            if 'gpt-4' in model.lower() and not model.startswith('openai/'):
                model = f'openai/{model}'
            
            logger.debug(f"Отправка запроса к API с моделью: {model}")
            logger.debug(f"Сообщения: {messages}")
            
            try:
                # Добавляем таймаут для запроса
                response = await asyncio.wait_for(
                    self.client.chat.completions.create(
                        model=model,
                        messages=messages,
                        max_tokens=max_tokens,
                        temperature=temperature,
                    ),
                    timeout=timeout
                )
                
                # Проверяем, что ответ не пустой
                if not response:
                    raise ValueError("Пустой ответ от API")
                    
                # Преобразуем ответ в словарь, если это необходимо
                if hasattr(response, 'model_dump'):
                    response_dict = response.model_dump()
                elif hasattr(response, 'dict'):
                    response_dict = response.dict()
                else:
                    response_dict = dict(response)
                
            except asyncio.TimeoutError:
                error_msg = f"Превышено время ожидания ответа от API ({timeout} сек)"
                logger.error(error_msg)
                raise ValueError(error_msg)
                
            except Exception as e:
                logger.error(f"Ошибка при вызове API: {str(e)}", exc_info=True)
                
                # Проверяем, есть ли дополнительные детали об ошибке
                error_msg = str(e)
                if hasattr(e, 'response') and hasattr(e.response, 'text'):
                    try:
                        error_data = e.response.json()
                        if 'error' in error_data and 'message' in error_data['error']:
                            error_msg = error_data['error']['message']
                        else:
                            error_msg += f"\nResponse: {e.response.text}"
                    except Exception as json_err:
                        error_msg += f"\nResponse: {e.response.text}"
                
                raise ValueError(f"Ошибка API: {error_msg}") from e
                
            # Логируем полученный ответ для отладки
            logger.debug(f"Получен ответ от API: {response_dict}")
            
            # Извлекаем текст ответа с учетом разных форматов ответа
            content = ''
            finish_reason = 'stop'
            usage = {}
            
            # Обработка стандартного формата OpenAI
            if 'choices' in response_dict and response_dict['choices']:
                choice = response_dict['choices'][0]
                if isinstance(choice, dict):
                    if 'message' in choice:
                        message = choice['message']
                        if isinstance(message, dict) and 'content' in message:
                            content = message['content']
                        elif isinstance(message, str):
                            content = message
                    elif 'text' in choice:
                        content = choice['text']
                    finish_reason = choice.get('finish_reason', 'stop')
            
            # Обработка прямого ответа с текстом
            elif 'text' in response_dict:
                content = response_dict['text']
            
            # Извлекаем информацию об использовании токенов
            if 'usage' in response_dict and response_dict['usage']:
                usage = response_dict['usage']
            
            # Убираем лишние пробелы и переносы
            content = content.strip() if content else ''
            
            return {
                'summary': content,
                'usage': usage,
                'finish_reason': finish_reason,
                'raw_response': response_dict
            }
            
        except Exception as e:
            logger.error(f"Ошибка при анализе контента через API: {str(e)}", exc_info=True)
            return {
                'summary': '',
                'usage': {},
                'finish_reason': 'error',
                'error': str(e)
            }

    async def _analyze_content_local(
        self,
        text: str = None,
        system_prompt: str = RAG_SUMMARY_PROMPT,
        max_tokens: int = 512
    ) -> dict:
        """
        Анализ через локальную модель
        
        Args:
            text: Текст для анализа
            system_prompt: Системный промпт
            max_tokens: Максимальное количество токенов
            
        Returns:
            dict: Словарь с ключами:
                - summary (str): Текст ответа
                - usage (dict): Информация об использовании токенов
                - finish_reason (str): Причина завершения
        """
        if not text:
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
            {text}
            """

            # Используем локальную модель
            if not hasattr(self, 'generator'):
                raise RuntimeError("Локальная модель не инициализирована")
                
            # Генерируем ответ
            response = self.generator(
                prompt,
                max_length=max_tokens,
                num_return_sequences=1,
                temperature=0.7,
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
