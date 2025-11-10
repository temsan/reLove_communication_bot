import asyncio
import logging
from aiohttp import web as aiohttp_web
from relove_bot.web import create_dashboard_app

# Настройка логирования - минимальный вывод
logging.basicConfig(
    level=logging.ERROR,  # Показываем только ошибки
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Отключаем все логи от библиотек
logging.getLogger('aiohttp').setLevel(logging.ERROR)
logging.getLogger('aiohttp.access').setLevel(logging.ERROR)
logging.getLogger('aiohttp.server').setLevel(logging.ERROR)
logging.getLogger('aiohttp.web').setLevel(logging.ERROR)
logging.getLogger('sqlalchemy').setLevel(logging.ERROR)
logging.getLogger('asyncpg').setLevel(logging.ERROR)
logging.getLogger('relove_bot').setLevel(logging.ERROR)

async def start_dashboard():
    # Создаем приложение дашборда
    app = create_dashboard_app()
    
    # Настраиваем и запускаем сервер
    runner = aiohttp_web.AppRunner(app)
    await runner.setup()
    site = aiohttp_web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    
    print('Веб-дашборд запущен на http://localhost:8080')
    print('Перейдите по адресу http://localhost:8080/dashboard для просмотра')
    
    # Бесконечный цикл, чтобы приложение не завершалось
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(start_dashboard())
