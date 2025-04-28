"""
Сервис для психологического анализа профиля пользователя.
"""
from relove_bot.services.llm_service import LLMService
from relove_bot.services.telegram_service import get_full_psychological_summary
from relove_bot.db.repository import UserRepository

class PsychAnalysisService:
    def __init__(self, session):
        self.repo = UserRepository(session)
        self.llm = LLMService()

    async def analyze_user_profile(self, user_id, main_channel_id, tg_user=None):
        """
        Анализирует профиль пользователя и сохраняет результат в поле psych_profile.
        """
        user = await self.repo.get_by_id(user_id)
        if not user:
            return None
        # Получаем summary через существующий сервис
        summary = await get_full_psychological_summary(user_id, main_channel_id, tg_user)
        user.psych_profile = summary
        await self.repo.session.commit()
        return summary
