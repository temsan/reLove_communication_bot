"""
Очистка gender от "unknown" - заменяем на "female" (по умолчанию).
Обновляет БД и показывает где еще нужно обновить код.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import select, update
from relove_bot.db.models import User, GenderEnum
from relove_bot.db.session import async_session
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def cleanup_unknown_gender(dry_run: bool = True):
    """
    Заменяет все "unknown" gender на "female".
    Также заменяет NULL на "female".
    """
    
    logger.info(f"\n{'='*70}")
    logger.info(f"CLEANUP UNKNOWN GENDER {'(DRY RUN)' if dry_run else '(REAL)'}")
    logger.info(f"{'='*70}\n")
    
    stats = {
        'null_to_female': 0,
        'unknown_to_female': 0,
        'markers_cleaned': 0,
        'total_female': 0,
        'total_male': 0
    }
    
    async with async_session() as session:
        # Получаем всех пользователей
        result = await session.execute(select(User))
        users = result.scalars().all()
        
        logger.info(f"Found {len(users)} users\n")
        
        for user in users:
            updated = False
            
            # 1. Заменяем NULL на female
            if user.gender is None:
                if not dry_run:
                    user.gender = GenderEnum.female
                logger.info(
                    f"User {user.id} (@{user.username}): "
                    f"{'Would set' if dry_run else 'Set'} "
                    f"NULL -> female"
                )
                stats['null_to_female'] += 1
                updated = True
            
            # 2. Очищаем markers['gender'] = 'unknown'
            if user.markers and 'gender' in user.markers:
                marker_gender = user.markers['gender']
                
                if marker_gender == 'unknown':
                    # Удаляем из markers
                    if not dry_run:
                        new_markers = {
                            k: v for k, v in user.markers.items()
                            if k != 'gender'
                        }
                        user.markers = new_markers if new_markers else None
                    
                    logger.info(
                        f"User {user.id} (@{user.username}): "
                        f"{'Would remove' if dry_run else 'Removed'} "
                        f"markers['gender']='unknown'"
                    )
                    stats['markers_cleaned'] += 1
                    updated = True
            
            # Подсчитываем итоговое распределение
            if not dry_run or not updated:
                final_gender = user.gender if not updated else GenderEnum.female
                if final_gender == GenderEnum.female:
                    stats['total_female'] += 1
                elif final_gender == GenderEnum.male:
                    stats['total_male'] += 1
        
        # Сохраняем изменения
        if not dry_run:
            await session.commit()
            logger.info("\n✅ Changes committed to database")
        else:
            logger.info("\n⚠️ DRY RUN - No changes made to database")
    
    # Выводим статистику
    logger.info(f"\n{'='*70}")
    logger.info("STATISTICS")
    logger.info(f"{'='*70}")
    logger.info(f"NULL -> female: {stats['null_to_female']}")
    logger.info(f"markers['gender']='unknown' removed: {stats['markers_cleaned']}")
    logger.info(f"\nFinal distribution:")
    logger.info(f"  Female: {stats['total_female']}")
    logger.info(f"  Male: {stats['total_male']}")
    logger.info(f"{'='*70}\n")
    
    return stats


def find_unknown_in_code():
    """Находит использование 'unknown' в коде"""
    logger.info("\n" + "="*70)
    logger.info("SEARCHING FOR 'unknown' IN CODE")
    logger.info("="*70 + "\n")
    
    # Файлы для проверки
    files_to_check = [
        'relove_bot/db/models.py',
        'relove_bot/handlers/common.py',
        'relove_bot/services/profile_service.py',
        'scripts/profiles/fill_profiles_from_channels.py',
        'scripts/database/migrate_markers_safe.py'
    ]
    
    found_files = []
    
    for file_path in files_to_check:
        path = Path(file_path)
        if path.exists():
            content = path.read_text(encoding='utf-8')
            
            # Ищем 'unknown' (case-insensitive)
            if 'unknown' in content.lower():
                found_files.append(file_path)
                
                # Показываем строки с 'unknown'
                lines = content.split('\n')
                for i, line in enumerate(lines, 1):
                    if 'unknown' in line.lower():
                        logger.info(f"{file_path}:{i}")
                        logger.info(f"  {line.strip()}")
    
    if found_files:
        logger.info(f"\n⚠️ Found 'unknown' in {len(found_files)} files")
        logger.info("   These files need to be updated manually")
    else:
        logger.info("✅ No 'unknown' found in code")
    
    logger.info("="*70 + "\n")


async def main():
    """Главная функция"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Cleanup unknown gender values"
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
        help='Actually perform the cleanup'
    )
    parser.add_argument(
        '--check-code',
        action='store_true',
        help='Check code for unknown gender usage'
    )
    
    args = parser.parse_args()
    
    print("\n" + "="*70)
    print("CLEANUP UNKNOWN GENDER")
    print("="*70 + "\n")
    
    if args.check_code:
        # Проверка кода
        find_unknown_in_code()
    else:
        # Очистка БД
        dry_run = not args.execute
        
        if dry_run:
            print("⚠️ DRY RUN MODE - No changes will be made")
            print("   Use --execute to perform actual cleanup\n")
        else:
            print("⚠️ REAL CLEANUP - Changes will be made!")
            print("   All NULL and 'unknown' will be replaced with 'female'\n")
            
            response = input("Continue? (yes/no): ")
            if response.lower() != 'yes':
                print("Cleanup cancelled.")
                return
        
        await cleanup_unknown_gender(dry_run=dry_run)
        
        if not dry_run:
            print("\n💡 Now check code for 'unknown' usage:")
            print("   python scripts/database/cleanup_unknown_gender.py --check-code")


if __name__ == "__main__":
    asyncio.run(main())
