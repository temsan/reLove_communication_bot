"""
Модуль для работы с LLM (Large Language Model).
"""
from relove_bot.rag.llm import LLM

class LLMService:
    def __init__(self):
        self.llm = LLM()

    async def analyze_text(self, prompt: str, system_prompt: str = None, max_tokens: int = 64) -> str:
        result = await self.llm.analyze_content(text=prompt, system_prompt=system_prompt, max_tokens=max_tokens)
        return (result["summary"] or '').strip() if result else ''

    async def analyze_image(self, image_base64: str, prompt: str, max_tokens: int = 6) -> str:
        result = await self.llm.analyze_content(image_base64=image_base64, text=None, system_prompt=prompt, max_tokens=max_tokens)
        return (result["summary"] or '').strip() if result else ''
