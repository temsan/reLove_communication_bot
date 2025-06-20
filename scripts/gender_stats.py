#!/usr/bin/env python3
import os
import sys
import asyncio
from dotenv import load_dotenv

# Добавляем корень проекта в PYTHONPATH для корректного импорта
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Загружаем переменные окружения
load_dotenv()

from relove_bot.db.database import setup_database, AsyncSessionFactory
from relove_bot.db.models import User
from relove_bot.config import settings
from sqlalchemy import select, func

async def get_gender_stats():
    # Инициализируем базу данных
    await setup_database()
    
    # Проверяем, что AsyncSessionFactory инициализирован
    print(f"AsyncSessionFactory: {AsyncSessionFactory}")
    if AsyncSessionFactory is None:
        raise RuntimeError("AsyncSessionFactory не инициализирован. Проверьте настройки базы данных.")
    
    # Создаем сессию
    async with AsyncSessionFactory() as session:
        # Получаем статистику по полу
        result = await session.execute(
            select(
                User.gender,
                func.count()
            ).group_by(User.gender)
        )
        
        # Выводим результат
        print("Статистика по полу:")
        total = 0
        for gender, count in result:
            total += count
            print(f"{gender}: {count} пользователей")
        
        print(f"\nВсего пользователей: {total}")

if __name__ == "__main__":
    asyncio.run(get_gender_stats())