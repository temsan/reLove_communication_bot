from aiohttp import web
from scripts.dashboard import start_dashboard

async def main():
    app = web.Application()
    await start_dashboard()
    return app

if __name__ == '__main__':
    web.run_app(main())
