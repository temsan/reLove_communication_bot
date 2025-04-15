import os
import openai
import asyncio

openai.api_key = os.getenv("OPENAI_API_KEY")

class LLM:
    async def generate_summary(self, text: str, model: str = "gpt-3.5-turbo", max_tokens: int = 256) -> str:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: openai.ChatCompletion.create(
                model=model,
                messages=[
                    {"role": "system", "content": "Сделай краткое информативное summary для следующего текста."},
                    {"role": "user", "content": text}
                ],
                max_tokens=max_tokens,
                temperature=0.4,
            )
        )
        return response.choices[0].message.content.strip()

    async def generate_rag_answer(self, context: str, question: str, model: str = "gpt-3.5-turbo", max_tokens: int = 256) -> str:
        loop = asyncio.get_event_loop()
        prompt = (
            f"Контекст пользователя:\n{context}\n\n"
            f"Вопрос пользователя: {question}\n"
            f"Ответь максимально полезно, учитывая только контекст."
        )
        response = await loop.run_in_executor(
            None,
            lambda: openai.ChatCompletion.create(
                model=model,
                messages=[
                    {"role": "system", "content": "Ты ассистент, отвечай только на основе контекста."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=0.4,
            )
        )
        return response.choices[0].message.content.strip()
