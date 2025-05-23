#!/usr/bin/env python3
import asyncio
from relove_bot.db.database import setup_database, AsyncSessionFactory
from relove_bot.config import settings

async def test_db_connection():
    # Инициализируем базу данных
    await setup_database()
    
    # Проверяем, что AsyncSessionFactory инициализирован
    if AsyncSessionFactory is None:
        raise RuntimeError("AsyncSessionFactory не инициализирован. Проверьте настройки базы данных.")
    
    print("База данных успешно инициализирована!")

if __name__ == "__main__":
    asyncio.run(test_db_connection())
