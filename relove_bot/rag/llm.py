import asyncio
from openai import AsyncOpenAI
from transformers import AutoTokenizer, AutoModelForCausalLM, AutoModelForSequenceClassification, pipeline, BitsAndBytesConfig
from huggingface_hub import login
from relove_bot.config import settings
import torch

class LLM:
    def __init__(self):
        self.provider = settings.model_provider
        self.model_name = settings.model_name
        self.model_path = settings.model_path
        
        if self.provider == 'openai':
            # Используем OpenRouter.ai в качестве base API
            self.client = AsyncOpenAI(
                api_key=settings.openai_api_key.get_secret_value(),
                base_url=settings.openai_api_base
            )
        elif self.provider == 'huggingface':
            # Используем HuggingFace API
            login(token=settings.hugging_face_token)
            self.client = None
        elif self.provider == 'local':
            # Инициализируем локальную модель
            self.model = "gemma-3-27b"
            try:
                hf_token = settings.hugging_face_token
            except AttributeError:
                hf_token = None

            # Загрузка токенизатора
            self.tokenizer = AutoTokenizer.from_pretrained(self.model, token=hf_token)
            
            # Настройка параметров загрузки модели
            if torch.cuda.is_available():
                # Настройки для GPU
                self.model = AutoModelForCausalLM.from_pretrained(
                    self.model,
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
                    self.model,
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
        system_prompt: str = "Сделай краткое информативное summary для следующего текста или изображения.",
        timeout: int = 60
    ) -> dict:
        """
        Универсальный анализ: текст, изображение или оба сразу.
        Возвращает структуру с summary, usage, finish_reason, raw_response.
        """
        if self.provider == 'local':
            return await self._analyze_content_local(text, system_prompt, max_tokens)
        else:
            return await self._analyze_content_api(text, image_url, image_base64, model, max_tokens, temperature, system_prompt, timeout)
        """
        Универсальный анализ: текст, изображение или оба сразу.
        Возвращает структуру с summary, usage, finish_reason, raw_response.
        """
        messages = [{"role": "system", "content": system_prompt}]
        user_content = []
        if text:
            user_content.append({"type": "text", "text": text})
        # Новый приоритет: image_base64 > image_url
        if image_base64:
            user_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{image_base64}"}
            })
        elif image_url:
            user_content.append({"type": "image_url", "image_url": {"url": image_url}})
        if user_content:
            messages.append({"role": "user", "content": user_content})
        else:
            raise ValueError("Необходимо указать text и/или image_url/image_base64 для анализа.")
        from relove_bot.config import settings
        model = model or settings.llm_summary_model
        from relove_bot.config import settings
        model = model or settings.llm_summary_model
    async def _analyze_content_api(
        self,
        text: str = None,
        image_url: str = None,
        image_base64: str = None,
        model: str = None,
        max_tokens: int = 512,
        temperature: float = 0.4,
        system_prompt: str = "Сделай краткое информативное summary для следующего текста или изображения.",
        timeout: int = 60
    ) -> dict:
        """
        Анализ через API (OpenAI или HuggingFace)
        """
        messages = [{"role": "system", "content": system_prompt}]
        user_content = []
        if text:
            user_content.append({"type": "text", "text": text})
        # Новый приоритет: image_base64 > image_url
        if image_base64:
            user_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{image_base64}"}
            })
        elif image_url:
            user_content.append({"type": "image_url", "image_url": {"url": image_url}})
        if user_content:
            messages.append({"role": "user", "content": user_content})
        else:
            raise ValueError("Необходимо указать text и/или image_url/image_base64 для анализа.")

        model = model or self.model_name
        response = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
    async def _analyze_content_local(
        self,
        text: str = None,
        system_prompt: str = "Сделай краткое информативное summary для следующего текста или изображения.",
        max_tokens: int = 512
    ) -> dict:
        """
        Анализ через модель Gemma через OpenRouter
        """
        if not text:
            raise ValueError("Text is required for analysis")

        # Формируем промпт
        prompt = f"""
        {system_prompt}

        Text:
        {text}
        """

        # Используем OpenRouter API
        openai = AsyncOpenAI(
            api_key=settings.openrouter_api_key.get_secret_value(),
            base_url=settings.openrouter_api_base
        )

        try:
            response = await openai.chat.completions.create(
                model="google/gemma-3-27b-it:free",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ],
                temperature=0.7,
                max_tokens=max_tokens
            )

            # Возвращаем результат
            return {
                "summary": response.choices[0].message.content,
                "usage": response.usage,
                "finish_reason": response.choices[0].finish_reason,
                "raw_response": response
            }
        except Exception as e:
            logger.error(f"Error in _analyze_content_local: {e}")
            raise

    async def generate_summary(self, text: str, model: str = None, max_tokens: int = 256) -> str:
        """
        Саммаризация только текста (GPT-4.1).
        Возвращает только summary (строка).
        """
        result = await self.analyze_content(text=text, model=model, max_tokens=max_tokens)
        return result["summary"]

    async def generate_rag_answer(self, context: str, question: str, model: str = "gpt-4.1-2025-04-14", max_tokens: int = 256) -> str:
        prompt = (
            f"Контекст пользователя:\n{context}\n\n"
            f"Вопрос пользователя: {question}\n"
            f"Ответь максимально полезно, учитывая только контекст."
        )
        result = await self.analyze_content(text=prompt, model=model, max_tokens=max_tokens,
                                            system_prompt="Ты ассистент, отвечай только на основе контекста.")
        return result["summary"]
