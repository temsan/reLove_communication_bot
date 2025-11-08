"""
Скрипт для массового обновления профилей пользователей.
Использует ProfileRotationService для актуализации данных.

Использование:
    python scripts/fill_profiles.py --all                    # Обновить все активные профили
    python scripts/fill_profiles.py --user-id 123456         # Обновить конкретного пользователя
    python scripts/fill_profiles.py --batch-size 20          # Изменить размер пачки
"""
import asyncio
import logging
import sys
import argparse
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from tqdm import tqdm

from relove_bot.db.models import User
from relove_bot.db.session import async_session
from relove_bot.services.profile_rotation_service import ProfileRotationService

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/fill_profiles.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


async def update_all_profiles(batch_size: int = 10):
    """Обновляет все активные профили"""
    logger.info("Starting mass profile update...")
    
    async with async_session() as session:
        service = ProfileRotationService(session)
        
        # Получаем пользователей для обновления
        users = await service.get_users_for_rotation()
        
        if not users:
            logger.info("No users found for update")
            return
        
        logger.info(f"Found {len(users)} users to update")
        
        # Обрабатываем с прогресс-баром
        with tqdm(total=len(users), desc="Updating profiles") as pbar:
            for i in range(0, len(users), batch_size):
                batch = users[i:i + batch_size]
                
                for user in batch:
                    try:
                        await service.update_user_profile(user)
                        pbar.update(1)
                    except Exception as e:
                        logger.error(f"Error updating user {user.id}: {e}")
                        pbar.update(1)
                
                # Пауза между пачками
                if i + batch_size < len(users):
                    await asyncio.sleep(5)
        
        # Выводим статистику
        logger.info(
            f"Update completed: "
            f"processed={service.stats['processed']}, "
            f"updated={service.stats['updated']}, "
            f"errors={service.stats['errors']}, "
            f"skipped={service.stats['skipped']}"
        )


async def update_user_profile(user_id: int):
    """Обновляет профиль конкретного пользователя"""
    logger.info(f"Updating profile for user {user_id}...")
    
    async with async_session() as session:
        # Получаем пользователя
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            logger.error(f"User {user_id} not found")
            return
        
        # Обновляем профиль
        service = ProfileRotationService(session)
        
        try:
            await service.update_user_profile(user)
            logger.info(f"Successfully updated profile for user {user_id}")
        except Exception as e:
            logger.error(f"Error updating user {user_id}: {e}")


def main():
    """Главная функция"""
    parser = argparse.ArgumentParser(
        description="Массовое обновление профилей пользователей"
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Обновить все активные профили'
    )
    parser.add_argument(
        '--user-id',
        type=int,
        help='ID конкретного пользователя для обновления'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=10,
        help='Размер пачки для обработки (по умолчанию 10)'
    )
    
    args = parser.parse_args()
    
    if args.all:
        asyncio.run(update_all_profiles(batch_size=args.batch_size))
    elif args.user_id:
        asyncio.run(update_user_profile(args.user_id))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
