"""
Скрипт для проверки и перезаполнения профилей в старом формате.
Находит профили в JSON формате и перезаполняет их.
"""
import asyncio
import logging
import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import select
from relove_bot.db.session import async_session
from relove_bot.db.models import User

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def is_old_format(profile: str) -> bool:
    """Проверяет, является ли профиль старым форматом."""
    if not profile:
        return False
    
    profile = profile.strip()
    
    # Проверка на JSON формат
    if profile.startswith('{') or profile.startswith('['):
        return True
    
    # Проверка на валидность JSON
    try:
        json.loads(profile)
        return True
    except (json.JSONDecodeError, TypeError):
        pass
    
    # Проверка на ключевые слова старого формата
    old_format_keywords = [
        'forensic_analysis',
        'psychological_analysis',
        'cognitive_analysis',
        'behavioral_analysis',
        'complex_analysis',
        'defense_mechanisms',
        'manipulation_patterns'
    ]
    
    return any(keyword in profile for keyword in old_format_keywords)


async def check_old_format_profiles():
    """Проверяет, сколько профилей в старом формате."""
    logger.info("Checking for old format profiles...")
    
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.profile.isnot(None))
        )
        users = result.scalars().all()
        
        total = len(users)
        old_format_count = 0
        empty_count = 0
        valid_count = 0
        
        old_format_users = []
        
        for user in users:
            if not user.profile:
                empty_count += 1
            elif is_old_format(user.profile):
                old_format_count += 1
                old_format_users.append(user)
            else:
                valid_count += 1
        
        logger.info(f"\n{'='*60}")
        logger.info("PROFILE FORMAT STATISTICS")
        logger.info(f"{'='*60}")
        logger.info(f"Total users with profile field: {total}")
        logger.info(f"Empty profiles: {empty_count}")
        logger.info(f"Old format (JSON): {old_format_count}")
        logger.info(f"Valid format (text): {valid_count}")
        logger.info(f"{'='*60}")
        
        if old_format_count > 0:
            logger.info(f"\n⚠️ Found {old_format_count} profiles in old format")
            logger.info("\nExamples (first 5):")
            for user in old_format_users[:5]:
                logger.info(f"\nUser {user.id} (@{user.username}):")
                logger.info(f"  Profile (first 200 chars): {user.profile[:200]}...")
        
        return old_format_users


async def mark_for_refill(dry_run: bool = True):
    """
    Помечает профили в старом формате для перезаполнения.
    Очищает поле profile, чтобы скрипт fill_profiles_from_channels.py их перезаполнил.
    """
    old_format_users = await check_old_format_profiles()
    
    if not old_format_users:
        logger.info("\n✅ No profiles in old format found")
        return
    
    logger.info(f"\n{'='*60}")
    if dry_run:
        logger.info("DRY RUN MODE - No changes will be made")
    else:
        logger.info("MARKING PROFILES FOR REFILL")
    logger.info(f"{'='*60}")
    
    async with async_session() as session:
        marked = 0
        
        for user in old_format_users:
            if dry_run:
                logger.info(f"Would mark user {user.id} (@{user.username}) for refill")
            else:
                # Очищаем профиль, чтобы он был перезаполнен
                user.profile = None
                marked += 1
                logger.info(f"Marked user {user.id} (@{user.username}) for refill")
        
        if not dry_run:
            await session.commit()
            logger.info(f"\n✅ Marked {marked} profiles for refill")
            logger.info("\nNext step: Run fill_profiles_from_channels.py to refill")
        else:
            logger.info(f"\n💡 Would mark {len(old_format_users)} profiles for refill")
            logger.info("\nTo actually mark them, run with --execute flag")


async def main():
    """Главная функция."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Check and refill old format profiles"
    )
    parser.add_argument(
        '--check',
        action='store_true',
        help='Only check for old format profiles'
    )
    parser.add_argument(
        '--mark',
        action='store_true',
        help='Mark old format profiles for refill (dry run)'
    )
    parser.add_argument(
        '--execute',
        action='store_true',
        help='Actually mark profiles for refill (not dry run)'
    )
    
    args = parser.parse_args()
    
    if args.check:
        await check_old_format_profiles()
    elif args.mark or args.execute:
        await mark_for_refill(dry_run=not args.execute)
    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())
