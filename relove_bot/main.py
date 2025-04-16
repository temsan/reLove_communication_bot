import asyncio
import logging

from aiohttp import web

from .logging_config import setup_logging
from .config import settings
from .bot import bot, dp, include_routers, setup_bot_commands
from .web import create_app

logger = logging.getLogger(__name__)

async def main():
    """Main function to setup logging, bot, webhooks, and start polling or web server."""
    # 1. Настройка логирования (Вызываем здесь)
    setup_logging()
    logger.info("Starting application setup...") # Добавим лог старта

    # 2. Включение роутеров
    include_routers()

    # 3. Установка команд бота
    await setup_bot_commands()

    # 4. Выбор режима работы: Webhook или Polling
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


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped by user or system.")
    except Exception as e:
        logger.critical(f"Unhandled exception at top level: {e}", exc_info=True) 