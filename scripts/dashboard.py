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
    try:
        # Создаем приложение дашборда
        app = create_dashboard_app()
        
        # Настраиваем и запускаем сервер
        runner = aiohttp_web.AppRunner(app)
        await runner.setup()
        
        print('✓ Веб-дашборд запущен на http://localhost:8080')
        print('  Перейдите по адресу http://localhost:8080/dashboard для просмотра')
        
        site = aiohttp_web.TCPSite(runner, '0.0.0.0', 8080)
        await site.start()
        
        # Бесконечный цикл, чтобы приложение не завершалось
        await asyncio.Event().wait()
    except ConnectionRefusedError:
        print('\n✗ Ошибка подключения к базе данных PostgreSQL!')
        print('  Запустите базу данных командой: docker-compose up -d\n')
        raise SystemExit(1)
    except Exception as e:
        error_msg = str(e)
        
        # Проверяем, связана ли ошибка с БД
        if any(keyword in error_msg.lower() for keyword in ['connection', 'database', 'refused', 'connect']):
            print('\n✗ Ошибка подключения к базе данных!')
            print('  Убедитесь, что PostgreSQL запущен:')
            print('    docker-compose up -d\n')
        else:
            print(f'\n✗ Ошибка запуска дашборда: {error_msg}\n')
        
        raise SystemExit(1)

if __name__ == "__main__":
    try:
        asyncio.run(start_dashboard())
    except KeyboardInterrupt:
        print('\n✓ Дашборд остановлен')
    except Exception:
        pass  # Ошибка уже выведена в start_dashboard()
