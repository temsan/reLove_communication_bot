"""
Асинхронный репозиторий для работы с пользователями.
"""
from relove_bot.db.models import User
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user(self, user_id: int):
        """Получает пользователя по ID"""
        return await self.session.get(User, user_id)

    async def update_summary(self, user_id: int, summary: str):
        user = await self.get_user(user_id)
        if user:
            user.profile_summary = summary
            await self.session.commit()
        return user

    async def get_all_users(self):
        """Получает всех пользователей из базы данных"""
        result = await self.session.execute(select(User))
        return result.scalars().all()

    async def update_gender(self, user_id: int, gender: str):
        """Обновляет пол пользователя"""
        user = await self.get_user(user_id)
        if user:
            user.gender = gender
            if not user.markers or not isinstance(user.markers, dict):
                user.markers = {}
            user.markers['gender'] = str(gender)
            await self.session.commit()
        return user
