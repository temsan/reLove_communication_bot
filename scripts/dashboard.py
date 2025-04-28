import asyncio
from aiohttp import web as aiohttp_web
from relove_bot.web import create_app
from relove_bot.bot import bot, dp
from relove_bot.db.database import setup_database

async def start_dashboard():
    app = create_app(bot, dp)
    runner = aiohttp_web.AppRunner(app)
    await runner.setup()
    site = aiohttp_web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    print('Веб-дэшборд запущен на http://localhost:8080/dashboard')
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(start_dashboard())
