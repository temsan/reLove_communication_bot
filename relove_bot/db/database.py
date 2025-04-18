import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from ..config import settings

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
            pool_size=10, # Настроить размер пула под нагрузку
            max_overflow=20,
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
            from . import models # noqa
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Table creation check complete.")

        return True
    except Exception as e:
        logger.exception(f"Failed to initialize database: {e}")
        return False

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency (or context manager) to get a DB session."""
    if AsyncSessionFactory is None:
        logger.error("Database is not initialized. Cannot get session.")
        yield None # Или вызвать исключение
        return

    async with AsyncSessionFactory() as session:
        try:
            yield session
        except Exception:
            logger.exception("Session rollback because of exception")
            await session.rollback()
            raise
        finally:
            await session.close()

async def close_database():
    """Closes the database engine connection."""
    global async_engine
    if async_engine:
        logger.info("Closing database engine connections...")
        await async_engine.dispose()
        async_engine = None
        logger.info("Database connections closed.")
    else:
         logger.info("Database engine was not initialized, skipping close.") 