"""
Фоновые задачи для бота.
Включает ротацию профилей и архивацию логов.
"""
import asyncio
import logging
from datetime import datetime, timedelta

from relove_bot.db.session import async_session
from relove_bot.services.profile_rotation_service import ProfileRotationService

logger = logging.getLogger(__name__)


async def profile_rotation_task():
    """
    Фоновая задача ротации профилей.
    Запускается каждые 24 часа.
    """
    while True:
        try:
            logger.info("Starting profile rotation task...")
            
            async with async_session() as session:
                service = ProfileRotationService(session)
                await service.rotate_profiles()
            
            logger.info("Profile rotation task completed")
            
        except Exception as e:
            logger.error(f"Error in profile rotation task: {e}", exc_info=True)
        
        # Ждём 24 часа
        await asyncio.sleep(86400)


async def log_archive_task():
    """
    Фоновая задача архивации логов.
    Архивирует логи старше 90 дней.
    Запускается каждые 7 дней.
    """
    while True:
        try:
            logger.info("Starting log archive task...")
            
            async with async_session() as session:
                from relove_bot.db.models import UserActivityLog, UserActivityLogArchive
                from sqlalchemy import select, delete
                
                # Дата 90 дней назад
                cutoff_date = datetime.now() - timedelta(days=90)
                
                # Получаем старые логи
                query = select(UserActivityLog).where(
                    UserActivityLog.timestamp < cutoff_date
                )
                result = await session.execute(query)
                old_logs = result.scalars().all()
                
                if old_logs:
                    logger.info(f"Found {len(old_logs)} logs to archive")
                    
                    # Копируем в архив
                    for log in old_logs:
                        archive_log = UserActivityLogArchive(
                            user_id=log.user_id,
                            chat_id=log.chat_id,
                            activity_type=log.activity_type,
                            timestamp=log.timestamp,
                            details=log.details
                        )
                        session.add(archive_log)
                    
                    # Удаляем из основной таблицы
                    await session.execute(
                        delete(UserActivityLog).where(
                            UserActivityLog.timestamp < cutoff_date
                        )
                    )
                    
                    await session.commit()
                    logger.info(f"Archived {len(old_logs)} logs")
                else:
                    logger.info("No logs to archive")
            
            logger.info("Log archive task completed")
            
        except Exception as e:
            logger.error(f"Error in log archive task: {e}", exc_info=True)
        
        # Ждём 7 дней
        await asyncio.sleep(604800)
