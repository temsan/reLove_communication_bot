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
from relove_bot.rag.llm import LLM

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
    users = await get_users_from_db()
    for user in users:
        if not user.profile_filled:
            profile_data = await LLM.analyze_content(f"Заполните профиль для пользователя {user.id}")
# Создаём подключение к базе данных
engine = create_engine('sqlite:///path_to_your_database.db')  # Замените на ваш путь к базе данных
Session = sessionmaker(bind=engine)
session = Session()

def get_users_from_db():
    # Получаем всех пользователей из базы данных
    return session.query(User).all()

def update_user_profile(user_id, profile_data):
    # Обновляем профиль пользователя в базе данных
    user = session.query(User).filter(User.id == user_id).first()
    if user:
        user.profile_data = profile_data  # Предполагается, что у модели User есть поле profile_data
        session.commit()
        print(f"Профиль пользователя {user_id} обновлён данными: {profile_data}")
    else:
        print(f"Пользователь с ID {user_id} не найден в базе данных")


async def fill_profiles_with_llm():
    # Предположим, что у нас есть функция get_users_from_db, которая возвращает список пользователей
    users = get_users_from_db()  # Эта функция должна быть определена для получения пользователей из БД

    for user in users:
        # Проверяем, есть ли незаполненные поля
        if not user.profile_filled:
            # Вызываем LLM для заполнения профиля
            profile_data = await LLM.analyze_content(f"Заполните профиль для пользователя {user.id}")
            # Обновляем профиль пользователя в базе данных
            update_user_profile(user.id, profile_data)  # Эта функция должна быть определена для обновления профиля в БД


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
