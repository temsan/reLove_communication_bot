"""
Модуль для работы с LLM (Large Language Model).
"""
from relove_bot.rag.llm import LLM

class LLMService:
    def __init__(self):
        print("Initializing LLMService...")
        self.llm = LLM()
        print("LLMService initialized")

    async def analyze_text(self, prompt: str, system_prompt: str = None, max_tokens: int = 64) -> str:
        """
        Анализирует текст с помощью модели Gemma через OpenRouter
        
        Args:
            prompt: Текст для анализа
            system_prompt: Системный промпт
            max_tokens: Максимальное количество токенов в ответе
            
        Returns:
            str: Ответ модели
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
        
        result = await self.llm.analyze_content(
            text=prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens
        )
        
        if result and "summary" in result:
            return result["summary"].strip()
        return ''

    async def analyze_image(self, image_base64: str, prompt: str, max_tokens: int = 6) -> str:
        result = await self.llm.analyze_content(image_base64=image_base64, text=None, system_prompt=prompt, max_tokens=max_tokens)
        return (result["summary"] or '').strip() if result else ''
