import logging
from aiohttp import web
from relove_bot.db.repository import UserRepository
from relove_bot.db.database import AsyncSessionFactory
from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
import base64

from .config import settings

logger = logging.getLogger(__name__)

async def health_check(request: web.Request):
    """Liveness probe endpoint."""
    # Простая проверка, можно добавить проверки зависимостей (БД, Telegram API)
    logger.debug("Health check requested")
    return web.Response(text="OK")

async def readiness_check(request: web.Request):
    pass

async def dashboard(request: web.Request):
    from aiohttp import web
    from relove_bot.db.repository import UserRepository
    from relove_bot.db.database import AsyncSessionFactory
    import logging
    logger = logging.getLogger("dashboard")
    # Получаем пользователей из БД
    async with AsyncSessionFactory() as session:
        repo = UserRepository(session)
        # Получаем всех пользователей из БД
        from relove_bot.db.models import User
        users = await session.execute(
            User.__table__.select()
        )
        user_rows = users.fetchall()
        progress = []
        for row in user_rows:
            user = row
            progress.append({
                'user_id': user.id,
                'username': user.username,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'gender': user.gender.value if user.gender else None,
                'photo': f"data:image/jpeg;base64,{base64.b64encode(user.photo_jpeg).decode('utf-8')}" if user.photo_jpeg else None,
                'summary': user.profile_summary,
            })
    html = """
    <html>
    <head>
      <title>Dashboard</title>
      <meta charset='utf-8'>
      <style>
        body {{{{ font-family: 'Segoe UI', Arial, sans-serif; background: #f6f7fb; margin: 0; }}}}
        h1 {{{{ text-align: center; font-size: 2em; margin: 24px 0 16px 0; color: #333; }}}}
        table {{{{ margin: 0 auto; border-collapse: collapse; background: #fff; box-shadow: 0 2px 16px #0001; width: 98%; max-width: 1600px; }}}}
        th, td {{{{ padding: 7px 10px; border: 1px solid #e0e0e0; text-align: left; font-size: 13px; }}}}
        th {{{{ background: #f0f0f7; font-size: 14px; }}}}
        td.photo-cell {{{{ text-align: center; }}}}
        img.user-photo {{{{
          width: 120px; height: 120px; object-fit: cover; border-radius: 10px; border: 1px solid #ddd;
          background: #eee;
        }}}}
        td.photo-summary-cell {{{{
          min-width: 220px;
          max-width: 320px;
          vertical-align: top;
          padding: 8px 12px;
        }}}}
        .photo-block {{{{
          text-align: center;
          margin-bottom: 7px;
        }}}}
        .summary-block {{{{
          font-size: 13px;
          color: #444;
          background: #f3f3f9;
          border-radius: 7px;
          padding: 7px 10px;
          margin-top: 0;
          word-break: break-word;
          white-space: pre-line;
        }}}}
        td.summary-cell, td.posts-cell {{{{
          font-size: 12px;
          color: #444;
          max-width: 300px;
          white-space: pre-line;
          word-break: break-word;
        }}}}
        tr:nth-child(even) {{{{ background: #f9f9fb; }}}}
        tr:hover {{{{ background: #f1f5ff; }}}}
        .status-ok {{{{ color: #388e3c; font-weight: bold; }}}}
        .status-skipped {{{{ color: #ffa000; font-weight: bold; }}}}
        .status-failed {{{{ color: #d32f2f; font-weight: bold; }}}}
      </style>
      <script>
        setInterval(function() {{{{ window.location.reload(); }}}}, 5000);
      </script>
    </head>
    <body>
    <h1>Прогресс обработки пользователей</h1>
    <table>
      <tr>
        <th>Фото + Summary</th><th>ID</th><th>Username</th><th>Имя</th><th>Фамилия</th><th>Пол</th><th>Статус</th><th>Дата регистрации</th><th>Последний визит</th><th>Посты</th>
      </tr>
      {rows}
    </table>
    </body>
    </html>
    """
    rows = ""
    try:
        if not progress:
            rows = "<tr><td colspan='11' style='text-align:center; color:#888;'>Нет данных для отображения</td></tr>"
        else:
            for user in progress:
                status = 'skipped' if user.get('skipped') else ('failed' if user.get('failed') else 'ok')
                photo = user.get('photo')
                photo_html = f'<img src="{photo}" class="user-photo">' if photo else ''
                posts = user.get('posts', [])
                posts_html = '<br>'.join(posts) if posts else ''
                rows += f"<tr>"
                # Фото и summary вместе в одной ячейке
                safe_photo = photo_html if photo else '<div class="photo-block"><img src="/static/avatars/default.jpg" class="user-photo" alt="no photo"></div>'
                summary_val = user.get('summary')
                safe_summary = str(summary_val) if summary_val else 'Нет описания'
                rows += "<td class='photo-summary-cell'>"
                rows += f"<div class='photo-block'>{safe_photo}</div>"
                rows += f"<div class='summary-block'>{safe_summary}</div>"
                rows += "</td>"
                rows += f"<td>{user.get('user_id')}</td>"
                rows += f"<td>{user.get('username') or ''}</td>"
                rows += f"<td>{user.get('first_name') or ''}</td>"
                rows += f"<td>{user.get('last_name') or ''}</td>"
                rows += f"<td>{user.get('gender') or ''}</td>"
                status_class = f"status-{status}"
                rows += f"<td class='{status_class}'>{status}</td>"
                rows += f"<td>{user.get('registration_date') or ''}</td>"
                rows += f"<td>{user.get('last_seen_date') or ''}</td>"
                rows += f"<td class='posts-cell'>{posts_html}</td>"
                rows += f"</tr>"
    except Exception as e:
        logger.error(f"Ошибка генерации rows для dashboard: {e}")
        rows = "<tr><td colspan='11'>Ошибка отображения данных: {}</td></tr>".format(e)
    # rows всегда строка, даже если пусто
    if not isinstance(rows, str):
        rows = str(rows)
    return web.Response(text=html.format(rows=rows), content_type='text/html')
    """Readiness probe endpoint."""
    # Здесь можно добавить проверки готовности принимать трафик
    # Например, инициализировался ли бот, есть ли соединение с БД
    # TODO: Добавить проверку подключения к БД, когда она будет реализована
    # TODO: Добавить проверку доступности внешних сервисов, если необходимо
    # Пока делаем простой ответ
    try:
        # Попытка получить базовую информацию о боте как индикатор
        # bot_info = await request.app['bot'].get_me()
        # logger.debug(f"Readiness check: bot info received for {bot_info.username}")
        # Если используем БД, можно проверить соединение
        # await check_db_connection(request.app['db_pool'])
        logger.debug("Readiness check successful")
        return web.Response(text="OK")
    except Exception as e:
        logger.error(f"Readiness check failed: {e}", exc_info=True)
        return web.Response(text="Service Unavailable", status=503)


