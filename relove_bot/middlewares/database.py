"""Database middleware для aiogram."""
from .db import DbSessionMiddleware

# Алиас для совместимости
DatabaseMiddleware = DbSessionMiddleware

