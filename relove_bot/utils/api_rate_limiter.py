import asyncio
from typing import Dict, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class APIRateLimiter:
    def __init__(self, max_requests_per_minute: int = 20, max_requests_per_day: int = 1000):
        self.max_requests_per_minute = max_requests_per_minute
        self.max_requests_per_day = max_requests_per_day
        
        self.requests_per_minute: Dict[str, int] = {}
        self.requests_per_day: Dict[str, int] = {}
        self.last_reset: Dict[str, datetime] = {}
        
        self.lock = asyncio.Lock()
        
    async def wait_for_limit(self, api_key: str):
        """Ожидает, пока не будет превышен лимит запросов"""
        async with self.lock:
            current_time = datetime.now()
            
            # Сбрасываем счетчики, если прошла минута
            if api_key not in self.last_reset or current_time - self.last_reset[api_key] > timedelta(minutes=1):
                self.requests_per_minute[api_key] = 0
                self.last_reset[api_key] = current_time
                
            # Сбрасываем дневные лимиты, если прошел день
            if api_key not in self.requests_per_day or current_time - self.last_reset[api_key] > timedelta(days=1):
                self.requests_per_day[api_key] = 0
                self.last_reset[api_key] = current_time
            
            # Проверяем лимиты
            if self.requests_per_minute[api_key] >= self.max_requests_per_minute:
                logger.warning(f"Достигнут лимит запросов в минуту для API ключа {api_key[:5]}...")
                # Ждем до следующей минуты
                next_minute = (current_time + timedelta(minutes=1)).replace(second=0, microsecond=0)
                wait_time = (next_minute - current_time).total_seconds()
                logger.info(f"Ожидание {wait_time:.1f} секунд до следующей минуты")
                await asyncio.sleep(wait_time)
                # Сбрасываем счетчик после ожидания
                self.requests_per_minute[api_key] = 0
                self.last_reset[api_key] = datetime.now()
            
            if self.requests_per_day[api_key] >= self.max_requests_per_day:
                logger.warning(f"Достигнут дневной лимит запросов для API ключа {api_key[:5]}...")
                # Ждем до следующего дня
                next_day = (current_time + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                wait_time = (next_day - current_time).total_seconds()
                logger.info(f"Ожидание {wait_time:.1f} секунд до следующего дня")
                await asyncio.sleep(wait_time)
                # Сбрасываем счетчик после ожидания
                self.requests_per_day[api_key] = 0
                self.last_reset[api_key] = datetime.now()
            
            # Увеличиваем счетчики
            self.requests_per_minute[api_key] += 1
            self.requests_per_day[api_key] += 1
            
    async def get_remaining_limits(self, api_key: str) -> tuple[int, int]:
        """Возвращает оставшиеся запросы в минуту и в день"""
        async with self.lock:
            return (
                self.max_requests_per_minute - self.requests_per_minute.get(api_key, 0),
                self.max_requests_per_day - self.requests_per_day.get(api_key, 0)
            )
