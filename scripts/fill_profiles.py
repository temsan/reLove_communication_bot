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

from relove_bot.utils.logging import setup_logging
from relove_bot.config import settings, reload_settings
from relove_bot.db.database import get_db_session, setup_database, close_database
from relove_bot.services.profile_service import ProfileService
from relove_bot.services import telegram_service
import asyncio

import subprocess
import sys
from relove_bot.services.telegram_service import get_user_posts_in_channel


async def start_dashboard():
    from aiohttp import web as aiohttp_web
    from relove_bot.web import create_app
    from relove_bot.bot import bot, dp
    from relove_bot.config import settings
    app = create_app(bot, dp)
    runner = aiohttp_web.AppRunner(app)
    await runner.setup()
    site = aiohttp_web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    print('Веб-дэшборд запущен на http://localhost:8080/dashboard')

async def main():
    # Запускаем веб-дэшборд параллельно
    import asyncio
    asyncio.create_task(start_dashboard())
    setup_logging()
    reload_settings()
    await setup_database()

    # Блокируем завершение скрипта, чтобы веб-дэшборд работал постоянно
    await asyncio.Event().wait()
    await telegram_service.start_client()
    channel_id = settings.our_channel_id
    print(f"Запуск массового обновления профилей для канала {channel_id}...")
    user_ids = await telegram_service.get_channel_users(channel_id)
    # Поддержка смещения через переменную окружения или аргумент
    offset = 0
    # os и sys уже импортированы в начале файла!
    if 'FILL_OFFSET' in os.environ:
        try:
            offset = int(os.environ['FILL_OFFSET'])
        except Exception:
            offset = 0
    elif len(sys.argv) > 1:
        try:
            offset = int(sys.argv[1])
        except Exception:
            offset = 0
    print(f"Обрабатываем пользователей с {offset} по {offset+100}")
    user_ids = user_ids[offset:offset+100]  # Следующие 100 пользователей
    processed, failed = 0, 0
    async for session in get_db_session():
        service = ProfileService(session)
        for user_id in user_ids:
            try:
                tg_user = await telegram_service.client.get_entity(user_id)
            except Exception:
                tg_user = None
            result = await service.process_user(user_id, channel_id, tg_user)
            # --- Запись прогресса для дашборда ---
            import json, os
            progress_file = os.path.join(os.path.dirname(__file__), '../dashboard_progress.json')
            # Получаем посты пользователя (до 3 последних)
            posts = []
            try:
                posts = await get_user_posts_in_channel(channel_id, user_id, limit=3)
            except Exception as e:
                print(f'[get_posts] Ошибка при получении постов для user {user_id}: {e}')
            user_info = {
                'user_id': user_id,
                'username': getattr(tg_user, 'username', None) if tg_user else None,
                'first_name': getattr(tg_user, 'first_name', None) if tg_user else None,
                'last_name': getattr(tg_user, 'last_name', None) if tg_user else None,
                'gender': result.get('gender') if isinstance(result, dict) else None,
                'registration_date': getattr(tg_user, 'date', None) if tg_user and hasattr(tg_user, 'date') else None,
                'last_seen_date': getattr(tg_user, 'last_seen', None) if tg_user and hasattr(tg_user, 'last_seen') else None,
                'summary': result.get('summary') if isinstance(result, dict) else None,
                'skipped': result == 'skipped',
                'failed': result.get('failed') if isinstance(result, dict) else False,
                'photo': None,
                'posts': posts
            }
            # Скачиваем и сохраняем фото пользователя, если оно есть
            if tg_user and getattr(tg_user, 'photo', None):
                try:
                    from telethon.errors.rpcerrorlist import PhotoInvalidError
                    static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../static/avatars'))
                    os.makedirs(static_dir, exist_ok=True)
                    photo_path = os.path.join(static_dir, f'{user_id}.jpg')
                    await telegram_service.client.download_profile_photo(user_id, file=photo_path)
                    user_info['photo'] = f'/static/avatars/{user_id}.jpg'
                except PhotoInvalidError:
                    user_info['photo'] = None
                except Exception as e:
                    print(f'[photo_download] Ошибка при скачивании фото для user {user_id}: {e}')
            # Читаем старый прогресс
            try:
                with open(progress_file, 'r', encoding='utf-8') as f:
                    progress = json.load(f)
            except Exception:
                progress = []
            # Обновляем или добавляем
            updated = False
            for idx, u in enumerate(progress):
                if u['user_id'] == user_id:
                    progress[idx] = user_info
                    updated = True
                    break
            if not updated:
                progress.append(user_info)
            with open(progress_file, 'w', encoding='utf-8') as f:
                json.dump(progress, f, ensure_ascii=False, indent=2)
            # --- Конец записи прогресса ---
            if isinstance(result, dict) and result.get('failed'):
                failed += 1
            elif result == 'skipped':
                pass  # Можно добавить счетчик пропущенных, если нужно
            else:
                processed += 1
    await close_database()
    print(f"Массовое обновление профилей завершено. Успешно: {processed}, ошибок: {failed}")
    # Оставляем веб-дэшборд работать, пока не завершат скрипт вручную
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        print("Остановка по сигналу, завершаем работу.")

if __name__ == "__main__":
    asyncio.run(main())
