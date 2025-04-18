import asyncio
import logging
import sys # Добавим sys для корректного выхода

from aiohttp import web

from .logging_config import setup_logging
from .config import settings
from .bot import bot, dp, include_routers, setup_bot_commands
from .web import create_app
from .db.database import setup_database, close_database, AsyncSessionFactory
from .middlewares.db import DbSessionMiddleware
from .middlewares.activity import ActivityLogMiddleware

logger = logging.getLogger(__name__)

async def main():
    """Main function to setup logging, bot, webhooks, and start polling or web server."""
    # 1. Настройка логирования
    setup_logging()
    logger.info("Starting application setup...")

    # 2. Настройка базы данных
    db_initialized = await setup_database()
    if not db_initialized:
        logger.critical("Database initialization failed. Exiting.")
        sys.exit(1)

    # 3. Регистрация Middleware (ДО включения роутеров)
    if AsyncSessionFactory:
        dp.update.outer_middleware(DbSessionMiddleware(session_pool=AsyncSessionFactory))
        logger.info("Database session middleware registered.")
        # Подключаем логирование активности пользователя
        dp.update.outer_middleware(ActivityLogMiddleware())
        logger.info("Activity log middleware registered.")
    else:
        logger.warning("Database session middleware skipped as DB is not initialized.")

    # 4. Включение роутеров
    include_routers()

    # 5. Установка команд бота
    await setup_bot_commands()

    # 6. Выбор режима работы: Webhook или Polling
    if settings.webhook_host:
        logger.info("Starting bot in webhook mode...")
        # Создаем приложение aiohttp
        app = create_app(bot=bot, dp=dp)
        # Запускаем веб-сервер
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, settings.web_server_host, settings.web_server_port)
        logger.info(f"Starting web server on {settings.web_server_host}:{settings.web_server_port}")
        await site.start()
        # Бесконечный цикл для поддержания работы сервера
        await asyncio.Event().wait()
        # Очистка при завершении (в теории не должно достигаться в K8s, т.к. SIGTERM обрабатывается)
        await runner.cleanup()
        logger.info("Web server stopped.")

    else:
        logger.info("Starting bot in polling mode...")
        # Важно: Перед запуском polling удаляем вебхук, если он был установлен
        await bot.delete_webhook(drop_pending_updates=True)
        # Запуск polling
        await dp.start_polling(bot)
        logger.info("Bot stopped polling.")

async def shutdown_app():
    """Graceful shutdown actions."""
    logger.info("Starting graceful shutdown...")
    await close_database()
    # Здесь можно добавить другие действия по очистке
    logger.info("Graceful shutdown complete.")

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped by user or system.")
    except Exception as e:
        logger.critical(f"Unhandled exception at top level: {e}", exc_info=True)
    finally:
        logger.info("Running shutdown tasks...")
        loop.run_until_complete(shutdown_app())
        logger.info("Application finished.") 