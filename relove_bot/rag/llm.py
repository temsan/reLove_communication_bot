import asyncio
from openai import AsyncOpenAI
from relove_bot.config import settings

class LLM:
    def __init__(self):
        # Используем OpenRouter.ai в качестве base API
        self.client = AsyncOpenAI(
            api_key=settings.openai_api_key.get_secret_value(),
            base_url=settings.openai_api_base
        )

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
        response = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        result = {
            "summary": response.choices[0].message.content.strip() if response.choices else None,
            "usage": response.usage.model_dump() if response and hasattr(response, "usage") and response.usage else None,
            "finish_reason": response.choices[0].finish_reason if response.choices else None,
            "raw_response": response.model_dump() if hasattr(response, "model_dump") else str(response)
        }
        return result

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
