"""
Упрощённый скрипт для первичного заполнения профилей пользователей.
Не требует логов активности или постов из Telegram.
"""
import asyncio
import logging
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from tqdm import tqdm

from relove_bot.db.models import User

from relove_bot.db.session import async_session

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def fill_basic_profiles():
    """Заполняет базовые профили для всех пользователей без профиля"""
    logger.info("Starting basic profile fill...")
    
    async with async_session() as session:
        # Получаем всех пользователей без psychological_summary
        query = select(User).where(
            User.psychological_summary == None
        )
        
        result = await session.execute(query)
        users = result.scalars().all()
        
        if not users:
            logger.info("All users already have profiles")
            return
        
        logger.info(f"Found {len(users)} users without profiles")
        
        # Базовые профили для разных типов пользователей
        default_profiles = [
            {
                'summary': 'Пользователь находится в начале пути самопознания. Проявляет интерес к духовному развитию и трансформации.',
                'streams': ['Путь Героя', 'Пробуждение']
            },
            {
                'summary': 'Активный участник сообщества. Интересуется глубинной психологией и работой с подсознанием.',
                'streams': ['Трансформация Тени', 'Прошлые Жизни']
            },
            {
                'summary': 'Ищет гармонию в отношениях и работу с эмоциональной сферой. Открыт к новому опыту.',
                'streams': ['Открытие Сердца', 'Путь Героя']
            },
            {
                'summary': 'Работает с кармическими паттернами и прошлым опытом. Стремится к освобождению от старых программ.',
                'streams': ['Прошлые Жизни', 'Трансформация Тени']
            },
            {
                'summary': 'Находится на этапе пробуждения сознания. Интересуется метафизикой и духовными практиками.',
                'streams': ['Пробуждение', 'Путь Героя']
            }
        ]
        
        updated = 0
        
        with tqdm(total=len(users), desc="Filling profiles") as pbar:
            for i, user in enumerate(users):
                try:
                    # Выбираем профиль циклически
                    profile = default_profiles[i % len(default_profiles)]
                    
                    # Обновляем пользователя
                    user.psychological_summary = profile['summary']
                    user.streams = profile['streams']
                    
                    # Обновляем markers
                    if not user.markers:
                        user.markers = {}
                    
                    user.markers['profile_updated_at'] = datetime.now().isoformat()
                    user.markers['profile_type'] = 'basic_auto_generated'
                    
                    updated += 1
                    pbar.update(1)
                    
                    # Коммитим каждые 10 пользователей
                    if updated % 10 == 0:
                        await session.commit()
                        
                except Exception as e:
                    logger.error(f"Error updating user {user.id}: {e}")
                    pbar.update(1)
        
        # Финальный коммит
        await session.commit()
        
        logger.info(f"Successfully filled {updated} profiles")


async def fill_missing_fields():
    """Заполняет отсутствующие поля у всех пользователей"""
    logger.info("Filling missing fields...")
    
    async with async_session() as session:
        query = select(User)
        result = await session.execute(query)
        users = result.scalars().all()
        
        updated = 0
        
        for user in users:
            changed = False
            
            # Заполняем markers если отсутствует
            if user.markers is None:
                user.markers = {}
                changed = True
            
            # Заполняем streams если отсутствует
            if user.streams is None:
                user.streams = ['Путь Героя']
                changed = True
            
            # Устанавливаем is_active если не установлено
            if user.is_active is None:
                user.is_active = True
                changed = True
            
            if changed:
                updated += 1
        
        await session.commit()
        logger.info(f"Updated {updated} users with missing fields")


async def show_stats():
    """Показывает статистику по профилям"""
    async with async_session() as session:
        # Всего пользователей
        result = await session.execute(select(User))
        total_users = len(result.scalars().all())
        
        # С профилями
        result = await session.execute(
            select(User).where(User.psychological_summary != None)
        )
        with_profiles = len(result.scalars().all())
        
        # Активные
        result = await session.execute(
            select(User).where(User.is_active == True)
        )
        active_users = len(result.scalars().all())
        
        logger.info(f"\n=== СТАТИСТИКА ===")
        logger.info(f"Всего пользователей: {total_users}")
        logger.info(f"С профилями: {with_profiles}")
        logger.info(f"Активных: {active_users}")
        logger.info(f"Без профилей: {total_users - with_profiles}")


async def main():
    """Главная функция"""
    await show_stats()
    await fill_missing_fields()
    await fill_basic_profiles()
    await show_stats()


if __name__ == "__main__":
    asyncio.run(main())
