#!/usr/bin/env python3
import os
import sys
import asyncio
from dotenv import load_dotenv

# Добавляем корень проекта в PYTHONPATH для корректного импорта
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

load_dotenv(override=True)

from relove_bot.config import settings, reload_settings
from relove_bot.utils.custom_logging import setup_logging
from relove_bot.utils.fill_profiles import fill_all_profiles

reload_settings()  # Принудительно перечитываем .env
print("parsed db_url:", settings.db_url)

async def main():
    setup_logging()
    await fill_all_profiles(settings.our_channel_id)

if __name__ == "__main__":
    asyncio.run(main())

import asyncio
from dotenv import load_dotenv
from relove_bot.utils.custom_logging import setup_logging
from relove_bot.config import settings, reload_settings
from relove_bot.db.models import User
from relove_bot.services import telegram_service
from relove_bot.db.database import get_db_session, setup_database, close_database
from relove_bot.utils.fill_profiles import fill_all_profiles

async def main():
    setup_logging()
    await fill_all_profiles(settings.our_channel_id)

if __name__ == "__main__":
    asyncio.run(main())