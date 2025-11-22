"""
Сервис сбора и анализа данных о пользователях для админки.
"""
from relove_bot.db.repository import UserRepository
from sqlalchemy import func

class AdminStatsService:
    def __init__(self, session):
        self.repo = UserRepository(session)

    async def get_gender_stats(self):
        result = await self.repo.session.execute(
            "SELECT gender, COUNT(*) FROM users GROUP BY gender"
        )
        return dict(result.fetchall())

    async def get_total_users(self):
        result = await self.repo.session.execute(
            "SELECT COUNT(*) FROM users"
        )
        return result.scalar()

    async def get_profiles_with_summary(self):
        result = await self.repo.session.execute(
            "SELECT COUNT(*) FROM users WHERE profile IS NOT NULL AND profile != ''"
        )
        return result.scalar()
