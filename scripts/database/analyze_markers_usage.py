"""
Анализ использования поля markers в таблице users.
Показывает что именно хранится и нужна ли эта колонка.
"""
import asyncio
import sys
from pathlib import Path
from collections import Counter
from typing import Dict, Any

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import select
from relove_bot.db.models import User
from relove_bot.db.session import async_session
import logging
import json

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def analyze_markers():
    """Анализирует содержимое markers"""
    logger.info("Analyzing markers field usage...")
    
    async with async_session() as session:
        # Получаем всех пользователей
        result = await session.execute(select(User))
        all_users = result.scalars().all()
        
        total = len(all_users)
        with_markers = [u for u in all_users if u.markers]
        
        logger.info(f"\n{'='*70}")
        logger.info("BASIC STATISTICS")
        logger.info(f"{'='*70}")
        logger.info(f"Total users: {total}")
        logger.info(f"Users with markers: {len(with_markers)}")
        logger.info(f"Users without markers: {total - len(with_markers)}")
        
        if not with_markers:
            logger.info("No users with markers!")
            return
        
        # Анализируем ключи в markers
        all_keys = Counter()
        key_examples = {}
        
        for user in with_markers:
            for key in user.markers.keys():
                all_keys[key] += 1
                
                # Сохраняем примеры значений
                if key not in key_examples:
                    key_examples[key] = []
                
                if len(key_examples[key]) < 3:
                    value = user.markers[key]
                    # Обрезаем длинные значения
                    if isinstance(value, str) and len(value) > 100:
                        value = value[:100] + "..."
                    key_examples[key].append({
                        'user_id': user.id,
                        'value': value,
                        'type': type(value).__name__
                    })
        
        # Выводим статистику по ключам
        logger.info(f"\n{'='*70}")
        logger.info("MARKERS KEYS STATISTICS")
        logger.info(f"{'='*70}")
        logger.info(f"Unique keys found: {len(all_keys)}")
        logger.info(f"\nKey usage frequency:")
        
        for key, count in all_keys.most_common():
            percentage = (count / len(with_markers)) * 100
            logger.info(f"\n  {key}:")
            logger.info(f"    Count: {count} ({percentage:.1f}% of users with markers)")
            
            # Показываем примеры
            if key in key_examples:
                logger.info(f"    Examples:")
                for i, example in enumerate(key_examples[key], 1):
                    logger.info(f"      {i}. User {example['user_id']}: {example['value']} ({example['type']})")
        
        # Анализируем размеры markers
        logger.info(f"\n{'='*70}")
        logger.info("MARKERS SIZE ANALYSIS")
        logger.info(f"{'='*70}")
        
        sizes = []
        key_counts = []
        
        for user in with_markers:
            sizes.append(len(json.dumps(user.markers)))
            key_counts.append(len(user.markers.keys()))
        
        avg_size = sum(sizes) / len(sizes)
        max_size = max(sizes)
        min_size = min(sizes)
        
        avg_keys = sum(key_counts) / len(key_counts)
        max_keys = max(key_counts)
        min_keys = min(key_counts)
        
        logger.info(f"Average markers size: {avg_size:.0f} bytes")
        logger.info(f"Max markers size: {max_size} bytes")
        logger.info(f"Min markers size: {min_size} bytes")
        logger.info(f"\nAverage keys per user: {avg_keys:.1f}")
        logger.info(f"Max keys per user: {max_keys}")
        logger.info(f"Min keys per user: {min_keys}")
        
        # Проверяем, есть ли данные, которые можно мигрировать
        logger.info(f"\n{'='*70}")
        logger.info("MIGRATION OPPORTUNITIES")
        logger.info(f"{'='*70}")
        
        # Проверяем дублирование с существующими колонками
        duplicates = {
            'summary': 0,
            'relove_context': 0,
            'last_message': 0
        }
        
        for user in with_markers:
            if 'summary' in user.markers:
                duplicates['summary'] += 1
            if 'relove_context' in user.markers:
                duplicates['relove_context'] += 1
            if 'last_message' in user.markers:
                duplicates['last_message'] += 1
        
        logger.info(f"Users with markers['summary']: {duplicates['summary']}")
        logger.info(f"Users with markers['relove_context']: {duplicates['relove_context']}")
        logger.info(f"Users with markers['last_message']: {duplicates['last_message']}")
        
        # Рекомендации
        logger.info(f"\n{'='*70}")
        logger.info("RECOMMENDATIONS")
        logger.info(f"{'='*70}")
        
        if len(all_keys) == 0:
            logger.info("✅ markers field is empty - can be removed")
        elif all(key in ['last_message', 'last_activity', 'temp_data'] for key in all_keys):
            logger.info("✅ markers contains only temporary data - keep it")
        elif duplicates['summary'] > 0 or duplicates['relove_context'] > 0:
            logger.info("⚠️ markers contains data that should be in separate columns")
            logger.info("   Run migration script to move data")
        else:
            logger.info("💡 markers contains custom data - analyze if it's needed")
        
        # Детальный анализ каждого ключа
        logger.info(f"\n{'='*70}")
        logger.info("DETAILED KEY ANALYSIS")
        logger.info(f"{'='*70}")
        
        for key in all_keys.keys():
            logger.info(f"\nKey: '{key}'")
            
            # Типы значений
            value_types = Counter()
            value_lengths = []
            
            for user in with_markers:
                if key in user.markers:
                    value = user.markers[key]
                    value_types[type(value).__name__] += 1
                    
                    if isinstance(value, str):
                        value_lengths.append(len(value))
            
            logger.info(f"  Value types: {dict(value_types)}")
            
            if value_lengths:
                avg_len = sum(value_lengths) / len(value_lengths)
                logger.info(f"  Average string length: {avg_len:.0f} chars")
                logger.info(f"  Max string length: {max(value_lengths)} chars")
            
            # Рекомендация по ключу
            if key in ['summary', 'relove_context', 'profile_summary', 'psychological_summary']:
                logger.info(f"  ⚠️ SHOULD BE IN SEPARATE COLUMN")
            elif key in ['last_message', 'last_activity', 'temp_data']:
                logger.info(f"  ✅ OK for markers (temporary data)")
            elif key in ['gender', 'age', 'city']:
                logger.info(f"  ⚠️ SHOULD BE IN SEPARATE COLUMN")
            else:
                logger.info(f"  💡 Review if needed")


async def main():
    """Главная функция"""
    print("\n" + "="*70)
    print("MARKERS FIELD ANALYSIS")
    print("="*70 + "\n")
    
    await analyze_markers()
    
    print("\n" + "="*70)
    print("ANALYSIS COMPLETE")
    print("="*70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
