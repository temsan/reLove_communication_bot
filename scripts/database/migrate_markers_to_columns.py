"""
Скрипт для миграции данных из markers в отдельные колонки.
Переносит markers['summary'] -> profile_summary
Переносит markers['relove_context'] -> psychological_summary
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import select, update
from relove_bot.db.models import User
from relove_bot.db.session import async_session
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def analyze_current_state():
    """Анализирует текущее состояние данных"""
    logger.info("Analyzing current data state...")
    
    async with async_session() as session:
        # Всего пользователей
        result = await session.execute(select(User))
        all_users = result.scalars().all()
        total = len(all_users)
        
        # С markers
        users_with_markers = [u for u in all_users if u.markers]
        
        # С markers['summary']
        users_with_markers_summary = [
            u for u in all_users 
            if u.markers and u.markers.get('summary')
        ]
        
        # С markers['relove_context']
        users_with_markers_context = [
            u for u in all_users 
            if u.markers and u.markers.get('relove_context')
        ]
        
        # С profile_summary
        users_with_profile_summary = [
            u for u in all_users 
            if u.profile_summary
        ]
        
        # С psychological_summary
        users_with_psych_summary = [
            u for u in all_users 
            if u.psychological_summary
        ]
        
        logger.info(f"\n{'='*60}")
        logger.info("CURRENT STATE")
        logger.info(f"{'='*60}")
        logger.info(f"Total users: {total}")
        logger.info(f"Users with markers: {len(users_with_markers)}")
        logger.info(f"Users with markers['summary']: {len(users_with_markers_summary)}")
        logger.info(f"Users with markers['relove_context']: {len(users_with_markers_context)}")
        logger.info(f"Users with profile_summary: {len(users_with_profile_summary)}")
        logger.info(f"Users with psychological_summary: {len(users_with_psych_summary)}")
        logger.info(f"{'='*60}\n")
        
        return {
            'total': total,
            'with_markers': len(users_with_markers),
            'with_markers_summary': len(users_with_markers_summary),
            'with_markers_context': len(users_with_markers_context),
            'with_profile_summary': len(users_with_profile_summary),
            'with_psych_summary': len(users_with_psych_summary)
        }


async def migrate_data(dry_run: bool = True):
    """
    Мигрирует данные из markers в отдельные колонки.
    
    Args:
        dry_run: Если True, только показывает что будет сделано
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"MIGRATION {'(DRY RUN)' if dry_run else '(REAL)'}")
    logger.info(f"{'='*60}\n")
    
    stats = {
        'migrated_summary': 0,
        'migrated_context': 0,
        'cleaned_markers': 0,
        'errors': 0
    }
    
    async with async_session() as session:
        # Получаем всех пользователей с markers
        result = await session.execute(
            select(User).where(User.markers.isnot(None))
        )
        users = result.scalars().all()
        
        logger.info(f"Found {len(users)} users with markers")
        
        for user in users:
            try:
                updated = False
                
                # Миграция markers['summary'] -> profile_summary
                if user.markers.get('summary'):
                    summary = user.markers['summary']
                    
                    # Проверяем, не затрем ли существующие данные
                    if user.profile_summary and user.profile_summary != summary:
                        logger.warning(
                            f"User {user.id}: profile_summary already exists and differs! "
                            f"Keeping existing."
                        )
                    else:
                        if not dry_run:
                            user.profile_summary = summary
                        logger.info(
                            f"User {user.id}: "
                            f"{'Would migrate' if dry_run else 'Migrated'} "
                            f"markers['summary'] -> profile_summary"
                        )
                        stats['migrated_summary'] += 1
                        updated = True
                
                # Миграция markers['relove_context'] -> psychological_summary
                if user.markers.get('relove_context'):
                    context = user.markers['relove_context']
                    
                    # Проверяем, не затрем ли существующие данные
                    if user.psychological_summary and user.psychological_summary != context:
                        logger.warning(
                            f"User {user.id}: psychological_summary already exists and differs! "
                            f"Keeping existing."
                        )
                    else:
                        if not dry_run:
                            user.psychological_summary = context
                        logger.info(
                            f"User {user.id}: "
                            f"{'Would migrate' if dry_run else 'Migrated'} "
                            f"markers['relove_context'] -> psychological_summary"
                        )
                        stats['migrated_context'] += 1
                        updated = True
                
                # Очищаем markers от мигрированных данных
                if updated and not dry_run:
                    # Создаем новый словарь без мигрированных ключей
                    new_markers = {
                        k: v for k, v in user.markers.items()
                        if k not in ['summary', 'relove_context']
                    }
                    user.markers = new_markers if new_markers else None
                    stats['cleaned_markers'] += 1
                    
                    logger.info(f"User {user.id}: Cleaned markers")
                
            except Exception as e:
                logger.error(f"Error migrating user {user.id}: {e}")
                stats['errors'] += 1
        
        # Сохраняем изменения
        if not dry_run:
            await session.commit()
            logger.info("\n✅ Changes committed to database")
        else:
            logger.info("\n⚠️ DRY RUN - No changes made to database")
    
    # Выводим статистику
    logger.info(f"\n{'='*60}")
    logger.info("MIGRATION STATISTICS")
    logger.info(f"{'='*60}")
    logger.info(f"Migrated summary: {stats['migrated_summary']}")
    logger.info(f"Migrated context: {stats['migrated_context']}")
    logger.info(f"Cleaned markers: {stats['cleaned_markers']}")
    logger.info(f"Errors: {stats['errors']}")
    logger.info(f"{'='*60}\n")
    
    return stats


