#!/usr/bin/env python3
import os
import sys
import glob
import asyncio
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Добавляем корень проекта в PYTHONPATH для корректного импорта
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from relove_bot.db.session import SessionLocal
from relove_bot.db.models import User
from relove_bot.utils.custom_logging import setup_logging
from relove_bot.config import settings, reload_settings
from relove_bot.utils.fill_profiles import fill_all_profiles
from sqlalchemy import select

load_dotenv(override=True)
reload_settings()
setup_logging()

EXPORT_DIR = os.getenv('TELEGRAM_EXPORT_PATH')
if not EXPORT_DIR:
    raise ValueError('Переменная окружения TELEGRAM_EXPORT_PATH не задана!')

html_files = glob.glob(os.path.join(EXPORT_DIR, 'messages*.html'))
user_ids_from_files = set()

for html_file in html_files:
    with open(html_file, encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')
        for msg in soup.find_all(class_='message'):
            user_id = msg.get('data-from-id')
            if user_id:
                user_ids_from_files.add(int(user_id))

print(f'User IDs из файлов: {len(user_ids_from_files)}')

async def fill_and_mark_sleeping(user_ids_from_files):
    async with SessionLocal() as session:
        result = await session.execute(select(User.id))
        user_ids_in_db = set(row[0] for row in result.all())

        new_ids = user_ids_from_files - user_ids_in_db
        sleeping_ids = user_ids_in_db - user_ids_from_files

        for uid in new_ids:
            session.add(User(id=uid, first_name='Unknown', is_active=True))

        for uid in sleeping_ids:
            user = await session.get(User, uid)
            if user:
                if not user.markers or not isinstance(user.markers, dict):
                    user.markers = {}
                user.markers['sleeping'] = True

        await session.commit()
        print(f"Добавлено новых: {len(new_ids)}. Спящих пользователей помечено: {len(sleeping_ids)}.")

    # После синхронизации профилей запускаем fill_all_profiles для актуализации данных
    await fill_all_profiles(settings.our_channel_id)

if __name__ == '__main__':
    asyncio.run(fill_and_mark_sleeping(user_ids_from_files))
