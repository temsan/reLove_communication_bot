import asyncio
from sqlalchemy import inspect
from relove_bot.db.session import engine

async def show_tables():
    async with engine.begin() as conn:
        inspector = inspect(conn.sync_engine)
        print('Список таблиц:', inspector.get_table_names())

if __name__ == "__main__":
    asyncio.run(show_tables())
