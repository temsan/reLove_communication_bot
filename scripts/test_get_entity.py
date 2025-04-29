import asyncio
import os
from telethon import TelegramClient
from dotenv import load_dotenv

load_dotenv(override=True)

api_id = int(os.getenv('TG_API_ID'))
api_hash = os.getenv('TG_API_HASH')
session = os.getenv('TG_SESSION', 'relove_bot')

async def main():
    client = TelegramClient(session, api_id, api_hash)
    await client.start()
    user_id = 1737830544
    try:
        entity = await client.get_entity(user_id)
        print(f'Entity по user_id={user_id}:', entity)
    except Exception as e:
        print(f'Ошибка при получении entity по user_id={user_id}:', e)
    await client.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
