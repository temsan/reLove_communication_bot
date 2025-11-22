import asyncio
import logging
import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.engine import URL

# Импортируем настройки
from relove_bot.config import settings

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# SQL для создания таблицы и индексов
SQL_STATEMENTS = [
    # Создаем таблицу
    """
    CREATE TABLE IF NOT EXISTS youtube_chat_users (
        id SERIAL PRIMARY KEY,
        youtube_display_name VARCHAR(255) NOT NULL,
        youtube_channel_id VARCHAR(255),
        message_count INTEGER NOT NULL DEFAULT 0,
        first_seen TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        last_seen TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        telegram_username VARCHAR(64),
        telegram_id BIGINT,
        is_community_member BOOLEAN NOT NULL DEFAULT FALSE,
        user_metadata JSONB
    )
    """,
    
    # Создаем индексы по отдельности
    """
    CREATE INDEX IF NOT EXISTS idx_youtube_chat_users_display_name 
    ON youtube_chat_users (youtube_display_name)
    """,
    
    """
    CREATE INDEX IF NOT EXISTS idx_youtube_chat_users_telegram_username 
    ON youtube_chat_users (telegram_username)
    """,
    
    """
    CREATE INDEX IF NOT EXISTS idx_youtube_chat_users_telegram_id 
    ON youtube_chat_users (telegram_id)
    """
]

async def execute_sql(conn, sql, params=None):
    """Выполняет SQL-запрос с обработкой ошибок"""
    try:
        if params:
            await conn.execute(text(sql), params)
        else:
            await conn.execute(text(sql))
        return True
    except Exception as e:
        logger.error(f"Ошибка при выполнении SQL: {e}")
        logger.error(f"SQL: {sql}")
        if params:
            logger.error(f"Параметры: {params}")
        return False

async def init_db():
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
        
        # Проверяем соединение
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            logger.info("Успешное подключение к базе данных")
        
        # Создаем таблицу и индексы в отдельной транзакции
        async with engine.begin() as conn:
            logger.info("Начинаем создание таблицы и индексов...")
            
            # Выполняем каждый SQL-запрос по очереди
            for i, sql in enumerate(SQL_STATEMENTS, 1):
                sql = sql.strip()
                if not sql:
                    continue
                    
                logger.info(f"Выполнение команды {i}/{len(SQL_STATEMENTS)}...")
                logger.debug(f"SQL: {sql}")
                
                success = await execute_sql(conn, sql)
                if not success:
                    raise Exception(f"Не удалось выполнить команду {i}")
                
                logger.info(f"Успешно выполнена команда {i}/{len(SQL_STATEMENTS)}")
            
            logger.info("Таблица youtube_chat_users и индексы успешно созданы")
            
    except Exception as e:
        logger.error(f"Ошибка при создании таблицы: {e}", exc_info=True)
        raise
    finally:
        if engine:
            await engine.dispose()
            logger.info("Соединение с базой данных закрыто")

if __name__ == "__main__":
    asyncio.run(init_db())
