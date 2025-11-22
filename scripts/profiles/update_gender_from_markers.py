#!/usr/bin/env python3
import os
import sys
import asyncio
import logging
from dotenv import load_dotenv
from sqlalchemy import select, update, or_
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql.expression import cast
from sqlalchemy.dialects.postgresql import JSONB

# Добавляем корень проекта в PYTHONPATH для корректного импорта
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from relove_bot.db.models import User, GenderEnum
from relove_bot.config import settings
from relove_bot.utils.custom_logging import setup_logging

# Настройка логирования
setup_logging()
logger = logging.getLogger(__name__)

async def update_genders_from_markers():
    """Обновляет поле gender из markers для всех пользователей"""
    # Загружаем переменные окружения
    load_dotenv()
    
    # Создаем движок и сессию
    engine = create_async_engine(settings.db_url)
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    updated_count = 0
    skipped_count = 0
    error_count = 0
    
    try:
        async with async_session() as session:
            # Получаем всех пользователей и фильтруем в Python
            result = await session.execute(select(User))
            all_users = result.scalars().all()
            
            # Фильтруем пользователей с корректными маркерами пола
            users = [
                user for user in all_users 
                if user.markers and 
                user.markers.get('gender') in ['male', 'female']
            ]
            
            logger.info(f"Найдено {len(users)} пользователей с маркером gender")
            
            # Обрабатываем каждого пользователя
            for user in users:
                try:
                    # Получаем пол из маркера
                    marker_gender = user.markers.get('gender', '').lower()
                    
                    # Проверяем, что пол корректен
                    if marker_gender not in ['male', 'female']:
                        logger.warning(f"Пользователь {user.id}: некорректное значение пола в маркере: {marker_gender}")
                        error_count += 1
                        continue
                    
                    # Определяем новый пол
                    new_gender = GenderEnum[marker_gender]
                    
                    # Логируем изменение, если пол уже был установлен
                    if user.gender and user.gender != new_gender:
                        logger.info(f"Пользователь {user.id}: изменение пола с {user.gender} на {new_gender} (по маркеру)")
                    user.gender = new_gender
                    
                    # Обновляем запись в базе
                    await session.execute(
                        update(User)
                        .where(User.id == user.id)
                        .values(gender=new_gender)
                    )
                    
                    await session.commit()
                    logger.info(f"Пользователь {user.id}: пол обновлен на {new_gender}")
                    updated_count += 1
                    
                except Exception as e:
                    error_count += 1
                    logger.error(f"Ошибка при обновлении пользователя {getattr(user, 'id', 'unknown')}: {e}")
                    await session.rollback()
    
    finally:
        await engine.dispose()
    
    # Выводим статистику
    logger.info("\nСтатистика обновления полов:")
    logger.info(f"- Всего пользователей с маркером пола: {len(users)}")
    logger.info(f"- Обновлено записей: {updated_count}")
    logger.info(f"- Ошибок обработки: {error_count}")

if __name__ == "__main__":
    asyncio.run(update_genders_from_markers())
