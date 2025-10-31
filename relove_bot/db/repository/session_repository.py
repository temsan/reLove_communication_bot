"""
Репозиторий для работы с сессиями пользователей.
"""
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_
from relove_bot.db.models import UserSession

class SessionRepository:
    """Репозиторий для работы с UserSession"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create_session(
        self,
        user_id: int,
        session_type: str,
        state: Optional[str] = None
    ) -> UserSession:
        """Создаёт новую сессию"""
        # Деактивируем предыдущие активные сессии того же типа
        await self.deactivate_sessions(user_id, session_type)
        
        db_session = UserSession(
            user_id=user_id,
            session_type=session_type,
            state=state,
            conversation_history=[],
            is_active=True
        )
        self.session.add(db_session)
        await self.session.commit()
        await self.session.refresh(db_session)
        return db_session
    
    async def get_active_session(
        self,
        user_id: int,
        session_type: Optional[str] = None
    ) -> Optional[UserSession]:
        """Получает активную сессию пользователя"""
        query = select(UserSession).where(
            and_(
                UserSession.user_id == user_id,
                UserSession.is_active == True
            )
        )
        if session_type:
            query = query.where(UserSession.session_type == session_type)
        
        result = await self.session.execute(query.order_by(UserSession.created_at.desc()))
        return result.scalar_one_or_none()
    
    async def get_session_by_id(self, session_id: int) -> Optional[UserSession]:
        """Получает сессию по ID"""
        return await self.session.get(UserSession, session_id)
    
    async def update_session(
        self,
        session_id: int,
        conversation_history: Optional[List] = None,
        state: Optional[str] = None,
        identified_patterns: Optional[List[str]] = None,
        core_issue: Optional[str] = None,
        question_count: Optional[int] = None,
        metaphysical_profile: Optional[dict] = None,
        core_trauma: Optional[dict] = None,
        session_data: Optional[dict] = None
    ) -> Optional[UserSession]:
        """Обновляет сессию"""
        update_data = {}
        if conversation_history is not None:
            update_data['conversation_history'] = conversation_history
        if state is not None:
            update_data['state'] = state
        if identified_patterns is not None:
            update_data['identified_patterns'] = identified_patterns
        if core_issue is not None:
            update_data['core_issue'] = core_issue
        if question_count is not None:
            update_data['question_count'] = question_count
        if metaphysical_profile is not None:
            update_data['metaphysical_profile'] = metaphysical_profile
        if core_trauma is not None:
            update_data['core_trauma'] = core_trauma
        if session_data is not None:
            update_data['session_data'] = session_data
        
        if not update_data:
            return await self.get_session_by_id(session_id)
        
        stmt = (
            update(UserSession)
            .where(UserSession.id == session_id)
            .values(**update_data)
        )
        await self.session.execute(stmt)
        await self.session.commit()
        return await self.get_session_by_id(session_id)
    
    async def deactivate_sessions(
        self,
        user_id: int,
        session_type: Optional[str] = None
    ) -> int:
        """Деактивирует активные сессии пользователя"""
        from sqlalchemy import func
        
        query = update(UserSession).where(
            and_(
                UserSession.user_id == user_id,
                UserSession.is_active == True
            )
        )
        if session_type:
            query = query.where(UserSession.session_type == session_type)
        
        query = query.values(is_active=False)
        result = await self.session.execute(query)
        await self.session.commit()
        return result.rowcount
    
    async def complete_session(self, session_id: int) -> Optional[UserSession]:
        """Завершает сессию"""
        from datetime import datetime
        
        stmt = (
            update(UserSession)
            .where(UserSession.id == session_id)
            .values(
                is_active=False,
                completed_at=datetime.utcnow()
            )
        )
        await self.session.execute(stmt)
        await self.session.commit()
        return await self.get_session_by_id(session_id)
    
    async def get_user_sessions(
        self,
        user_id: int,
        session_type: Optional[str] = None,
        limit: Optional[int] = None,
        include_inactive: bool = False
    ) -> List[UserSession]:
        """Получает сессии пользователя"""
        query = select(UserSession).where(UserSession.user_id == user_id)
        
        if session_type:
            query = query.where(UserSession.session_type == session_type)
        
        if not include_inactive:
            query = query.where(UserSession.is_active == True)
        
        query = query.order_by(UserSession.created_at.desc())
        
        if limit:
            query = query.limit(limit)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())

