"""
Обновление конкретного пользователя по username.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import select
from relove_bot.db.session import get_session
from relove_bot.db.models import User
from scripts.profiles.fill_profiles_from_channels import ChannelProfileFiller
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/update_single_user.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


async def find_and_update_user(username: str):
    """Находит и обновляет пользователя по username."""
    
    print("\n" + "="*80)
    print(f"ПОИСК И ОБНОВЛЕНИЕ ПОЛЬЗОВАТЕЛЯ: @{username}")
    print("="*80 + "\n")
    
    # Ищем пользователя в БД
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.username == username)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            logger.error(f"❌ Пользователь @{username} не найден в БД!")
            return
        
        logger.info(f"✅ Найден пользователь:")
        logger.info(f"   ID: {user.id}")
        logger.info(f"   Username: @{user.username}")
        logger.info(f"   Имя: {user.first_name} {user.last_name or ''}")
        logger.info(f"   Пол: {user.gender.value if user.gender else 'N/A'}")
        
        # Состояние ДО
        print("\n" + "-"*80)
        print("СОСТОЯНИЕ ДО ОБНОВЛЕНИЯ:")
        print("-"*80)
        print(f"📋 Profile Summary: {user.profile_summary[:100] + '...' if user.profile_summary and len(user.profile_summary) > 100 else user.profile_summary or 'N/A'}")
        print(f"🧠 Psychological Summary: {user.psychological_summary[:100] + '...' if user.psychological_summary and len(user.psychological_summary) > 100 else user.psychological_summary or 'N/A'}")
        print(f"🌀 Streams: {', '.join(user.streams) if user.streams else 'N/A'}")
        
        # Проверяем, нужно ли обновление
        needs_update = False
        
        if not user.profile_summary:
            logger.info("\n📝 profile_summary пуст - нужно заполнить")
            needs_update = True
        
        if not user.psychological_summary:
            logger.info("📝 psychological_summary пуст - нужно заполнить")
            needs_update = True
        
        if not needs_update:
            logger.info("\n✅ Все поля уже заполнены, обновление не требуется")
            return
        
        # Обновляем профиль
        logger.info("\n🔄 Запускаем заполнение профиля...")
        
        filler = ChannelProfileFiller()
        await filler.fill_user_profile(user, session)
        
        await session.commit()
        
        # Обновляем данные
        await session.refresh(user)
        
        # Состояние ПОСЛЕ
        print("\n" + "-"*80)
        print("СОСТОЯНИЕ ПОСЛЕ ОБНОВЛЕНИЯ:")
        print("-"*80)
        print(f"📋 Profile Summary: {user.profile_summary[:100] + '...' if user.profile_summary and len(user.profile_summary) > 100 else user.profile_summary or 'N/A'}")
        print(f"🧠 Psychological Summary: {user.psychological_summary[:100] + '...' if user.psychological_summary and len(user.psychological_summary) > 100 else user.psychological_summary or 'N/A'}")
        print(f"🌀 Streams: {', '.join(user.streams) if user.streams else 'N/A'}")
        
        print("\n" + "="*80)
        print("✅ ОБНОВЛЕНИЕ ЗАВЕРШЕНО")
        print("="*80 + "\n")


async def main():
    """Главная функция."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Update single user by username"
    )
    parser.add_argument(
        'username',
        type=str,
        help='Username (without @)'
    )
    
    args = parser.parse_args()
    
    await find_and_update_user(args.username)


if __name__ == "__main__":
    asyncio.run(main())
