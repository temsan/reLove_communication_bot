"""Тест подключения Telethon"""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from telethon import TelegramClient
from relove_bot.config import settings

async def test():
    client = TelegramClient(
        settings.tg_session,
        settings.tg_api_id,
        settings.tg_api_hash.get_secret_value()
    )
    
    print("Connecting to Telegram...")
    await client.start()
    
    print("✅ Connected!")
    
    me = await client.get_me()
    print(f"Logged in as: {me.first_name} (@{me.username})")
    
    await client.disconnect()
    print("Disconnected")

asyncio.run(test())
