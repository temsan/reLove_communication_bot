"""
Безопасный тест импорта пользователей.
Проверяет логику без изменения существующих данных.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from telethon import TelegramClient
from sqlalchemy import select
from relove_bot.config import settings
from relove_bot.db.models import User
from relove_bot.db.session import async_session
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def check_existing_users():
    """Проверяет существующих пользователей в БД"""
    logger.info("Checking existing users in database...")
    
    async with async_session() as session:
        result = await session.execute(
            select(User).limit(10)
        )
        users = result.scalars().all()
        
        if not users:
            logger.warning("No users found in database")
            return []
        
        logger.info(f"Found {len(users)} users (showing first 10):")
        print("\n" + "="*80)
        print(f"{'ID':<12} {'Username':<20} {'Name':<25} {'Has Summary':<12}")
        print("="*80)
        
        for user in users:
            has_summary = "✅ Yes" if (user.markers and user.markers.get('summary')) else "❌ No"
            username = f"@{user.username}" if user.username else "no username"
            name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "no name"
            
            print(f"{user.id:<12} {username:<20} {name:<25} {has_summary:<12}")
        
        print("="*80 + "\n")
        
        return users


async def simulate_import_logic(tg_user_data: dict):
    """
    Симулирует логику импорта БЕЗ реального изменения данных.
    Показывает что будет сделано.
    """
    logger.info(f"\n{'='*80}")
    logger.info(f"Simulating import for user: {tg_user_data['id']} (@{tg_user_data.get('username')})")
    logger.info(f"{'='*80}")
    
    async with async_session() as session:
        # Проверяем существование
        result = await session.execute(
            select(User).where(User.id == tg_user_data['id'])
        )
        db_user = result.scalar_one_or_none()
        
        if db_user:
            logger.info("✅ User EXISTS in database")
            logger.info(f"   Current data:")
            logger.info(f"   - Username: @{db_user.username}")
            logger.info(f"   - Name: {db_user.first_name} {db_user.last_name or ''}")
            logger.info(f"   - Is Active: {db_user.is_active}")
            logger.info(f"   - Has Summary: {'Yes' if (db_user.markers and db_user.markers.get('summary')) else 'No'}")
            
            if db_user.markers and db_user.markers.get('summary'):
                summary = db_user.markers['summary']
                logger.info(f"   - Summary preview: {summary[:100]}...")
            
            # Проверяем что изменится
            changes = []
            
            if db_user.username != tg_user_data.get('username'):
                changes.append(f"Username: {db_user.username} → {tg_user_data.get('username')}")
            
            if db_user.first_name != tg_user_data.get('first_name'):
                changes.append(f"First name: {db_user.first_name} → {tg_user_data.get('first_name')}")
            
            if db_user.last_name != tg_user_data.get('last_name'):
                changes.append(f"Last name: {db_user.last_name} → {tg_user_data.get('last_name')}")
            
            if not db_user.is_active:
                changes.append(f"Is active: False → True")
            
            if changes:
                logger.info(f"\n   📝 WOULD UPDATE:")
                for change in changes:
                    logger.info(f"      - {change}")
            else:
                logger.info(f"\n   ✅ No changes needed")
            
            # ВАЖНО: Проверяем что НЕ затрем
            if db_user.markers and db_user.markers.get('summary'):
                logger.info(f"\n   🔒 WILL PRESERVE:")
                logger.info(f"      - Summary (existing)")
                if db_user.markers.get('relove_context'):
                    logger.info(f"      - Relove context (existing)")
            
        else:
            logger.info("❌ User DOES NOT exist in database")
            logger.info(f"   📝 WOULD CREATE new user:")
            logger.info(f"      - ID: {tg_user_data['id']}")
            logger.info(f"      - Username: @{tg_user_data.get('username')}")
            logger.info(f"      - Name: {tg_user_data.get('first_name')} {tg_user_data.get('last_name', '')}")
            logger.info(f"      - Is Active: True")
            logger.info(f"      - Gender: female (default)")


async def test_with_real_channel():
    """Тестирует с реальным каналом (только чтение, без записи)"""
    logger.info("\n" + "="*80)
    logger.info("Testing with real Telegram channel (READ ONLY)")
    logger.info("="*80)
    
    # Проверяем наличие сессии
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
    
    try:
        await client.connect()
        
        if not await client.is_user_authorized():
            logger.error("❌ Not authorized!")
            logger.info("   Run: python scripts/telegram/test_telethon_connection.py")
            return
        
        logger.info("✅ Connected to Telegram")
        
        # Ищем первый канал reLove
        relove_channel = None
        async for dialog in client.iter_dialogs():
            if 'relove' in dialog.name.lower() or 'релов' in dialog.name.lower():
                relove_channel = dialog
                break
        
        if not relove_channel:
            logger.warning("⚠️ No reLove channels found")
            logger.info("   Make sure you joined reLove channels")
            return
        
        logger.info(f"\n📢 Testing with channel: {relove_channel.name}")
        
        # Получаем первых 3 участников для теста
        participants = []
        try:
            async for user in client.iter_participants(relove_channel, limit=3):
                if not user.bot:
                    participants.append(user)
        except Exception as e:
            logger.warning(f"⚠️ Could not get participants: {e}")
            logger.info("   This might be a broadcast channel (can't get subscribers)")
            return
        
        if not participants:
            logger.warning("⚠️ No participants found")
            return
        
        logger.info(f"✅ Got {len(participants)} participants for testing\n")
        
        # Симулируем импорт для каждого
        for i, tg_user in enumerate(participants, 1):
            user_data = {
                'id': tg_user.id,
                'username': tg_user.username,
                'first_name': tg_user.first_name,
                'last_name': tg_user.last_name
            }
            
            await simulate_import_logic(user_data)
            
            if i < len(participants):
                logger.info("\n" + "-"*80 + "\n")
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await client.disconnect()
        logger.info("\n✅ Disconnected from Telegram")


async def main():
    """Главная функция"""
    print("\n" + "="*80)
    print("SAFE IMPORT TEST - NO DATA WILL BE MODIFIED")
    print("="*80 + "\n")
    
    # 1. Проверяем существующих пользователей
    existing_users = await check_existing_users()
    
    # 2. Симулируем импорт с реальным каналом
    await test_with_real_channel()
    
    print("\n" + "="*80)
    print("TEST COMPLETED - NO DATA WAS MODIFIED")
    print("="*80)
    print("\n💡 If everything looks good, you can run:")
    print("   python scripts/profiles/fill_profiles_from_channels.py --all --no-fill")
    print("\n⚠️ This will only ADD new users and UPDATE basic info (username, name)")
    print("⚠️ Existing summaries and profiles will NOT be overwritten")
    print("="*80 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