async def setup_webhook(bot: Bot, dispatcher: Dispatcher):
    """Sets up the webhook for the bot."""
    if not settings.webhook_host:
        logger.warning("WEBHOOK_HOST not set, skipping webhook setup.")
        return None

    webhook_url = f"{settings.webhook_host}{settings.webhook_path}"
    webhook_secret = settings.webhook_secret.get_secret_value() if settings.webhook_secret else None

    try:
        await bot.set_webhook(
            url=webhook_url,
            secret_token=webhook_secret,
            # drop_pending_updates=True # Раскомментировать, если нужно сбрасывать старые апдейты при старте
        )
        logger.info(f"Webhook set up successfully at {webhook_url}")
        return webhook_url
    except Exception as e:
        logger.error(f"Failed to set webhook at {webhook_url}: {e}", exc_info=True)
        return None

async def on_startup(app: web.Application):
    """Actions to perform on web server startup."""
    bot: Bot = app['bot']
    dp: Dispatcher = app['dp']
    logger.info("Web server starting up...")
    await setup_webhook(bot, dp)
    # Здесь можно добавить инициализацию подключения к БД
    # app['db_pool'] = await create_db_pool()
    logger.info("Web server startup complete.")

async def on_shutdown(app: web.Application):
    """Actions to perform on web server shutdown."""
    bot: Bot = app['bot']
    logger.info("Web server shutting down...")
    # Удаляем вебхук при остановке
    # await bot.delete_webhook()
    # logger.info("Webhook deleted.")
    # Закрываем соединение с БД
    # if 'db_pool' in app:
    #    await app['db_pool'].close()
    #    logger.info("Database pool closed.")
    await bot.session.close()
    logger.info("Bot session closed.")
    logger.info("Web server shutdown complete.")

def create_app(bot: Bot, dp: Dispatcher) -> web.Application:
    """Creates and configures the aiohttp web application."""
    app = web.Application()

    # Сохраняем экземпляры Bot и Dispatcher для доступа в обработчиках
    app['bot'] = bot
    app['dp'] = dp

    # Добавляем health и readiness эндпоинты
    app.router.add_get('/health', health_check)
    app.router.add_get('/readiness', readiness_check)
    app.router.add_get('/dashboard', dashboard)

    # Отдача статических файлов (аватары)
    import os
    static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../static/avatars'))
    if not os.path.exists(static_dir):
        os.makedirs(static_dir, exist_ok=True)
    app.router.add_static('/static/avatars/', static_dir, name='avatars')

    # Регистрируем обработчик вебхуков aiogram
    SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=settings.webhook_secret.get_secret_value() if settings.webhook_secret else None,
    ).register(app, path=settings.webhook_path)

    # Настраиваем приложение aiogram (необходимо для SimpleRequestHandler)
    setup_application(app, dp, bot=bot)

    # Добавляем обработчики startup и shutdown
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    logger.info(f"aiohttp application created. Webhook path: {settings.webhook_path}")
    return app 