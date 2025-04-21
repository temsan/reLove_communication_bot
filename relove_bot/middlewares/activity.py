import logging
from typing import Callable, Dict, Any, Awaitable, Union
import datetime

from aiogram import BaseMiddleware
from typing import Optional
from aiogram.types import Message, CallbackQuery, User as TgUser, Chat as TgChat, TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import UserActivityLog, User, Chat
from ..db.database import get_db_session # Используем нашу функцию для получения сессии, если нужно

logger = logging.getLogger(__name__)

class ActivityLogMiddleware(BaseMiddleware):
    """Logs user activity (messages, commands, callbacks) to the database."""

    async def get_or_create_chat(self, session: AsyncSession, tg_chat: TgChat) -> Chat:
        """Helper to get or create Chat entry."""
        if not tg_chat:
            return None
        chat = await session.get(Chat, tg_chat.id)
        if not chat:
            logger.info(f"Creating new chat entry for ID {tg_chat.id} (type: {tg_chat.type})")
            chat = Chat(
                id=tg_chat.id,
                title=tg_chat.title,
                type=tg_chat.type,
                is_active=True
            )
            session.add(chat)
            try:
                await session.commit()
                await session.refresh(chat)
            except Exception as e:
                 logger.error(f"Failed to commit new chat {tg_chat.id}: {e}", exc_info=True)
                 await session.rollback()
                 return None # Не удалось создать/сохранить чат
        return chat

    async def log_activity(
        self,
        session: AsyncSession,
        user: TgUser,
        chat: Optional[TgChat],
        activity_type: str,
        details: Optional[Dict] = None
    ):
        if not user:
            logger.warning("Cannot log activity: User object is missing.")
            return

        # Убедимся, что пользователь существует в нашей БД (логика из common.py)
        # В реальном приложении лучше вынести get_or_create_user в отдельный сервис/репозиторий
        db_user = await session.get(User, user.id)
        if not db_user:
             logger.warning(f"User {user.id} not found in DB for activity logging. Skipping log.")
             # В идеале, пользователь должен быть создан до или во время этого middleware,
             # но на всякий случай пропускаем лог, если его нет.
             # Можно раскомментировать get_or_create_user ниже, если нужно создавать его здесь
             # from ..handlers.common import get_or_create_user # Осторожно с циклическими импортами!
             # db_user = await get_or_create_user(session, user)
             # if not db_user:
             #    logger.error(f"Failed to get/create user {user.id} during activity logging.")
             #    return
             return

        # Получаем или создаем чат, если он есть
        db_chat_id = None
        if chat:
            db_chat_obj = await self.get_or_create_chat(session, chat)
            if db_chat_obj:
                 db_chat_id = db_chat_obj.id
            else:
                logger.warning(f"Failed to get/create chat {chat.id} for activity log.")
                # Продолжаем без chat_id, если не удалось

        # Создаем запись лога
        log_entry = UserActivityLog(
            user_id=user.id,
            chat_id=db_chat_id,
            activity_type=activity_type,
            details=details,
            timestamp=datetime.datetime.now(datetime.timezone.utc) # Явно ставим время UTC
        )
        session.add(log_entry)
        try:
            await session.commit()
            logger.debug(f"Logged activity '{activity_type}' for user {user.id}")
        except Exception as e:
            logger.error(f"Failed to commit activity log for user {user.id}: {e}", exc_info=True)
            await session.rollback()

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: Union[Message, CallbackQuery],
        data: Dict[str, Any],
    ) -> Any:

        # Получаем сессию, созданную предыдущим middleware (DbSessionMiddleware)
        session: Optional[AsyncSession] = data.get("session")
        if not session:
            logger.error("DB session not found in data for ActivityLogMiddleware. Skipping log.")
            return await handler(event, data) # Продолжаем без логирования

        user: Optional[TgUser] = data.get('event_from_user')
        chat: Optional[TgChat] = data.get('event_chat')
        activity_type = event.event_type # 'message' или 'callback_query'
        details = {}

        if isinstance(event, Message):
            # Это может быть команда или обычное сообщение
            if event.text:
                if event.text.startswith('/'):
                    activity_type = "command"
                    details['command'] = event.text.split()[0]
                    details['text'] = event.text
                else:
                    activity_type = "message"
                    details['text_preview'] = event.text[:100] # Логируем только начало сообщения
            # Можно добавить логирование других типов сообщений (фото, документы...)
            details['message_id'] = event.message_id

        elif isinstance(event, CallbackQuery):
            activity_type = "callback_query"
            details['callback_data'] = event.data
            if event.message:
                 details['message_id'] = event.message.message_id

        # Выполняем логирование в фоне (не блокируя основной хендлер)
        # Важно: Используем ту же сессию!
        # asyncio.create_task(self.log_activity(session, user, chat, activity_type, details))
        # Проблема с create_task: сессия может закрыться до выполнения задачи.
        # Поэтому выполняем логирование до вызова основного хендлера.
        await self.log_activity(session, user, chat, activity_type, details)

        # Вызываем следующий middleware или хендлер
        return await handler(event, data) 