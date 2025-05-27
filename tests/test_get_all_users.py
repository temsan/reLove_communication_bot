#!/usr/bin/env python3
import asyncio
import logging
from tqdm import tqdm
from relove_bot.services.telegram_service import get_channel_users, get_bot_client

async def get_all_user_ids(channel_id_or_username: str, batch_size: int = 200):
    """
    Получает все user_id из канала с прогресс-баром.
    """
    user_ids = []
    total_users = 0
    async for _ in get_channel_users(channel_id_or_username, batch_size):
        total_users += 1
    with tqdm(total=total_users, desc="Получение user_id") as pbar:
        async for user_id in get_channel_users(channel_id_or_username, batch_size):
            user_ids.append(user_id)
            pbar.update(1)
    return user_ids

async def main():
    try:
        logging.info("Script execution started via __main__.")
        # Укажите корректный username или id канала
        channel_id_or_username = '@reloveinfo'  # или числовой id, например -1001234567890
        user_ids = await get_all_user_ids(channel_id_or_username, batch_size=200)
        logging.info(f"Всего получено user_id: {len(user_ids)}")
    except Exception as e:
        logging.error(f"Error in main: {e}")
    finally:
        logging.info("Script execution finished.")

if __name__ == "__main__":
    asyncio.run(main()) 