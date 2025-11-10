"""
Rate Limiter для проактивных сообщений.
Контролирует частоту отправки проактивных сообщений.
"""
import logging
from datetime import datetime, date, time, timedelta
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from relove_bot.db.models import ProactiveTrigger, ProactivityConfig

logger = logging.getLogger(__name__)


class ProactiveRateLimiter:
    """Rate limiter для проактивных сообщений"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self._config_cache: Optional[ProactivityConfig] = None
        self._cache_time: Optional[datetime] = None
    
    async def check_proactive_limit(
        self,
        user_id: int,
        check_date: Optional[date] = None
    ) -> bool:
        """
        Проверяет, не превышен ли лимит проактивных сообщений
        
        Args:
            user_id: ID пользователя
            check_date: Дата для проверки (по умолчанию сегодня)
        
        Returns:
            True если можно отправить, False если лимит превышен
        """
        try:
            if check_date is None:
                check_date = date.today()
            
            # Получаем конфигурацию
            config = await self.get_config()
            max_messages = config.max_messages_per_day
            
            # Считаем отправленные сообщения за день
            start_of_day = datetime.combine(check_date, time.min)
            end_of_day = datetime.combine(check_date, time.max)
            
            query = select(func.count(ProactiveTrigger.id)).where(
                ProactiveTrigger.user_id == user_id,
                ProactiveTrigger.executed == True,
                ProactiveTrigger.executed_at >= start_of_day,
                ProactiveTrigger.executed_at <= end_of_day
            )
            
            result = await self.session.execute(query)
            count = result.scalar()
            
            can_send = count < max_messages
            
            if not can_send:
                logger.info(f"Proactive limit reached for user {user_id}: {count}/{max_messages}")
            
            return can_send
            
        except Exception as e:
            logger.error(f"Error checking proactive limit: {e}", exc_info=True)
            return False
    
    async def check_time_window(self) -> bool:
        """
        Проверяет, находимся ли мы в разрешённом временном окне
        
        Returns:
            True если в окне, False если нет
        """
        try:
            config = await self.get_config()
            
            current_time = datetime.now().time()
            start_time = config.time_window_start
            end_time = config.time_window_end
            
            # Преобразуем datetime в time если нужно
            if isinstance(start_time, datetime):
                start_time = start_time.time()
            if isinstance(end_time, datetime):
                end_time = end_time.time()
            
            in_window = start_time <= current_time <= end_time
            
            if not in_window:
                logger.info(f"Outside time window: {current_time} not in {start_time}-{end_time}")
            
            return in_window
            
        except Exception as e:
            logger.error(f"Error checking time window: {e}", exc_info=True)
            return False
    
    async def can_send_proactive(
        self,
        user_id: int,
        trigger_type: str
    ) -> bool:
        """
        Проверяет все условия для отправки проактивного сообщения
        
        Args:
            user_id: ID пользователя
            trigger_type: Тип триггера
        
        Returns:
            True если можно отправить, False если нет
        """
        try:
            # 1. Проверяем лимит сообщений в день
            if not await self.check_proactive_limit(user_id):
                return False
            
            # 2. Проверяем временное окно
            if not await self.check_time_window():
                return False
            
            # 3. Проверяем, включён ли этот тип триггера
            config = await self.get_config()
            if trigger_type not in config.enabled_triggers:
                logger.info(f"Trigger type {trigger_type} is disabled")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking if can send proactive: {e}", exc_info=True)
            return False
    
    async def get_config(self) -> ProactivityConfig:
        """
        Получает конфигурацию проактивности с кэшированием
        
        Returns:
            ProactivityConfig
        """
        try:
            # Проверяем кэш (TTL 5 минут)
            if self._config_cache and self._cache_time:
                if datetime.now() - self._cache_time < timedelta(minutes=5):
                    return self._config_cache
            
            # Загружаем из БД
            query = select(ProactivityConfig).limit(1)
            result = await self.session.execute(query)
            config = result.scalar_one_or_none()
            
            # Если нет конфигурации, создаём дефолтную
            if not config:
                config = ProactivityConfig(
                    max_messages_per_day=2,
                    time_window_start=datetime.strptime("08:00", "%H:%M").time(),
                    time_window_end=datetime.strptime("22:00", "%H:%M").time(),
                    enabled_triggers=[
                        "inactivity_24h",
                        "milestone_completed",
                        "pattern_detected",
                        "morning_check"
                    ]
                )
                self.session.add(config)
                await self.session.commit()
                logger.info("Created default proactivity config")
            
            # Обновляем кэш
            self._config_cache = config
            self._cache_time = datetime.now()
            
            return config
            
        except Exception as e:
            logger.error(f"Error getting config: {e}", exc_info=True)
            # Возвращаем дефолтную конфигурацию
            return ProactivityConfig(
                max_messages_per_day=2,
                time_window_start=datetime.strptime("08:00", "%H:%M").time(),
                time_window_end=datetime.strptime("22:00", "%H:%M").time(),
                enabled_triggers=["inactivity_24h", "milestone_completed"]
            )
    
    def invalidate_cache(self):
        """Инвалидирует кэш конфигурации"""
        self._config_cache = None
        self._cache_time = None
        logger.info("Proactivity config cache invalidated")
