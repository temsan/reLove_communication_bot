"""
Тестовый скрипт для проверки подключения Telethon.
Показывает информацию о вашем аккаунте и список диалогов.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from telethon import TelegramClient
from relove_bot.config import settings


async def test_connection():
    """Тестирует подключение к Telegram"""
    print("🔄 Connecting to Telegram...")
    
    client = TelegramClient(
        settings.tg_session,
        settings.tg_api_id,
        settings.tg_api_hash.get_secret_value()
    )
    
    try:
        await client.start()
        print("✅ Successfully connected!")
        
        # Получаем информацию о себе
        me = await client.get_me()
        print(f"\n👤 Your account:")
        print(f"   ID: {me.id}")
        print(f"   Name: {me.first_name} {me.last_name or ''}")
        print(f"   Username: @{me.username or 'no username'}")
        print(f"   Phone: {me.phone}")
        
        # Показываем первые 10 диалогов
        print(f"\n💬 Your dialogs (first 10):")
        count = 0
        async for dialog in client.iter_dialogs(limit=10):
            count += 1
            entity_type = "Channel" if dialog.is_channel else "Group" if dialog.is_group else "User"
            username = getattr(dialog.entity, 'username', None)
            username_str = f"@{username}" if username else "no username"
            print(f"   {count}. {dialog.name} ({username_str}) [{entity_type}]")
        
        # Ищем каналы с relove
        print(f"\n🔍 Searching for reLove channels...")
        relove_count = 0
        async for dialog in client.iter_dialogs():
            if 'relove' in dialog.name.lower() or 'релов' in dialog.name.lower():
                relove_count += 1
                entity_type = "Channel" if dialog.is_channel else "Group"
                username = getattr(dialog.entity, 'username', None)
                username_str = f"@{username}" if username else "no username"
                print(f"   ✓ {dialog.name} ({username_str}) [{entity_type}]")
        
        if relove_count == 0:
            print("   ⚠️ No reLove channels found")
        else:
            print(f"\n✅ Found {relove_count} reLove channels/groups")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await client.disconnect()
        print("\n👋 Disconnected")


if __name__ == "__main__":
    print("="*60)
    print("Telethon Connection Test")
    print("="*60)
    asyncio.run(test_connection())
