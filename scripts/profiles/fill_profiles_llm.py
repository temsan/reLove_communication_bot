#!/usr/bin/env python3
# Отключаем предупреждения до импорта других библиотек
import warnings
warnings.filterwarnings('ignore', category=FutureWarning, module='transformers*')
warnings.filterwarnings('ignore', category=UserWarning, module='transformers*')

import os
import sys
import asyncio
import logging
from dotenv import load_dotenv

# Добавляем корень проекта в PYTHONPATH для корректного импорта
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from relove_bot.config import settings, reload_settings
from relove_bot.utils.fill_profiles import fill_all_profiles
from relove_bot.db.database import setup_database
from relove_bot.db.repository import UserRepository
from relove_bot.services.llm_service import llm_service
from relove_bot.services.prompts import PROFILE_INTERESTS_PROMPT

logger = logging.getLogger(__name__)

# Отключаем логирование для всех логгеров, кроме ошибок
for name in logging.root.manager.loggerDict:
    logging.getLogger(name).setLevel(logging.ERROR)

# Загружаем настройки из .env
load_dotenv(override=True)
reload_settings()

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.future import select
from sqlalchemy.orm import sessionmaker
from relove_bot.db.models import User  # Предполагается, что у вас есть модель User

# Создаём асинхронное подключение к базе данных
engine = create_async_engine('sqlite+aiosqlite:///path_to_your_database.db')  # Замените на ваш путь к базе данных
Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_users_from_db():
    async with Session() as session:
        stmt = select(User)
        result = await session.execute(stmt)
        return result.scalars().all()

async def update_user_profile(user_id, profile_data):
    async with Session() as session:
        stmt = select(User).where(User.id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        if user:
            user.profile_data = profile_data  # Предполагается, что у модели User есть поле profile_data
            await session.commit()
            print(f"Профиль пользователя {user_id} обновлён данными: {profile_data}")
        else:
            print(f"Пользователь с ID {user_id} не найден в базе данных")

async def fill_profiles_with_llm():
    """
    Заполняет профили пользователей с помощью LLM.
    """
    try:
        # Получаем всех пользователей
        users = await get_users_from_db()
        
        for user in users:
            try:
                # Получаем профиль пользователя
                profile = await get_user_profile(user.id)
                if not profile:
                    continue
                    
                # Анализируем текстовые поля
                text_parts = []
                if profile.first_name:
                    text_parts.append(f"Имя: {profile.first_name}")
                if profile.last_name:
                    text_parts.append(f"Фамилия: {profile.last_name}")
                if profile.username:
                    text_parts.append(f"Логин: @{profile.username}")
                if profile.bio:
                    text_parts.append(f"О себе: {profile.bio}")
                    
                if not text_parts:
                    continue
                    
                prompt = "\n".join(text_parts)
                
                # Анализируем профиль
                result = await llm_service.analyze_text(
                    text=prompt,
                    system_prompt=PROFILE_INTERESTS_PROMPT,
                    max_tokens=64
                )
                
                if not result:
                    continue
                    
                # Обновляем профиль
                await update_user_profile(user.id, {
                    'interests': result.strip()
                })
                
            except Exception as e:
                logger.error(f"Ошибка при заполнении профиля пользователя {user.id}: {e}", exc_info=True)
                continue
                
    except Exception as e:
        logger.error(f"Ошибка при заполнении профилей: {e}", exc_info=True)

async def main():
    try:
        # Запускаем процесс обновления профилей через LLM
        # Временно отключаем обращение к Telegram API
        await fill_profiles_with_llm()

        return 0
    except Exception as e:
        logger.error(f"Ошибка при обновлении профилей через LLM: {e}")
        return 1

if __name__ == "__main__":
    asyncio.run(main())
