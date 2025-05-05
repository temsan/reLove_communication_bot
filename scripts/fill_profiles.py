#!/usr/bin/env python3
import os
import sys
import asyncio
from dotenv import load_dotenv
from openai import OpenAI

# Добавляем корень проекта в PYTHONPATH для корректного импорта
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from relove_bot.utils.custom_logging import setup_logging
from relove_bot.config import settings, reload_settings
from relove_bot.utils.fill_profiles import fill_all_profiles

load_dotenv(override=True)
reload_settings()  # Принудительно перечитываем .env

async def main():
    setup_logging()
    await fill_all_profiles(settings.our_channel_id)

if __name__ == "__main__":
    asyncio.run(main())