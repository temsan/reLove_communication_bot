import logging
from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

logger = logging.getLogger(__name__)

class DbSessionMiddleware(BaseMiddleware):
    def __init__(self, session_pool: async_sessionmaker[AsyncSession]):
        super().__init__()
        self.session_pool = session_pool

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        if self.session_pool is None:
            logger.error("Database session pool is not initialized in middleware.")
            # В зависимости от логики, можно либо вызвать ошибку, либо пропустить
            # return await handler(event, data) # Пропустить, если БД не критична для всех хендлеров
            raise RuntimeError("Database session pool is not available.")

        async with self.session_pool() as session:
            data["session"] = session # Передаем сессию в data для доступа в хендлерах
            logger.debug("DB session provided to handler via middleware.")
            try:
                result = await handler(event, data)
            except Exception as e:
                logger.error(f"Rolling back session due to exception in handler: {e}", exc_info=True)
                await session.rollback()
                raise
            finally:
                # Коммит здесь не нужен, т.к. сессия закрывается контекстным менеджером
                # await session.commit() # Не нужно
                await session.close() # Закрываем для надежности, хотя менеджер должен это делать
                logger.debug("DB session closed after handler execution.")
            return result 