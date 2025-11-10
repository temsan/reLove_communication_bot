"""
Trigger Engine для проактивных сообщений.
Отслеживает события и создаёт триггеры для отправки проактивных сообщений.
"""
import logging
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from relove_bot.db.models import (
    User, UserSession, ProactiveTrigger, TriggerTypeEnum,
    JourneyProgress, JourneyStageEnum
)

logger = logging.getLogger(__name__)


class TriggerEngine:
    """Движок для создания и управления проактивными триггерами"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def check_inactivity_triggers(self) -> List[ProactiveTrigger]:
        """
        Проверяет пользователей с неактивностью 24ч и создаёт триггеры
        
        Returns:
            Список созданных триггеров
        """
        try:
            cutoff_time = datetime.now() - timedelta(hours=24)
            
            # Находим пользователей с активными сессиями без ответа 24ч
            query = select(UserSession).where(
                and_(
                    UserSession.is_active == True,
                    UserSession.updated_at < cutoff_time
                )
            )
            
            result = await self.session.execute(query)
            inactive_sessions = result.scalars().all()
            
            triggers = []
            for session in inactive_sessions:
                # Проверяем, нет ли уже триггера для этого пользователя
                existing_trigger = await self._get_pending_trigger(
                    session.user_id,
                    TriggerTypeEnum.INACTIVITY_24H
                )
                
                if not existing_trigger:
                    # Создаём новый триггер
                    trigger = ProactiveTrigger(
                        user_id=session.user_id,
                        trigger_type=TriggerTypeEnum.INACTIVITY_24H,
                        scheduled_time=datetime.now()
                    )
                    self.session.add(trigger)
                    triggers.append(trigger)
            
            await self.session.commit()
            logger.info(f"Created {len(triggers)} inactivity triggers")
            
            return triggers
            
        except Exception as e:
            logger.error(f"Error checking inactivity triggers: {e}", exc_info=True)
            await self.session.rollback()
            return []
    
    async def check_milestone_triggers(self) -> List[ProactiveTrigger]:
        """
        Проверяет завершение этапов пути и создаёт триггеры
        
        Returns:
            Список созданных триггеров
        """
        try:
            # Находим недавние изменения в JourneyProgress (последние 5 минут)
            recent_time = datetime.now() - timedelta(minutes=5)
            
            query = select(JourneyProgress).where(
                JourneyProgress.created_at >= recent_time
            )
            
            result = await self.session.execute(query)
            recent_progress = result.scalars().all()
            
            triggers = []
            for progress in recent_progress:
                # Проверяем, нет ли уже триггера
                existing_trigger = await self._get_pending_trigger(
                    progress.user_id,
                    TriggerTypeEnum.MILESTONE_COMPLETED
                )
                
                if not existing_trigger:
                    trigger = ProactiveTrigger(
                        user_id=progress.user_id,
                        trigger_type=TriggerTypeEnum.MILESTONE_COMPLETED,
                        scheduled_time=datetime.now()
                    )
                    self.session.add(trigger)
                    triggers.append(trigger)
            
            await self.session.commit()
            logger.info(f"Created {len(triggers)} milestone triggers")
            
            return triggers
            
        except Exception as e:
            logger.error(f"Error checking milestone triggers: {e}", exc_info=True)
            await self.session.rollback()
            return []
    
    async def check_pattern_triggers(
        self,
        user_id: int,
        conversation: List[dict]
    ) -> Optional[ProactiveTrigger]:
        """
        Проверяет паттерны избегания в диалоге
        
        Args:
            user_id: ID пользователя
            conversation: История диалога
        
        Returns:
            Созданный триггер или None
        """
        try:
            # Простая эвристика: если последние 3 ответа короткие (<10 символов)
            # или содержат отрицания
            if len(conversation) < 3:
                return None
            
            last_messages = conversation[-3:]
            avoidance_detected = False
            
            # Проверяем паттерны избегания
            short_answers = sum(1 for msg in last_messages if len(msg.get('content', '')) < 10)
            denial_words = ['не знаю', 'не понимаю', 'не хочу', 'потом', 'может быть']
            denials = sum(
                1 for msg in last_messages
                if any(word in msg.get('content', '').lower() for word in denial_words)
            )
            
            if short_answers >= 2 or denials >= 2:
                avoidance_detected = True
            
            if avoidance_detected:
                # Проверяем, нет ли уже триггера
                existing_trigger = await self._get_pending_trigger(
                    user_id,
                    TriggerTypeEnum.PATTERN_DETECTED
                )
                
                if not existing_trigger:
                    trigger = ProactiveTrigger(
                        user_id=user_id,
                        trigger_type=TriggerTypeEnum.PATTERN_DETECTED,
                        scheduled_time=datetime.now()
                    )
                    self.session.add(trigger)
                    await self.session.commit()
                    
                    logger.info(f"Created pattern trigger for user {user_id}")
                    return trigger
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking pattern triggers: {e}", exc_info=True)
            await self.session.rollback()
            return None
    
    async def schedule_proactive_message(
        self,
        user_id: int,
        trigger_type: TriggerTypeEnum,
        delay: timedelta = timedelta(0)
    ) -> Optional[ProactiveTrigger]:
        """
        Планирует проактивное сообщение
        
        Args:
            user_id: ID пользователя
            trigger_type: Тип триггера
            delay: Задержка перед отправкой
        
        Returns:
            Созданный триггер или None
        """
        try:
            # Проверяем, нет ли уже триггера
            existing_trigger = await self._get_pending_trigger(user_id, trigger_type)
            
            if existing_trigger:
                logger.info(f"Trigger already exists for user {user_id}, type {trigger_type}")
                return existing_trigger
            
            trigger = ProactiveTrigger(
                user_id=user_id,
                trigger_type=trigger_type,
                scheduled_time=datetime.now() + delay
            )
            
            self.session.add(trigger)
            await self.session.commit()
            
            logger.info(f"Scheduled proactive message for user {user_id}, type {trigger_type}")
            return trigger
            
        except Exception as e:
            logger.error(f"Error scheduling proactive message: {e}", exc_info=True)
            await self.session.rollback()
            return None
    
    async def get_pending_triggers(self) -> List[ProactiveTrigger]:
        """
        Получает все незавершённые триггеры, готовые к выполнению
        
        Returns:
            Список триггеров
        """
        try:
            query = select(ProactiveTrigger).where(
                and_(
                    ProactiveTrigger.executed == False,
                    ProactiveTrigger.scheduled_time <= datetime.now()
                )
            )
            
            result = await self.session.execute(query)
            return list(result.scalars().all())
            
        except Exception as e:
            logger.error(f"Error getting pending triggers: {e}", exc_info=True)
            return []
    
    async def mark_trigger_executed(
        self,
        trigger_id: int,
        message_sent: Optional[str] = None,
        error: Optional[str] = None
    ):
        """
        Отмечает триггер как выполненный
        
        Args:
            trigger_id: ID триггера
            message_sent: Отправленное сообщение
            error: Сообщение об ошибке если была
        """
        try:
            query = select(ProactiveTrigger).where(ProactiveTrigger.id == trigger_id)
            result = await self.session.execute(query)
            trigger = result.scalar_one_or_none()
            
            if trigger:
                trigger.executed = True
                trigger.executed_at = datetime.now()
                trigger.message_sent = message_sent
                trigger.error_message = error
                
                await self.session.commit()
                logger.info(f"Marked trigger {trigger_id} as executed")
            
        except Exception as e:
            logger.error(f"Error marking trigger as executed: {e}", exc_info=True)
            await self.session.rollback()
    
    async def cancel_trigger(self, trigger_id: int):
        """
        Отменяет триггер
        
        Args:
            trigger_id: ID триггера
        """
        try:
            query = select(ProactiveTrigger).where(ProactiveTrigger.id == trigger_id)
            result = await self.session.execute(query)
            trigger = result.scalar_one_or_none()
            
            if trigger:
                await self.session.delete(trigger)
                await self.session.commit()
                logger.info(f"Cancelled trigger {trigger_id}")
            
        except Exception as e:
            logger.error(f"Error cancelling trigger: {e}", exc_info=True)
            await self.session.rollback()
    
    async def _get_pending_trigger(
        self,
        user_id: int,
        trigger_type: TriggerTypeEnum
    ) -> Optional[ProactiveTrigger]:
        """Получает незавершённый триггер для пользователя"""
        query = select(ProactiveTrigger).where(
            and_(
                ProactiveTrigger.user_id == user_id,
                ProactiveTrigger.trigger_type == trigger_type,
                ProactiveTrigger.executed == False
            )
        )
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
