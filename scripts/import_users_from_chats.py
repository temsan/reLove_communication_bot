"""
Скрипт для импорта пользователей из экспортированных чатов Telegram.
"""
import asyncio
import json
import logging
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from relove_bot.db.models import User
from relove_bot.db.session import async_session

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def import_users_from_json(json_path: str):
    """Импортирует пользователей из JSON файла экспорта чата."""
    logger.info(f"Reading {json_path}...")
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    messages = data.get('messages', [])
    logger.info(f"Found {len(messages)} messages")
    
    # Собираем уникальных пользователей
    users_data = {}
    
    for msg in messages:
        if msg.get('type') != 'message':
            continue
            
        from_user = msg.get('from')
        from_id = msg.get('from_id')
        
        if not from_user or not from_id:
            continue
        
        # Извлекаем user_id из from_id (формат: "user123456")
        if isinstance(from_id, str) and from_id.startswith('user'):
            user_id = int(from_id.replace('user', ''))
        elif isinstance(from_id, int):
            user_id = from_id
        else:
            continue
        
        if user_id not in users_data:
            users_data[user_id] = {
                'user_id': user_id,
                'username': from_user,
                'first_name': from_user,
                'last_name': None,
                'is_active': True
            }
    
    logger.info(f"Found {len(users_data)} unique users")
    
    # Сохраняем в БД
    async with async_session() as session:
        added = 0
        updated = 0
        
        for user_data in users_data.values():
            # Проверяем, есть ли уже такой пользователь
            result = await session.execute(
                select(User).where(User.id == user_data['user_id'])
            )
            existing_user = result.scalar_one_or_none()
            
            if existing_user:
                # Пропускаем - не затираем существующих
                updated += 1
            else:
                # Создаем только нового
                new_user = User(
                    id=user_data['user_id'],
                    username=user_data['username'],
                    first_name=user_data['first_name'],
                    last_name=user_data['last_name'],
                    is_active=True
                )
                session.add(new_user)
                added += 1
        
        await session.commit()
        logger.info(f"Added {added} new users, updated {updated} existing users")


async def main():
    """Импортирует пользователей из всех файлов экспорта."""
    chat_files = [
        'reLoveReason/Прошлые жизни reLove.json',
        'reLoveReason/reLove people Chat.json',
        'reLoveReason/Путь героя.json'
    ]
    
    for chat_file in chat_files:
        if Path(chat_file).exists():
            await import_users_from_json(chat_file)
        else:
            logger.warning(f"File not found: {chat_file}")
    
    # Проверяем итоговое количество
    async with async_session() as session:
        result = await session.execute(select(User))
        users = result.scalars().all()
        logger.info(f"Total users in database: {len(users)}")


if __name__ == "__main__":
    asyncio.run(main())
