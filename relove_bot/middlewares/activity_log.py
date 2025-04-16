import logging
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message
from sqlalchemy.ext.asyncio import AsyncSession
from relove_bot.db.models import UserActivityLog

logger = logging.getLogger(__name__)

class ActivityLogMiddleware(BaseMiddleware):
    def __init__(self):
        super().__init__()

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        session: AsyncSession = data.get("session")
        user_id = None
        chat_id = None
        activity_type = None
        details = {}
        # Определяем тип события и собираем данные
        if isinstance(event, Message):
            user_id = event.from_user.id if event.from_user else None
            chat_id = event.chat.id if event.chat else None
            if event.text:
                activity_type = "command" if event.text.startswith("/") else "message"
                details = {"text": event.text}
            elif event.photo:
                activity_type = "photo"
            else:
                activity_type = "other"
        # Можно добавить обработку CallbackQuery и других типов
        # Записываем лог только если есть user и сессия
        if session and user_id:
            try:
                log = UserActivityLog(
                    user_id=user_id,
                    chat_id=chat_id,
                    activity_type=activity_type or "unknown",
                    details=details
                )
                session.add(log)
                await session.commit()
                logger.debug(f"Activity log written: {log}")
            except Exception as e:
                logger.error(f"Failed to write activity log: {e}")
        return await handler(event, data)
