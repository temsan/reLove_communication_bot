import logging
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from .config import settings

logger = logging.getLogger(__name__)

async def health_check(request: web.Request):
    """Liveness probe endpoint."""
    # Простая проверка, можно добавить проверки зависимостей (БД, Telegram API)
    logger.debug("Health check requested")
    return web.Response(text="OK")

async def readiness_check(request: web.Request):
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
    app.router.add_get('/healthz', health_check, name='healthz')
    app.router.add_get('/readyz', readiness_check, name='readyz')

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