"""
Тестовый импорт: по 1 пользователю из каждого канала reLove.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from telethon import TelegramClient
from sqlalchemy import select
from relove_bot.config import settings
from relove_bot.db.models import User, GenderEnum
from relove_bot.db.session import async_session
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/test_import_one_per_channel.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


async def main():
    """Импортирует по 1 пользователю из каждого канала reLove"""
    
    print("\n" + "="*70)
    print("TEST IMPORT: 1 USER PER RELOVE CHANNEL")
    print("="*70 + "\n")
    
    # Проверяем сессию
    session_file = Path(f"{settings.tg_session}.session")
    if not session_file.exists():
        logger.error("❌ Session file not found!")
        logger.info("   Run: python scripts/telegram/test_telethon_connection.py")
        return
    
    client = TelegramClient(
        settings.tg_session,
        settings.tg_api_id,
        settings.tg_api_hash.get_secret_value()
    )
    
    stats = {
        'channels_found': 0,
        'users_imported': 0,
        'users_updated': 0,
        'errors': 0
    }
    
    try:
        await client.connect()
        
        if not await client.is_user_authorized():
            logger.error("❌ Not authorized!")
            logger.info("   Run: python scripts/telegram/test_telethon_connection.py")
            return
        
        logger.info("✅ Connected to Telegram\n")
        
        # Находим все каналы reLove
        logger.info("🔍 Searching for reLove channels...")
        relove_channels = []
        
        async for dialog in client.iter_dialogs():
            entity_name = dialog.name.lower()
            
            if 'relove' in entity_name or 'релов' in entity_name:
                channel_info = {
                    'id': dialog.id,
                    'name': dialog.name,
                    'username': getattr(dialog.entity, 'username', None),
                    'type': 'channel' if dialog.is_channel else 'group',
                    'entity': dialog.entity
                }
                relove_channels.append(channel_info)
                logger.info(
                    f"   Found: {channel_info['name']} "
                    f"(@{channel_info['username'] or 'no username'}) "
                    f"[{channel_info['type']}]"
                )
        
        if not relove_channels:
            logger.warning("⚠️ No reLove channels found!")
            return
        
        stats['channels_found'] = len(relove_channels)
        logger.info(f"\n✅ Found {len(relove_channels)} reLove channels\n")
        
        # Обрабатываем каждый канал
        for i, channel_info in enumerate(relove_channels, 1):
            logger.info(f"\n{'='*70}")
            logger.info(f"Channel {i}/{len(relove_channels)}: {channel_info['name']}")
            logger.info(f"{'='*70}")
            
            try:
                # Получаем первого пользователя (не бота)
                user_found = False
                
                async for user in client.iter_participants(
                    channel_info['entity'],
                    limit=10  # Проверяем первых 10, чтобы найти не-бота
                ):
                    if not user.bot:
                        # Нашли пользователя!
                        logger.info(f"\n👤 Found user:")
                        logger.info(f"   ID: {user.id}")
                        logger.info(f"   Username: @{user.username or 'no username'}")
                        logger.info(f"   Name: {user.first_name} {user.last_name or ''}")
                        
                        # Сохраняем в БД
                        async with async_session() as session:
                            # Проверяем существование
                            result = await session.execute(
                                select(User).where(User.id == user.id)
                            )
                            db_user = result.scalar_one_or_none()
                            
                            if db_user:
                                # Обновляем
                                logger.info(f"\n   ✅ User exists in DB")
                                logger.info(f"   Current profile_summary: {'Yes' if db_user.profile_summary else 'No'}")
                                
                                update_needed = False
                                if db_user.username != user.username:
                                    db_user.username = user.username
                                    update_needed = True
                                if db_user.first_name != user.first_name:
                                    db_user.first_name = user.first_name
                                    update_needed = True
                                if db_user.last_name != user.last_name:
                                    db_user.last_name = user.last_name
                                    update_needed = True
                                if not db_user.is_active:
                                    db_user.is_active = True
                                    update_needed = True
                                
                                if update_needed:
                                    await session.commit()
                                    logger.info(f"   📝 Updated user info")
                                    stats['users_updated'] += 1
                                else:
                                    logger.info(f"   ✅ No updates needed")
                            else:
                                # Создаем нового
                                logger.info(f"\n   ➕ Creating new user in DB")
                                
                                new_user = User(
                                    id=user.id,
                                    username=user.username,
                                    first_name=user.first_name or "",
                                    last_name=user.last_name,
                                    gender=GenderEnum.female,
                                    is_active=True
                                )
                                session.add(new_user)
                                await session.commit()
                                
                                logger.info(f"   ✅ User created")
                                stats['users_imported'] += 1
                        
                        user_found = True
                        break  # Берем только первого пользователя
                
                if not user_found:
                    logger.warning(f"   ⚠️ No users found (might be broadcast channel)")
                
            except Exception as e:
                logger.error(f"   ❌ Error processing channel: {e}")
                stats['errors'] += 1
        
        # Итоговая статистика
        logger.info(f"\n{'='*70}")
        logger.info("STATISTICS")
        logger.info(f"{'='*70}")
        logger.info(f"Channels found: {stats['channels_found']}")
        logger.info(f"Users imported (new): {stats['users_imported']}")
        logger.info(f"Users updated: {stats['users_updated']}")
        logger.info(f"Errors: {stats['errors']}")
        logger.info(f"{'='*70}\n")
        
        if stats['users_imported'] > 0 or stats['users_updated'] > 0:
            logger.info("✅ Test import successful!")
            logger.info("\n💡 To import all users, run:")
            logger.info("   python scripts/profiles/fill_profiles_from_channels.py --all --no-fill")
        
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
    
    finally:
        await client.disconnect()
        logger.info("\n👋 Disconnected from Telegram")


if __name__ == "__main__":
    asyncio.run(main())
