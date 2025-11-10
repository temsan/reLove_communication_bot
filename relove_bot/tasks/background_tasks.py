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


async def check_proactive_triggers_task():
    """
    Фоновая задача проверки проактивных триггеров.
    Запускается каждые 15 минут.
    """
    while True:
        try:
            logger.info("Starting proactive triggers check...")
            
            async with async_session() as session:
                from relove_bot.services.trigger_engine import TriggerEngine
                
                engine = TriggerEngine(session)
                
                # Проверяем неактивность
                await engine.check_inactivity_triggers()
                
                # Проверяем завершённые этапы
                await engine.check_milestone_triggers()
            
            logger.info("Proactive triggers check completed")
            
        except Exception as e:
            logger.error(f"Error in proactive triggers check: {e}", exc_info=True)
        
        # Ждём 15 минут
        await asyncio.sleep(900)


async def send_proactive_messages_task(bot):
    """
    Фоновая задача отправки проактивных сообщений.
    Запускается каждую минуту.
    
    Args:
        bot: Экземпляр бота для отправки сообщений
    """
    while True:
        try:
            async with async_session() as session:
                from relove_bot.services.trigger_engine import TriggerEngine
                from relove_bot.services.message_orchestrator import MessageOrchestrator
                from relove_bot.services.proactive_rate_limiter import ProactiveRateLimiter
                
                engine = TriggerEngine(session)
                orchestrator = MessageOrchestrator(session)
                rate_limiter = ProactiveRateLimiter(session)
                
                # Получаем готовые триггеры
                pending_triggers = await engine.get_pending_triggers()
                
                for trigger in pending_triggers:
                    try:
                        # Проверяем rate limit
                        can_send = await rate_limiter.can_send_proactive(
                            trigger.user_id,
                            trigger.trigger_type.value
                        )
                        
                        if not can_send:
                            logger.info(f"Skipping trigger {trigger.id} due to rate limit")
                            continue
                        
                        # Генерируем сообщение
                        response = await orchestrator.generate_proactive_message(
                            trigger.user_id,
                            trigger.trigger_type
                        )
                        
                        if response:
                            # Отправляем сообщение
                            await bot.send_message(
                                chat_id=trigger.user_id,
                                text=response.text,
                                reply_markup=response.keyboard,
                                parse_mode=response.parse_mode
                            )
                            
                            # Отмечаем как выполненный
                            await engine.mark_trigger_executed(
                                trigger.id,
                                message_sent=response.text
                            )
                            
                            logger.info(f"Sent proactive message to user {trigger.user_id}")
                        else:
                            # Отмечаем с ошибкой
                            await engine.mark_trigger_executed(
                                trigger.id,
                                error="Failed to generate message"
                            )
                    
                    except Exception as e:
                        logger.error(f"Error sending proactive message for trigger {trigger.id}: {e}", exc_info=True)
                        await engine.mark_trigger_executed(
                            trigger.id,
                            error=str(e)
                        )
            
        except Exception as e:
            logger.error(f"Error in send proactive messages task: {e}", exc_info=True)
        
        # Ждём 1 минуту
        await asyncio.sleep(60)
