import asyncio
import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from relove_bot.config import settings

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def check_tables():
    engine = None
    try:
        # Получаем URL для подключения к базе данных
        db_url = settings.db_url
        
        # Если используется SQLite, заменяем на асинхронный драйвер
        if db_url.startswith('sqlite'):
            db_url = db_url.replace('sqlite://', 'sqlite+aiosqlite:///')
        # Для PostgreSQL заменяем на асинхронный драйвер
        elif db_url.startswith('postgresql'):
            db_url = db_url.replace('postgresql://', 'postgresql+asyncpg://')
        
        logger.info(f"Подключаемся к базе данных: {db_url.split('@')[-1] if '@' in db_url else db_url}")
        
        # Создаем асинхронный движок
        engine = create_async_engine(db_url, echo=True)
        
        # Проверяем наличие таблицы youtube_chat_users
        async with engine.connect() as conn:
            # Для PostgreSQL
            if 'postgresql' in db_url:
                result = await conn.execute(
                    text("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = 'youtube_chat_users'
                    )
                    """)
                )
                exists = result.scalar()
                logger.info(f"Таблица youtube_chat_users существует: {exists}")
                
                # Получаем информацию о таблице
                if exists:
                    result = await conn.execute(
                        text("""
                        SELECT column_name, data_type 
                        FROM information_schema.columns 
                        WHERE table_name = 'youtube_chat_users'
                        ORDER BY ordinal_position
                        """)
                    )
                    logger.info("Столбцы таблицы youtube_chat_users:")
                    for row in result:
                        logger.info(f"  {row.column_name}: {row.data_type}")
            
            # Для SQLite
            else:
                result = await conn.execute(
                    text("SELECT name FROM sqlite_master WHERE type='table' AND name='youtube_chat_users'")
                )
                exists = bool(result.fetchone())
                logger.info(f"Таблица youtube_chat_users существует: {exists}")
                
                if exists:
                    result = await conn.execute(
                        text("PRAGMA table_info(youtube_chat_users)")
                    )
                    logger.info("Столбцы таблицы youtube_chat_users:")
                    for row in result:
                        logger.info(f"  {row.name}: {row.type}")
        
    except Exception as e:
        logger.error(f"Ошибка при проверке таблиц: {e}", exc_info=True)
        raise
    finally:
        if engine:
            await engine.dispose()
            logger.info("Соединение с базой данных закрыто")

if __name__ == "__main__":
    asyncio.run(check_tables())
