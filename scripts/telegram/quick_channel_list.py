"""
Быстрый скрипт для просмотра каналов reLove.
Использует существующую сессию Telethon.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from telethon import TelegramClient
from relove_bot.config import settings


async def list_relove_channels():
    """Показывает список каналов reLove"""
    
    # Проверяем наличие файла сессии
    session_file = Path(f"{settings.tg_session}.session")
    if not session_file.exists():
        print("❌ Session file not found!")
        print(f"   Expected: {session_file}")
        print("\n📝 First, you need to authorize:")
        print("   python scripts/test_telethon_connection.py")
        return
    
    print("🔄 Connecting to Telegram...")
    
    client = TelegramClient(
        settings.tg_session,
        settings.tg_api_id,
        settings.tg_api_hash.get_secret_value()
    )
    
    try:
        await client.connect()
        
        if not await client.is_user_authorized():
            print("❌ Not authorized! Run test_telethon_connection.py first")
            return
        
        print("✅ Connected!")
        
        # Получаем информацию о себе
        me = await client.get_me()
        print(f"\n👤 Logged in as: {me.first_name} (@{me.username or 'no username'})")
        
        # Ищем каналы с relove
        print(f"\n🔍 Searching for reLove channels and groups...\n")
        
        relove_entities = []
        
        async for dialog in client.iter_dialogs():
            entity_name = dialog.name.lower()
            
            if 'relove' in entity_name or 'релов' in entity_name:
                entity_type = "📢 Channel" if dialog.is_channel else "👥 Group"
                username = getattr(dialog.entity, 'username', None)
                username_str = f"@{username}" if username else "no username"
                
                entity_info = {
                    'name': dialog.name,
                    'username': username_str,
                    'type': entity_type,
                    'id': dialog.id
                }
                relove_entities.append(entity_info)
        
        if not relove_entities:
            print("⚠️ No reLove channels found!")
            print("\nMake sure you:")
            print("  1. Joined reLove channels")
            print("  2. Channels have 'relove' or 'релов' in name")
        else:
            print(f"✅ Found {len(relove_entities)} reLove channels/groups:\n")
            print("="*70)
            
            for i, entity in enumerate(relove_entities, 1):
                print(f"{i}. {entity['type']} {entity['name']}")
                print(f"   Username: {entity['username']}")
                print(f"   ID: {entity['id']}")
                print("-"*70)
            
            print(f"\n💡 To import users from all channels, run:")
            print(f"   python scripts/fill_profiles_from_channels.py --all")
            
            print(f"\n💡 To import from specific channel, run:")
            if relove_entities[0]['username'] != 'no username':
                print(f"   python scripts/fill_profiles_from_channels.py --channel {relove_entities[0]['username']}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await client.disconnect()
        print("\n👋 Done!")


if __name__ == "__main__":
    print("="*70)
    print("reLove Channels Finder")
    print("="*70)
    print()
    asyncio.run(list_relove_channels())
