"""
Безопасная миграция данных из markers в отдельные колонки.
НЕ затирает существующие заполненные значения!
"""
import asyncio
import sys
from pathlib import Path
import base64

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import select
from relove_bot.db.models import User, GenderEnum
from relove_bot.db.session import async_session
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def migrate_markers_safe(dry_run: bool = True):
    """
    Безопасная миграция markers в колонки.
    
    Правила:
    1. НЕ затирать существующие значения в колонках
    2. Переносить только если колонка пустая
    3. Показывать что будет сделано
    """
    
    logger.info(f"\n{'='*70}")
    logger.info(f"SAFE MIGRATION {'(DRY RUN)' if dry_run else '(REAL)'}")
    logger.info(f"{'='*70}\n")
    
    stats = {
        'gender_migrated': 0,
        'gender_skipped': 0,
        'streams_migrated': 0,
        'streams_skipped': 0,
        'photo_migrated': 0,
        'photo_skipped': 0,
        'photo_errors': 0,
        'markers_cleaned': 0
    }
    
    async with async_session() as session:
        # Получаем пользователей с markers
        result = await session.execute(
            select(User).where(User.markers.isnot(None))
        )
        users = result.scalars().all()
        
        logger.info(f"Found {len(users)} users with markers\n")
        
        for user in users:
            user_updated = False
            
            # Пропускаем если markers пустой
            if not user.markers:
                continue
            
            # 1. Миграция gender
            if 'gender' in user.markers:
                marker_gender = user.markers['gender']
                
                # Проверяем, не затрем ли существующее значение
                if user.gender is None:
                    # Колонка пустая - можно мигрировать
                    try:
                        if marker_gender == 'male':
                            new_gender = GenderEnum.male
                        elif marker_gender == 'female':
                            new_gender = GenderEnum.female
                        else:
                            new_gender = None  # unknown не мигрируем
                        
                        if new_gender:
                            if not dry_run:
                                user.gender = new_gender
                            logger.info(
                                f"User {user.id}: "
                                f"{'Would migrate' if dry_run else 'Migrated'} "
                                f"gender '{marker_gender}' -> {new_gender.value}"
                            )
                            stats['gender_migrated'] += 1
                            user_updated = True
                    except Exception as e:
                        logger.error(f"User {user.id}: Error migrating gender: {e}")
                else:
                    # Колонка заполнена - НЕ трогаем!
                    logger.debug(
                        f"User {user.id}: gender already set to {user.gender.value}, "
                        f"skipping markers['gender']={marker_gender}"
                    )
                    stats['gender_skipped'] += 1
            
            # 2. Миграция streams
            if 'streams' in user.markers:
                marker_streams = user.markers['streams']
                
                # Проверяем, не затрем ли существующее значение
                if not user.streams or len(user.streams) == 0:
                    # Колонка пустая - можно мигрировать
                    if marker_streams and len(marker_streams) > 0:
                        if not dry_run:
                            user.streams = marker_streams
                        logger.info(
                            f"User {user.id}: "
                            f"{'Would migrate' if dry_run else 'Migrated'} "
                            f"streams {marker_streams}"
                        )
                        stats['streams_migrated'] += 1
                        user_updated = True
                else:
                    # Колонка заполнена - НЕ трогаем!
                    logger.debug(
                        f"User {user.id}: streams already set to {user.streams}, "
                        f"skipping markers['streams']={marker_streams}"
                    )
                    stats['streams_skipped'] += 1
            
            # 3. Миграция photo_base64
            if 'photo_base64' in user.markers:
                marker_photo = user.markers['photo_base64']
                
                # Проверяем, не затрем ли существующее значение
                if user.photo_jpeg is None:
                    # Колонка пустая - можно мигрировать
                    try:
                        # Конвертируем base64 в binary
                        photo_binary = base64.b64decode(marker_photo)
                        
                        if not dry_run:
                            user.photo_jpeg = photo_binary
                        
                        logger.info(
                            f"User {user.id}: "
                            f"{'Would migrate' if dry_run else 'Migrated'} "
                            f"photo ({len(photo_binary)} bytes)"
                        )
                        stats['photo_migrated'] += 1
                        user_updated = True
                    except Exception as e:
                        logger.error(f"User {user.id}: Error converting photo: {e}")
                        stats['photo_errors'] += 1
                else:
                    # Колонка заполнена - НЕ трогаем!
                    logger.debug(
                        f"User {user.id}: photo_jpeg already set "
                        f"({len(user.photo_jpeg)} bytes), skipping"
                    )
                    stats['photo_skipped'] += 1
            
            # 4. Очищаем markers от мигрированных данных
            if user_updated and not dry_run:
                # Создаем новый словарь без мигрированных ключей
                new_markers = {
                    k: v for k, v in user.markers.items()
                    if k not in ['gender', 'streams', 'photo_base64']
                }
                
                # Оставляем только полезные ключи (from_json можно оставить)
                if new_markers:
                    user.markers = new_markers
                else:
                    user.markers = None
                
                stats['markers_cleaned'] += 1
        
        # Сохраняем изменения
        if not dry_run:
            await session.commit()
            logger.info("\n✅ Changes committed to database")
        else:
            logger.info("\n⚠️ DRY RUN - No changes made to database")
    
    # Выводим статистику
    logger.info(f"\n{'='*70}")
    logger.info("MIGRATION STATISTICS")
    logger.info(f"{'='*70}")
    logger.info(f"Gender:")
    logger.info(f"  Migrated: {stats['gender_migrated']}")
    logger.info(f"  Skipped (already set): {stats['gender_skipped']}")
    logger.info(f"\nStreams:")
    logger.info(f"  Migrated: {stats['streams_migrated']}")
    logger.info(f"  Skipped (already set): {stats['streams_skipped']}")
    logger.info(f"\nPhoto:")
    logger.info(f"  Migrated: {stats['photo_migrated']}")
    logger.info(f"  Skipped (already set): {stats['photo_skipped']}")
    logger.info(f"  Errors: {stats['photo_errors']}")
    logger.info(f"\nMarkers cleaned: {stats['markers_cleaned']}")
    logger.info(f"{'='*70}\n")
    
    return stats


