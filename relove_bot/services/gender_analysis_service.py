"""
Сервис автоматического определения пола пользователя.
"""
from relove_bot.utils.gender import detect_gender
from relove_bot.db.repository import UserRepository
from relove_bot.services.telegram_service import client

class GenderAnalysisService:
    def __init__(self, session):
        self.repo = UserRepository(session)

    async def analyze_and_save_gender(self, user_id, tg_user=None):
        if tg_user is None:
            try:
                logger.debug(f'Attempting to get entity for user_id: {user_id}')
                tg_user = await client.get_entity(int(user_id))
            except Exception as e:
                # Можно логировать
                tg_user = None
        user = await self.repo.get_by_id(user_id)
        if not user:
            return None
        gender = await detect_gender(tg_user) if tg_user else 'unknown'
        user.gender = gender
        await self.repo.session.commit()
        return gender
