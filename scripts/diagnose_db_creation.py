import asyncio
from sqlalchemy.exc import SQLAlchemyError
from relove_bot.db.session import engine
from relove_bot.db.models import Base

def print_header(msg):
    print("\n" + "="*30)
    print(msg)
    print("="*30)

async def diagnose_db_creation():
    print_header("ШАГ 1: Проверка подключения к базе данных")
    try:
        async with engine.connect() as conn:
            print("✔ Соединение с базой данных успешно установлено.")
    except Exception as e:
        print(f"❌ Ошибка подключения к базе данных: {e}")
        return

    print_header("ШАГ 2: Попытка создания таблиц (Base.metadata.create_all)")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            print("✔ Таблицы успешно созданы или уже существуют.")
    except SQLAlchemyError as e:
        print(f"❌ Ошибка SQLAlchemy при создании таблиц: {e}")
        return
    except Exception as e:
        print(f"❌ Другая ошибка при создании таблиц: {e}")
        return

    print_header("ШАГ 3: Список таблиц после создания")
    try:
        async with engine.connect() as conn:
            from sqlalchemy import inspect
            inspector = inspect(conn.sync_engine)
            tables = inspector.get_table_names()
            print(f"Таблицы в базе: {tables if tables else 'Нет таблиц'}")
    except Exception as e:
        print(f"❌ Ошибка при получении списка таблиц: {e}")

if __name__ == "__main__":
    asyncio.run(diagnose_db_creation())
