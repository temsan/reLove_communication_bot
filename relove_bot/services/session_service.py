"""
Сервис для работы с сессиями пользователей.
Обёртка над SessionRepository для удобной работы.
"""
import logging
from typing import Optional, Dict, List, Any
from sqlalchemy.ext.asyncio import AsyncSession
from relove_bot.db.repository.session_repository import SessionRepository
from relove_bot.db.models import UserSession, User

logger = logging.getLogger(__name__)


class SessionService:
    """Сервис для управления сессиями пользователей"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = SessionRepository(session)
    
    async def get_or_create_session(
        self,
        user_id: int,
        session_type: str,
        state: Optional[str] = None
    ) -> UserSession:
        """Получает активную сессию или создаёт новую"""
        active_session = await self.repository.get_active_session(user_id, session_type)
        if active_session:
            return active_session
        
        return await self.repository.create_session(user_id, session_type, state)
    
    async def add_message(
        self,
        session_id: int,
        role: str,
        content: str
    ) -> Optional[UserSession]:
        """Добавляет сообщение в историю сессии"""
        session = await self.repository.get_session_by_id(session_id)
        if not session:
            return None
        
        conversation_history = list(session.conversation_history) if session.conversation_history else []
        conversation_history.append({"role": role, "content": content})
        
        return await self.repository.update_session(
            session_id=session_id,
            conversation_history=conversation_history,
            question_count=session.question_count + (1 if role == "assistant" else 0)
        )
    
    async def update_session_data(
        self,
        session_id: int,
        identified_patterns: Optional[List[str]] = None,
        core_issue: Optional[str] = None,
        metaphysical_profile: Optional[Dict] = None,
        core_trauma: Optional[Dict] = None,
        state: Optional[str] = None,
        **kwargs
    ) -> Optional[UserSession]:
        """Обновляет данные сессии"""
        return await self.repository.update_session(
            session_id=session_id,
            identified_patterns=identified_patterns,
            core_issue=core_issue,
            metaphysical_profile=metaphysical_profile,
            core_trauma=core_trauma,
            state=state,
            session_data=kwargs if kwargs else None
        )
    
    async def complete_session(self, session_id: int) -> Optional[UserSession]:
        """Завершает сессию"""
        return await self.repository.complete_session(session_id)
    
    async def get_active_session(
        self,
        user_id: int,
        session_type: Optional[str] = None
    ) -> Optional[UserSession]:
        """Получает активную сессию"""
        return await self.repository.get_active_session(user_id, session_type)
    
    async def has_active_session(
        self,
        user_id: int,
        session_type: Optional[str] = None
    ) -> bool:
        """Проверяет наличие активной сессии"""
        session = await self.repository.get_active_session(user_id, session_type)
        return session is not None
    
    async def deactivate_all_sessions(
        self,
        user_id: int,
        session_type: Optional[str] = None
    ) -> int:
        """Деактивирует все активные сессии пользователя"""
        return await self.repository.deactivate_sessions(user_id, session_type)