async def verify_migration():
    """Проверяет результаты миграции"""
    logger.info("\n" + "="*70)
    logger.info("VERIFICATION")
    logger.info("="*70)
    
    async with async_session() as session:
        result = await session.execute(select(User))
        users = result.scalars().all()
        
        # Проверяем колонки
        with_gender = [u for u in users if u.gender]
        with_streams = [u for u in users if u.streams and len(u.streams) > 0]
        with_photo = [u for u in users if u.photo_jpeg]
        
        logger.info(f"\nUsers with gender: {len(with_gender)}")
        logger.info(f"Users with streams: {len(with_streams)}")
        logger.info(f"Users with photo: {len(with_photo)}")
        
        # Проверяем markers
        with_markers = [u for u in users if u.markers]
        
        if with_markers:
            # Проверяем, остались ли старые ключи
            remaining_gender = [
                u for u in with_markers 
                if 'gender' in u.markers
            ]
            remaining_streams = [
                u for u in with_markers 
                if 'streams' in u.markers
            ]
            remaining_photo = [
                u for u in with_markers 
                if 'photo_base64' in u.markers
            ]
            
            logger.info(f"\nRemaining in markers:")
            logger.info(f"  gender: {len(remaining_gender)}")
            logger.info(f"  streams: {len(remaining_streams)}")
            logger.info(f"  photo_base64: {len(remaining_photo)}")
            
            if remaining_gender == 0 and remaining_streams == 0 and remaining_photo == 0:
                logger.info("\n✅ All data migrated successfully!")
            else:
                logger.warning("\n⚠️ Some data still in markers (probably skipped due to existing values)")
        
        logger.info("="*70 + "\n")


async def main():
    """Главная функция"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Safe migration from markers to columns"
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        default=True,
        help='Show what would be done without making changes (default)'
    )
    parser.add_argument(
        '--execute',
        action='store_true',
        help='Actually perform the migration'
    )
    parser.add_argument(
        '--verify',
        action='store_true',
        help='Only verify migration results'
    )
    
    args = parser.parse_args()
    
    print("\n" + "="*70)
    print("SAFE MARKERS MIGRATION")
    print("="*70 + "\n")
    
    if args.verify:
        # Только проверка
        await verify_migration()
    else:
        # Миграция
        dry_run = not args.execute
        
        if dry_run:
            print("⚠️ DRY RUN MODE - No changes will be made")
            print("   Use --execute to perform actual migration\n")
        else:
            print("⚠️ REAL MIGRATION - Changes will be made!")
            print("   Make sure you have a database backup!\n")
            
            # Подтверждение
            response = input("Continue? (yes/no): ")
            if response.lower() != 'yes':
                print("Migration cancelled.")
                return
        
        await migrate_markers_safe(dry_run=dry_run)
        
        # Проверка после миграции
        if not dry_run:
            await verify_migration()
        else:
            print("\n💡 To perform actual migration, run:")
            print("   python scripts/database/migrate_markers_safe.py --execute")


if __name__ == "__main__":
    asyncio.run(main())
