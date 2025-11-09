import asyncio
import logging
from aiohttp import web
from relove_bot.bot import create_bot_and_dispatcher
from relove_bot.web import create_app
from relove_bot.config import settings

async def main():
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger(__name__)

    # Создаем бота и диспетчер
    bot, dp = create_bot_and_dispatcher()
    
    # Создаем веб-приложение
    app = create_app(bot, dp)
    
    # Запускаем веб-сервер
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    
    logger.info(f"Сервер запущен на http://localhost:8080")
    
    # Бесконечный цикл для работы сервера
    while True:
        await asyncio.sleep(3600)  # Спим час, чтобы не нагружать процессор

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Сервер остановлен")
