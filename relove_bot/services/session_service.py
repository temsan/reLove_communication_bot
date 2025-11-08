"""
Сервис для работы с сессиями пользователей.
Обёртка над SessionRepository для удобной работы.
Включает персистентность сессий и интеграцию с User моделью.
"""
import logging
from datetime import datetime
from typing import Optional, Dict, List, Any
from sqlalchemy import select
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
    
    async def restore_active_sessions(self) -> Dict[int, UserSession]:
        """
        Восстанавливает активные сессии из БД при перезапуске бота.
        Возвращает словарь {user_id: UserSession}
        """
        try:
            result = await self.session.execute(
                select(UserSession).where(UserSession.is_active == True)
            )
            sessions = result.scalars().all()
            
            restored = {session.user_id: session for session in sessions}
            
            logger.info(
                f"Restored {len(restored)} active sessions from database"
            )
            
            return restored
            
        except Exception as e:
            logger.error(f"Error restoring active sessions: {e}")
            return {}
    
    async def update_user_from_session(
        self, 
        session_id: int
    ) -> Optional[User]:
        """
        Обновляет User модель на основе данных из завершённой сессии.
        Обновляет metaphysical_profile и last_journey_stage.
        """
        try:
            # Получаем сессию
            session = await self.repository.get_session_by_id(session_id)
            if not session:
                logger.warning(f"Session {session_id} not found")
                return None
            
            # Получаем пользователя
            result = await self.session.execute(
                select(User).where(User.id == session.user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                logger.warning(f"User {session.user_id} not found")
                return None
            
            # Обновляем metaphysical_profile если есть в сессии
            if session.metaphysical_profile:
                user.metaphysical_profile = session.metaphysical_profile
                logger.info(
                    f"Updated metaphysical_profile for user {user.id} "
                    f"from session {session_id}"
                )
            
            # Обновляем last_journey_stage если есть в session_data
            if session.session_data and 'journey_stage' in session.session_data:
                from relove_bot.db.models import JourneyStageEnum
                
                stage_value = session.session_data['journey_stage']
                
                # Преобразуем строку в enum если нужно
                if isinstance(stage_value, str):
                    try:
                        stage_enum = JourneyStageEnum[stage_value]
                        user.last_journey_stage = stage_enum
                        logger.info(
                            f"Updated last_journey_stage for user {user.id} "
                            f"to {stage_enum.name}"
                        )
                    except KeyError:
                        logger.warning(
                            f"Invalid journey stage value: {stage_value}"
                        )
                elif isinstance(stage_value, JourneyStageEnum):
                    user.last_journey_stage = stage_value
                    logger.info(
                        f"Updated last_journey_stage for user {user.id} "
                        f"to {stage_value.name}"
                    )
            
            await self.session.commit()
            await self.session.refresh(user)
            
            return user
            
        except Exception as e:
            logger.error(
                f"Error updating user from session {session_id}: {e}"
            )
            await self.session.rollback()
            return None
    
    async def complete_session_with_user_update(
        self, 
        session_id: int
    ) -> Optional[UserSession]:
        """
        Завершает сессию и обновляет User модель.
        Комбинирует complete_session и update_user_from_session.
        """
        try:
            # Сначала обновляем пользователя
            await self.update_user_from_session(session_id)
            
            # Затем завершаем сессию
            completed_session = await self.repository.complete_session(session_id)
            
            if completed_session:
                logger.info(
                    f"Completed session {session_id} for user "
                    f"{completed_session.user_id} with user update"
                )
            
            return completed_session
            
        except Exception as e:
            logger.error(
                f"Error completing session {session_id} with user update: {e}"
            )
            return None

