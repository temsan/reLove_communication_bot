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
    
    async def update(self, user_id: int, data: dict):
        """Обновляет поля пользователя из словаря"""
        user = await self.get_user(user_id)
        if not user:
            return None
        
        for key, value in data.items():
            if hasattr(user, key):
                setattr(user, key, value)
        
        await self.session.commit()
        await self.session.refresh(user)
        return user
    
    async def get_by_id(self, user_id: int):
        """Алиас для get_user для совместимости"""
        return await self.get_user(user_id)
    
    async def get_users_by_criteria(
        self,
        is_active: Optional[bool] = None,
        has_started_journey: Optional[bool] = None,
        has_completed_journey: Optional[bool] = None,
        last_journey_stage: Optional[str] = None,
        streams: Optional[List[str]] = None,
        registered_before: Optional[datetime] = None,
        registered_after: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> List[User]:
        """Получает пользователей по критериям для рассылки"""
        from sqlalchemy import and_, or_
        
        query = select(User)
        conditions = []
        
        if is_active is not None:
            conditions.append(User.is_active == is_active)
        if has_started_journey is not None:
            conditions.append(User.has_started_journey == has_started_journey)
        if has_completed_journey is not None:
            conditions.append(User.has_completed_journey == has_completed_journey)
        if last_journey_stage:
            from relove_bot.db.models import JourneyStageEnum
            try:
                stage_enum = JourneyStageEnum(last_journey_stage)
                conditions.append(User.last_journey_stage == stage_enum)
            except ValueError:
                # Если этап не найден в enum, пропускаем
                pass
        if streams:
            # Ищем пользователей, у которых есть хотя бы один из указанных потоков
            from sqlalchemy import or_
            
            # Проверяем каждый поток отдельно через OR
            stream_conditions = []
            for stream in streams:
                # Проверяем наличие потока в массиве JSON
                stream_conditions.append(
                    User.streams.contains([stream])
                )
            if stream_conditions:
                conditions.append(or_(*stream_conditions))
        
        if registered_before:
            conditions.append(User.registration_date <= registered_before)
        if registered_after:
            conditions.append(User.registration_date >= registered_after)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        if limit:
            query = query.limit(limit)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())