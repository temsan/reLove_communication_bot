"""Репозиторий для работы с пользователями"""
from typing import Optional, List
from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from relove_bot.db.models import User


class UserRepository:
    """Репозиторий для работы с пользователями"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_user(self, user_id: int) -> Optional[User]:
        """Получить пользователя по ID"""
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def get_all_users(self) -> List[User]:
        """Получить всех пользователей"""
        result = await self.session.execute(select(User))
        return list(result.scalars().all())
    
    async def create_user(self, user: User) -> User:
        """Создать нового пользователя"""
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user
    
    async def update_user(self, user_id: int, **kwargs) -> Optional[User]:
        """Обновить данные пользователя"""
        await self.session.execute(
            update(User).where(User.id == user_id).values(**kwargs)
        )
        await self.session.commit()
        return await self.get_user(user_id)
    
    async def delete_user(self, user_id: int) -> bool:
        """Удалить пользователя"""
        result = await self.session.execute(
            delete(User).where(User.id == user_id)
        )
        await self.session.commit()
        return result.rowcount > 0
    
    async def get_users_by_gender(self, gender: str) -> List[User]:
        """Получить пользователей по полу"""
        result = await self.session.execute(
            select(User).where(User.gender == gender)
        )
        return list(result.scalars().all())
    
    async def get_active_users(self) -> List[User]:
        """Получить активных пользователей"""
        result = await self.session.execute(
            select(User).where(User.is_active == True)
        )
        return list(result.scalars().all())
    
    async def count_users(self) -> int:
        """Подсчитать общее количество пользователей"""
        result = await self.session.execute(select(func.count(User.id)))
        return result.scalar_one()
