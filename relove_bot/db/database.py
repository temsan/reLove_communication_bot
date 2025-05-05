import logging
import sys
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from ..config import settings
from .models import Base

logger = logging.getLogger(__name__)

class Base(DeclarativeBase):
    pass

# Глобальные переменные для engine и sessionmaker
# Инициализируются в setup_database()
async_engine = None
AsyncSessionFactory = None

async def setup_database():
    """Initializes the database engine and session factory."""
    global async_engine, AsyncSessionFactory
    if not settings.db_url:
        logger.error("DB_URL (DB_DSN) is not configured. Database functionality will be disabled.")
        return False

    try:
        logger.info(f"Initializing database connection using URL...")
        async_engine = create_async_engine(
            settings.db_url,
            echo=False, # Установить в True для отладки SQL-запросов
            pool_pre_ping=True, # Проверять соединение перед использованием
            pool_size=50, # Увеличиваем размер пула для лучшей производительности
            max_overflow=100, # Увеличиваем максимальное количество дополнительных соединений
        )

        # Создаем фабрику сессий
        AsyncSessionFactory = async_sessionmaker(
            async_engine,
            class_=AsyncSession,
            expire_on_commit=False # Важно для асинхронного режима
        )

        # Проверяем соединение (опционально, но полезно)
        async with async_engine.connect() as conn:
            logger.info("Database connection successful.")

        # Создаем таблицы (если их нет)
        # В реальном приложении лучше использовать Alembic для миграций
        async with async_engine.begin() as conn:
            logger.info("Creating database tables if they don't exist...")
            # Импортируем модели здесь, чтобы избежать циклических зависимостей
            from .models import Base
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Table creation check complete.")

        return True
    except Exception as e:
        logger.exception(f"Failed to initialize database: {e}")
        return False

def get_engine():
    """
    Возвращает экземпляр engine.
    
    Returns:
        Engine: Экземпляр SQLAlchemy engine.
    """
    if async_engine is None:
        raise ValueError("Database engine is not initialized. Call setup_database() first.")
    return async_engine

def get_db_session():
    """Dependency (or context manager) to get a DB session."""
    if AsyncSessionFactory is None:
        logger.error("Database is not initialized. Cannot get session.")
        return None

    return AsyncSessionFactory()

database = sys.modules[__name__]

async def safe_db_operation(func):
    """Decorator for safe database operations."""
    async def wrapper(*args, **kwargs):
        session = get_db_session()
        if session is None:
            logger.error("Database session is not available.")
            raise Exception("Database session is not available.")
        try:
            return await func(*args, session=session, **kwargs)
        except Exception as e:
            logger.error(f"Database operation error: {e}")
            raise
    return wrapper

async def close_database():
    """Closes the database engine connection."""
    global async_engine
    if async_engine:
        logger.info("Closing database engine connections...")
        try:
            await async_engine.dispose()
            async_engine = None
            logger.info("Database engine connections closed.")
        except Exception as e:
            logger.error(f"Error closing database engine: {e}")
            raise
    else:
         logger.info("Database engine was not initialized, skipping close.") 