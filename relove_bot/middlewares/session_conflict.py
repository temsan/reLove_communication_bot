"""
Middleware для обработки конфликтов активных сессий.
Проверяет, не находится ли пользователь уже в другой сессии.
"""
import logging
from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message
from sqlalchemy.ext.asyncio import AsyncSession

from relove_bot.services.session_service import SessionService

logger = logging.getLogger(__name__)


class SessionConflictMiddleware(BaseMiddleware):
    """Middleware для проверки активных сессий перед началом новой"""
    
    # Команды, которые требуют проверки конфликтов
    SESSION_COMMANDS = {
        "natasha": "provocative",
        "diagnostic": "diagnostic",
        "start_journey": "journey",
        "start_diagnostic": "diagnostic"
    }
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        # Проверяем только сообщения
        if not isinstance(event, Message):
            return await handler(event, data)
        
        # Проверяем команды, которые начинают сессии
        if not event.text or not event.text.startswith('/'):
            return await handler(event, data)
        
        command = event.text.split()[0].replace('/', '').split('@')[0]
        
        if command not in self.SESSION_COMMANDS:
            return await handler(event, data)
        
        session_type = self.SESSION_COMMANDS[command]
        user_id = event.from_user.id
        db_session: AsyncSession = data.get("session")
        
        if not db_session:
            logger.warning(f"Session not found in data for user {user_id}")
            return await handler(event, data)
        
        session_service = SessionService(db_session)
        
        # Проверяем наличие других активных сессий
        active_sessions = await session_service.repository.get_active_session(
            user_id, session_type=None
        )
        
        if active_sessions:
            # Если уже есть активная сессия другого типа
            if active_sessions.session_type != session_type:
                logger.info(f"User {user_id} has active {active_sessions.session_type} session, blocking {session_type}")
                await event.answer(
                    f"⚠️ У тебя уже есть активная сессия ({active_sessions.session_type}).\n\n"
                    "Заверши её командой:\n"
                    "- /end_session (для провокативной сессии)\n"
                    "- /end_diagnostic (для диагностики)\n\n"
                    "Или продолжай текущую сессию."
                )
                return  # Блокируем обработку
        
        return await handler(event, data)

