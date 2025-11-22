import asyncio
from dotenv import load_dotenv
from relove_bot.db.repository import UserRepository
from relove_bot.config import settings
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from relove_bot.utils.gender import detect_gender
from tqdm.asyncio import tqdm

# Загружаем переменные окружения
load_dotenv()

async def process_user(user, repo):
    """Обрабатывает одного пользователя"""
    try:
        # Проверяем, есть ли уже пол
        if user.gender and user.gender != 'unknown':
            print(f"Пол пользователя {user.id} уже определен: {user.gender}")
            return user.gender.value if hasattr(user.gender, 'value') else user.gender

        # Определяем пол
        gender = await detect_gender(user)
        print(f"Определенный пол: {gender}")
        
        # Обновляем пол в базе данных
        await repo.update_gender(user.id, gender)
        print(f"Пол пользователя {user.id} обновлен")
        
        return gender
    except Exception as e:
        print(f"Ошибка при обработке пользователя {user.id}: {e}")
        return 'unknown'

async def main():
    """Основная функция"""
    # Загружаем переменные окружения
    load_dotenv()
    
    # Создаем движок и сессию
    engine = create_async_engine(settings.db_url)
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    try:
        # Создаем репозиторий
        repo = UserRepository(async_session())
        
        # Получаем всех пользователей
        users = await repo.get_all_users()
        if not users:
            print("Нет пользователей в базе данных")
            return
            
        # Статистика
        male_count = 0
        female_count = 0
        unknown_count = 0
        
        # Обрабатываем всех пользователей
        for user in tqdm(users, desc="Определение пола пользователей"):
            gender = await process_user(user, repo)
            if gender == 'male':
                male_count += 1
            elif gender == 'female':
                female_count += 1
            else:
                unknown_count += 1
                
        # Выводим статистику
        total_users = len(users)
        print(f"\nСтатистика определения пола:")
        print(f"Всего пользователей: {total_users}")
        print(f"Мужчины: {male_count} ({(male_count/total_users*100):.1f}%)")
        print(f"Женщины: {female_count} ({(female_count/total_users*100):.1f}%)")
        print(f"Не определено: {unknown_count} ({(unknown_count/total_users*100):.1f}%)")
            
    finally:
        await repo.session.close()
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
