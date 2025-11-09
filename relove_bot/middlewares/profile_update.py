"""
Middleware для автоматического обновления профиля пользователя при каждом контакте.
Обновляет last_seen_date, сохраняет в UserActivityLog и запускает фоновое обновление профиля.
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from relove_bot.db.models import User, UserActivityLog

logger = logging.getLogger(__name__)


class ProfileUpdateMiddleware(BaseMiddleware):
    """Middleware для обновления профиля пользователя при каждом контакте"""
    
    def __init__(self):
        super().__init__()
        self._profile_update_tasks = {}  # Словарь для отслеживания фоновых задач
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        # Обрабатываем только сообщения и callback query
        if not isinstance(event, (Message, CallbackQuery)):
            return await handler(event, data)
        
        user_id = event.from_user.id if event.from_user else None
        if not user_id:
            return await handler(event, data)
        
        db_session: AsyncSession = data.get("session")
        if not db_session:
            logger.warning(f"DB session not found in data for user {user_id}")
            return await handler(event, data)
        
        try:
            # 1. Обновляем last_seen_date
            await self._update_last_seen(db_session, user_id)
            
            # 2. Сохраняем в UserActivityLog
            await self._save_activity_log(db_session, event, user_id)
            
            # 3. Проверяем возраст профиля и запускаем фоновое обновление если нужно
            await self._check_and_schedule_profile_update(db_session, user_id)
            
        except Exception as e:
            logger.error(f"Error in ProfileUpdateMiddleware for user {user_id}: {e}")
            # Не блокируем обработку события при ошибке
        
        return await handler(event, data)
    
    async def _update_last_seen(self, session: AsyncSession, user_id: int):
        """Обновляет last_seen_date пользователя"""
        try:
            result = await session.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if user:
                user.last_seen_date = datetime.now()
                await session.commit()
                logger.debug(f"Updated last_seen_date for user {user_id}")
        except Exception as e:
            logger.error(f"Error updating last_seen_date for user {user_id}: {e}")
            await session.rollback()
    
    async def _save_activity_log(
        self, 
        session: AsyncSession, 
        event: TelegramObject, 
        user_id: int
    ):
        """Сохраняет активность пользователя в UserActivityLog"""
        try:
            activity_type = "unknown"
            details = {}
            chat_id = None
            
            if isinstance(event, Message):
                chat_id = event.chat.id if event.chat else None
                
                if event.text:
                    if event.text.startswith('/'):
                        activity_type = "command"
                        details = {"command": event.text.split()[0]}
                    else:
                        activity_type = "message"
                        details = {"text": event.text[:500]}  # Ограничиваем длину
                elif event.photo:
                    activity_type = "photo"
                    details = {"photo_count": len(event.photo)}
                elif event.document:
                    activity_type = "document"
                    details = {"file_name": event.document.file_name}
                else:
                    activity_type = "other_message"
            
            elif isinstance(event, CallbackQuery):
                chat_id = event.message.chat.id if event.message and event.message.chat else None
                activity_type = "callback_query"
                details = {"data": event.data}
            
            log = UserActivityLog(
                user_id=user_id,
                chat_id=chat_id,
                activity_type=activity_type,
                details=details
            )
            
            session.add(log)
            await session.commit()
            logger.debug(f"Saved activity log for user {user_id}: {activity_type}")
            
        except Exception as e:
            logger.error(f"Error saving activity log for user {user_id}: {e}")
            await session.rollback()
    
    async def _check_and_schedule_profile_update(
        self, 
        session: AsyncSession, 
        user_id: int
    ):
        """Проверяет возраст профиля и запускает фоновое обновление если нужно"""
        try:
            result = await session.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                return
            
            # Проверяем markers['profile_updated_at']
            markers = user.markers or {}
            profile_updated_at_str = markers.get('profile_updated_at')
            
            if profile_updated_at_str:
                try:
                    profile_updated_at = datetime.fromisoformat(profile_updated_at_str)
                    age = datetime.now() - profile_updated_at
                    
                    if age > timedelta(days=7):
                        logger.info(
                            f"Profile for user {user_id} is {age.days} days old, "
                            f"scheduling background update"
                        )
                        await self._schedule_background_update(user_id)
                except (ValueError, TypeError) as e:
                    logger.warning(
                        f"Invalid profile_updated_at format for user {user_id}: {e}"
                    )
            else:
                # Если profile_updated_at отсутствует - тоже запускаем обновление
                logger.info(
                    f"Profile for user {user_id} has no update timestamp, "
                    f"scheduling background update"
                )
                await self._schedule_background_update(user_id)
                
        except Exception as e:
            logger.error(
                f"Error checking profile age for user {user_id}: {e}"
            )
    
    async def _schedule_background_update(self, user_id: int):
        """Запускает фоновую задачу обновления профиля"""
        # Проверяем, не запущена ли уже задача для этого пользователя
        if user_id in self._profile_update_tasks:
            task = self._profile_update_tasks[user_id]
            if not task.done():
                logger.debug(
                    f"Background update already running for user {user_id}"
                )
                return
        
        # Запускаем фоновую задачу
        task = asyncio.create_task(self._update_profile_background(user_id))
        self._profile_update_tasks[user_id] = task
        
        logger.info(f"Started background profile update for user {user_id}")
    
    async def _update_profile_background(self, user_id: int):
        """Фоновая задача обновления профиля"""
        try:
            from relove_bot.services.profile_rotation_service import ProfileRotationService
            from relove_bot.db.session import async_session
            
            logger.info(f"Starting background profile update for user {user_id}")
            
            async with async_session() as session:
                # Получаем пользователя
                from sqlalchemy import select
                from relove_bot.db.models import User
                
                result = await session.execute(
                    select(User).where(User.id == user_id)
                )
                user = result.scalar_one_or_none()
                
                if not user:
                    logger.warning(f"User {user_id} not found for background update")
                    return
                
                # Обновляем профиль через ProfileRotationService
                service = ProfileRotationService(session)
                await service.update_user_profile(user)
                
                logger.info(f"Completed background profile update for user {user_id}")
            
        except Exception as e:
            logger.error(
                f"Error in background profile update for user {user_id}: {e}",
                exc_info=True
            )
        finally:
            # Удаляем задачу из словаря
            if user_id in self._profile_update_tasks:
                del self._profile_update_tasks[user_id]
