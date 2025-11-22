"""
Финальная очистка markers:
1. Удаляем from_json (технический мусор)
2. Удаляем gender (дублирует колонку)
3. Удаляем streams (дублирует колонку)
4. Удаляем photo_base64 (дублирует колонку)
5. Если markers пустой - ставим NULL
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import select
from relove_bot.db.models import User
from relove_bot.db.session import async_session
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def cleanup_markers_final(dry_run: bool = True):
    """Финальная очистка markers от дублирующих данных"""
    
    logger.info(f"\n{'='*70}")
    logger.info(f"FINAL MARKERS CLEANUP {'(DRY RUN)' if dry_run else '(REAL)'}")
    logger.info(f"{'='*70}\n")
    
    stats = {
        'from_json_removed': 0,
        'gender_removed': 0,
        'streams_removed': 0,
        'photo_removed': 0,
        'markers_nullified': 0,
        'markers_kept': 0
    }
    
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.markers.isnot(None))
        )
        users = result.scalars().all()
        
        logger.info(f"Found {len(users)} users with markers\n")
        
        for user in users:
            if not user.markers:
                continue
            
            original_keys = set(user.markers.keys())
            
            # Удаляем дублирующие ключи
            keys_to_remove = {'from_json', 'gender', 'streams', 'photo_base64'}
            
            removed_keys = original_keys & keys_to_remove
            
            if removed_keys:
                # Создаем новый markers без дублирующих ключей
                new_markers = {
                    k: v for k, v in user.markers.items()
                    if k not in keys_to_remove
                }
                
                if not dry_run:
                    if new_markers:
                        user.markers = new_markers
                        stats['markers_kept'] += 1
                    else:
                        user.markers = None
                        stats['markers_nullified'] += 1
                
                # Подсчитываем что удалили
                for key in removed_keys:
                    if key == 'from_json':
                        stats['from_json_removed'] += 1
                    elif key == 'gender':
                        stats['gender_removed'] += 1
                    elif key == 'streams':
                        stats['streams_removed'] += 1
                    elif key == 'photo_base64':
                        stats['photo_removed'] += 1
                
                logger.info(
                    f"User {user.id}: "
                    f"{'Would remove' if dry_run else 'Removed'} "
                    f"{removed_keys}"
                )
        
        if not dry_run:
            await session.commit()
            logger.info("\n✅ Changes committed to database")
        else:
            logger.info("\n⚠️ DRY RUN - No changes made to database")
    
    # Статистика
    logger.info(f"\n{'='*70}")
    logger.info("STATISTICS")
    logger.info(f"{'='*70}")
    logger.info(f"Removed keys:")
    logger.info(f"  from_json: {stats['from_json_removed']}")
    logger.info(f"  gender: {stats['gender_removed']}")
    logger.info(f"  streams: {stats['streams_removed']}")
    logger.info(f"  photo_base64: {stats['photo_removed']}")
    logger.info(f"\nMarkers status:")
    logger.info(f"  Set to NULL (empty): {stats['markers_nullified']}")
    logger.info(f"  Kept (has other data): {stats['markers_kept']}")
    logger.info(f"{'='*70}\n")
    
    return stats


async def verify_cleanup():
    """Проверяет результаты очистки"""
    logger.info("\n" + "="*70)
    logger.info("VERIFICATION")
    logger.info("="*70)
    
    async with async_session() as session:
        result = await session.execute(select(User))
        users = result.scalars().all()
        
        total = len(users)
        with_markers = [u for u in users if u.markers]
        
        logger.info(f"\nTotal users: {total}")
        logger.info(f"Users with markers: {len(with_markers)}")
        logger.info(f"Users without markers: {total - len(with_markers)}")
        
        if with_markers:
            # Проверяем какие ключи остались
            from collections import Counter
            all_keys = Counter()
            
            for user in with_markers:
                for key in user.markers.keys():
                    all_keys[key] += 1
            
            logger.info(f"\nRemaining keys in markers:")
            for key, count in all_keys.most_common():
                logger.info(f"  {key}: {count}")
            
            # Проверяем, остались ли дублирующие ключи
            duplicate_keys = {'from_json', 'gender', 'streams', 'photo_base64'}
            remaining_duplicates = set(all_keys.keys()) & duplicate_keys
            
            if remaining_duplicates:
                logger.warning(f"\n⚠️ Still have duplicate keys: {remaining_duplicates}")
            else:
                logger.info(f"\n✅ No duplicate keys remaining!")
        else:
            logger.info("\n✅ All markers cleaned!")
        
        logger.info("="*70 + "\n")


async def main():
    """Главная функция"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Final cleanup of markers field"
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        default=True,
        help='Show what would be done (default)'
    )
    parser.add_argument(
        '--execute',
        action='store_true',
        help='Actually perform the cleanup'
    )
    parser.add_argument(
        '--verify',
        action='store_true',
        help='Only verify cleanup results'
    )
    
    args = parser.parse_args()
    
    print("\n" + "="*70)
    print("FINAL MARKERS CLEANUP")
    print("="*70 + "\n")
    
    if args.verify:
        await verify_cleanup()
    else:
        dry_run = not args.execute
        
        if dry_run:
            print("⚠️ DRY RUN MODE")
            print("   Use --execute to perform actual cleanup\n")
        else:
            print("⚠️ REAL CLEANUP")
            print("   Will remove: from_json, gender, streams, photo_base64\n")
            
            response = input("Continue? (yes/no): ")
            if response.lower() != 'yes':
                print("Cleanup cancelled.")
                return
        
        await cleanup_markers_final(dry_run=dry_run)
        
        if not dry_run:
            await verify_cleanup()


if __name__ == "__main__":
    asyncio.run(main())