async def verify_migration():
    """Проверяет результаты миграции"""
    logger.info("\n" + "="*60)
    logger.info("VERIFICATION")
    logger.info("="*60)
    
    async with async_session() as session:
        # Проверяем, остались ли markers['summary'] или markers['relove_context']
        result = await session.execute(select(User))
        users = result.scalars().all()
        
        remaining_summary = [
            u for u in users 
            if u.markers and u.markers.get('summary')
        ]
        
        remaining_context = [
            u for u in users 
            if u.markers and u.markers.get('relove_context')
        ]
        
        if remaining_summary:
            logger.warning(f"⚠️ Still {len(remaining_summary)} users with markers['summary']")
        else:
            logger.info("✅ No users with markers['summary']")
        
        if remaining_context:
            logger.warning(f"⚠️ Still {len(remaining_context)} users with markers['relove_context']")
        else:
            logger.info("✅ No users with markers['relove_context']")
        
        # Проверяем, что данные перенесены
        with_profile_summary = [u for u in users if u.profile_summary]
        with_psych_summary = [u for u in users if u.psychological_summary]
        
        logger.info(f"\n✅ Users with profile_summary: {len(with_profile_summary)}")
        logger.info(f"✅ Users with psychological_summary: {len(with_psych_summary)}")
        
        logger.info("="*60 + "\n")


async def main():
    """Главная функция"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Migrate data from markers to separate columns"
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making changes'
    )
    parser.add_argument(
        '--verify',
        action='store_true',
        help='Only verify migration results'
    )
    
    args = parser.parse_args()
    
    print("\n" + "="*60)
    print("MARKERS TO COLUMNS MIGRATION")
    print("="*60 + "\n")
    
    # Анализ текущего состояния
    await analyze_current_state()
    
    if args.verify:
        # Только проверка
        await verify_migration()
    else:
        # Миграция
        await migrate_data(dry_run=args.dry_run)
        
        # Проверка после миграции
        if not args.dry_run:
            await verify_migration()
        else:
            print("\n💡 To perform actual migration, run:")
            print("   python scripts/database/migrate_markers_to_columns.py")
            print("\n⚠️ Make sure to backup your database first!")


if __name__ == "__main__":
    asyncio.run(main())
