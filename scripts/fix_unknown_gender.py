#!/usr/bin/env python3
import asyncio
import logging
from sqlalchemy import update, select, text
from sqlalchemy.ext.asyncio import AsyncSession

# Добавляем корень проекта в PYTHONPATH для корректного импорта
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from relove_bot.db.database import setup_database, get_engine, get_db_session
from relove_bot.db.models import User, GenderEnum
from relove_bot.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def fix_unknown_gender():
    """
    Обновляет записи в базе данных, где пол установлен в 'unknown',
    устанавливая значение по умолчанию GenderEnum.female.
    """
    # Инициализируем базу данных
    if not await setup_database():
        logger.error("Не удалось инициализировать подключение к базе данных.")
        return

    session = get_db_session()
    if session is None:
        logger.error("Не удалось получить сессию базы данных.")
        return
        
    try:
        # Используем сырой SQL запрос для обновления записей
        result = await session.execute(
            text("""
            SELECT COUNT(*) 
            FROM users 
            WHERE gender = 'unknown'::genderenum
            """)
        )
        count = result.scalar_one()
        
        if count == 0:
            logger.info("Нет пользователей с полем gender = 'unknown'.")
            return
            
        logger.info(f"Найдено {count} пользователей с полем gender = 'unknown'.")
        
        # Обновляем записи с использованием сырого SQL
        result = await session.execute(
            text("""
            UPDATE users 
            SET gender = 'female'::genderenum 
            WHERE gender = 'unknown'::genderenum
            """)
        )
        await session.commit()
        
        logger.info(f"Обновлено {result.rowcount} записей, установлен пол 'female'.")
        
    except Exception as e:
        if session.in_transaction():
            await session.rollback()
        logger.error(f"Ошибка при обновлении записей: {e}", exc_info=True)
    finally:
        await session.close()

if __name__ == "__main__":
    asyncio.run(fix_unknown_gender())
