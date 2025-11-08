"""
Middleware для проверки активных сессий перед обработкой команд.
Проверяет наличие активных сессий и предлагает завершить текущую или продолжить.
"""
import logging
from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message
from sqlalchemy.ext.asyncio import AsyncSession

from relove_bot.services.session_service import SessionService

logger = logging.getLogger(__name__)


class SessionCheckMiddleware(BaseMiddleware):
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
        active_session = await session_service.get_active_session(user_id, session_type=None)
        
        if active_session:
            # Если уже есть активная сессия другого типа
            if active_session.session_type != session_type:
                logger.info(
                    f"User {user_id} has active {active_session.session_type} session, "
                    f"blocking {session_type}"
                )
                
                session_type_names = {
                    "provocative": "провокативная сессия с Наташей",
                    "diagnostic": "диагностика",
                    "journey": "путь героя"
                }
                
                current_name = session_type_names.get(
                    active_session.session_type, 
                    active_session.session_type
                )
                
                await event.answer(
                    f"⚠️ У тебя уже есть активная сессия: <b>{current_name}</b>\n\n"
                    "Заверши её командой /end_session или продолжай текущую сессию.\n\n"
                    "Если хочешь посмотреть сводку текущей сессии, используй /my_session_summary"
                )
                return  # Блокируем обработку
            else:
                # Если пытается начать сессию того же типа - передаём активную сессию
                logger.info(
                    f"User {user_id} already has active {session_type} session, "
                    f"passing it to handler"
                )
                data['active_session'] = active_session
        
        return await handler(event, data)
