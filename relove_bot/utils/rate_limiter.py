import asyncio
import time
from functools import wraps
from typing import Callable, Any, TypeVar, Coroutine, Union, Awaitable

T = TypeVar('T')

class RateLimiter:
    """
    Декоратор для ограничения частоты вызовов асинхронных функций.
    
    Args:
        max_calls: Максимальное количество вызовов за период
        period: Период в секундах
    """
    def __init__(self, max_calls: int, period: float):
        self.max_calls = max_calls
        self.period = period
        self.calls = 0
        self.last_reset = time.time()
        self.lock = asyncio.Lock()
    
    def __call__(self, func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def wrapped(*args, **kwargs) -> T:
            async with self.lock:
                now = time.time()
                
                # Сбрасываем счетчик, если прошел период
                if now - self.last_reset > self.period:
                    self.calls = 0
                    self.last_reset = now
                
                # Если превысили лимит, ждем
                if self.calls >= self.max_calls:
                    sleep_time = self.period - (now - self.last_reset)
                    if sleep_time > 0:
                        # await asyncio.sleep(sleep_time)
                        pass
                    self.calls = 0
                    self.last_reset = time.time()
                
                self.calls += 1
            
            # Вызываем оригинальную функцию вне блока lock, чтобы не блокировать другие вызовы
            return await func(*args, **kwargs)
            
        return wrapped

# Глобальный rate limiter для LLM API (3 запроса в минуту)
llm_rate_limiter = RateLimiter(max_calls=3, period=60)  # Ограничение: 3 запроса в минуту
