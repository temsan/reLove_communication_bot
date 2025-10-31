from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from ..config import settings

Base = declarative_base()

engine = create_async_engine(
    settings.db_url,  # Добавьте в config.py: db_url: str = Field(...)
    echo=False,
    future=True,
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

def get_session():
    """Получает асинхронную сессию базы данных"""
    return SessionLocal()

# Для совместимости с bot.py
async_session = SessionLocal
