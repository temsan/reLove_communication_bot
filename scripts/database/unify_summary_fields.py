"""
Унификация полей саммари в БД.

ПРОБЛЕМА:
- profile_summary - дублирует psychological_summary
- Оба хранят похожую информацию
- Путаница в коде

РЕШЕНИЕ:
- Оставляем только psychological_summary (основное поле)
- Мигрируем данные из profile_summary в psychological_summary
- Удаляем колонку profile_summary из модели

ПЛАН:
1. Проверить текущее состояние
2. Мигрировать данные (если profile_summary заполнен, а psychological_summary нет)
3. Обновить код для использования только psychological_summary
4. Создать алембик миграцию для удаления колонки
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import select
from relove_bot.db.session import get_session
from relove_bot.db.models import User
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def analyze_current_state():
    """Анализирует текущее состояние полей."""
    logger.info("="*60)
    logger.info("АНАЛИЗ ТЕКУЩЕГО СОСТОЯНИЯ")
    logger.info("="*60)
    
    async with get_session() as session:
        result = await session.execute(select(User))
        users = result.scalars().all()
        
        total = len(users)
        with_profile = sum(1 for u in users if u.profile_summary)
        with_psych = sum(1 for u in users if u.psychological_summary)
        with_both = sum(1 for u in users if u.profile_summary and u.psychological_summary)
        only_profile = sum(1 for u in users if u.profile_summary and not u.psychological_summary)
        only_psych = sum(1 for u in users if u.psychological_summary and not u.profile_summary)
        
        logger.info(f"Всего пользователей: {total}")
        logger.info(f"С profile_summary: {with_profile}")
        logger.info(f"С psychological_summary: {with_psych}")
        logger.info(f"С обоими: {with_both}")
        logger.info(f"Только profile_summary: {only_profile}")
        logger.info(f"Только psychological_summary: {only_psych}")
        
        return {
            'total': total,
            'with_profile': with_profile,
            'with_psych': with_psych,
            'with_both': with_both,
            'only_profile': only_profile,
            'only_psych': only_psych
        }


async def migrate_data(dry_run: bool = True):
    """
    Мигрирует данные из profile_summary в psychological_summary.
    
    Логика:
    - Если есть только profile_summary → копируем в psychological_summary
    - Если есть оба → оставляем psychological_summary (более полное)
    - Если есть только psychological_summary → ничего не делаем
    """
    logger.info("\n" + "="*60)
    logger.info(f"МИГРАЦИЯ ДАННЫХ {'(DRY RUN)' if dry_run else ''}")
    logger.info("="*60)
    
    async with get_session() as session:
        result = await session.execute(select(User))
        users = result.scalars().all()
        
        migrated = 0
        skipped = 0
        
        for user in users:
            # Случай 1: Есть только profile_summary
            if user.profile_summary and not user.psychological_summary:
                logger.info(
                    f"User {user.id} (@{user.username}): "
                    f"Migrating profile_summary → psychological_summary"
                )
                
                if not dry_run:
                    user.psychological_summary = user.profile_summary
                
                migrated += 1
            
            # Случай 2: Есть оба - оставляем psychological_summary
            elif user.profile_summary and user.psychological_summary:
                logger.debug(
                    f"User {user.id} (@{user.username}): "
                    f"Both exist, keeping psychological_summary"
                )
                skipped += 1
            
            # Случай 3: Есть только psychological_summary - ничего не делаем
            elif user.psychological_summary:
                skipped += 1
        
        if not dry_run:
            await session.commit()
            logger.info("\n✅ Изменения сохранены в БД")
        else:
            logger.info("\n⚠️ DRY RUN - изменения НЕ сохранены")
        
        logger.info(f"\nМигрировано: {migrated}")
        logger.info(f"Пропущено: {skipped}")
        
        return {'migrated': migrated, 'skipped': skipped}


async def verify_migration():
    """Проверяет результаты миграции."""
    logger.info("\n" + "="*60)
    logger.info("ПРОВЕРКА РЕЗУЛЬТАТОВ")
    logger.info("="*60)
    
    async with get_session() as session:
        result = await session.execute(select(User))
        users = result.scalars().all()
        
        only_profile = [u for u in users if u.profile_summary and not u.psychological_summary]
        
        if only_profile:
            logger.warning(f"⚠️ Найдено {len(only_profile)} пользователей только с profile_summary!")
            for u in only_profile[:5]:
                logger.warning(f"  - User {u.id} (@{u.username})")
        else:
            logger.info("✅ Все пользователи с profile_summary имеют psychological_summary")
        
        return len(only_profile) == 0


async def main():
    """Главная функция."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Унификация полей саммари"
    )
    parser.add_argument(
        '--execute',
        action='store_true',
        help='Выполнить миграцию (по умолчанию dry-run)'
    )
    
    args = parser.parse_args()
    
    # Анализ
    await analyze_current_state()
    
    # Миграция
    await migrate_data(dry_run=not args.execute)
    
    # Проверка
    if args.execute:
        success = await verify_migration()
        if success:
            logger.info("\n" + "="*60)
            logger.info("✅ МИГРАЦИЯ ЗАВЕРШЕНА УСПЕШНО")
            logger.info("="*60)
            logger.info("\nСледующие шаги:")
            logger.info("1. Обновить код для использования только psychological_summary")
            logger.info("2. Создать алембик миграцию для удаления колонки profile_summary")
            logger.info("3. Запустить алембик миграцию")
        else:
            logger.error("\n❌ МИГРАЦИЯ ЗАВЕРШЕНА С ОШИБКАМИ")


if __name__ == "__main__":
    asyncio.run(main())
