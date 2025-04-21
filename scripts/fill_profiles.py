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
    # Автоматическая миграция alembic при старте
    import subprocess
    import os
    if os.path.exists(os.path.join(os.path.dirname(__file__), '..', 'alembic.ini')):
        alembic_dir = os.path.join(os.path.dirname(__file__), '..')
        print('Автоматическая генерация и применение миграций Alembic...')
        # Внимание: autogenerate актуален только для dev/test! В продакшене лучше вручную ревью миграций.
        subprocess.run(['alembic', 'revision', '--autogenerate', '-m', 'auto'], cwd=alembic_dir)
        subprocess.run(['alembic', 'upgrade', 'head'], cwd=alembic_dir)
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
            if tg_user and getattr(tg_user, 'photo', None):
                try:
                    from telethon.errors.rpcerrorlist import PhotoInvalidError
                    from PIL import Image
                    import io
                    # Скачиваем фото во временный буфер
                    temp_buf = io.BytesIO()
                    await telegram_service.client.download_profile_photo(user_id, file=temp_buf)
                    temp_buf.seek(0)
                    # Открываем изображение и сжимаем в JPEG
                    img = Image.open(temp_buf)
                    jpeg_buf = io.BytesIO()
                    img.convert('RGB').save(jpeg_buf, format='JPEG', quality=80)
                    jpeg_bytes = jpeg_buf.getvalue()
                    # Сохраняем в БД
                    await session.execute(
                        f"UPDATE users SET photo_jpeg = :photo WHERE id = :uid",
                        {"photo": jpeg_bytes, "uid": user_id}
                    )
                    await session.commit()
                except PhotoInvalidError:
                    pass
                except Exception as e:
                    print(f'[photo_download] Ошибка при скачивании фото для user {user_id}: {e}')
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
