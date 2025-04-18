#!/usr/bin/env python3
import os
import sys
# Добавляем корневую папку проекта в PYTHONPATH для импорта relove_bot
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import asyncio

from dotenv import load_dotenv
load_dotenv(override=True)

from relove_bot.config import settings, reload_settings
reload_settings()  # Принудительно перечитываем .env
print("parsed db_url:", settings.db_url)

from relove_bot.utils.fill_profiles import fill_all_profiles


def main():
    channel_id = settings.our_channel_id
    print(f"Запуск массового обновления профилей для канала {channel_id}...")
    asyncio.run(fill_all_profiles(channel_id))
    print("Массовое обновление профилей завершено.")


if __name__ == "__main__":
    main()
