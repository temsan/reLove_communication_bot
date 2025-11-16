"""
Добавляет отсутствующие колонки в таблицу users
"""
import asyncio
from sqlalchemy import text
from relove_bot.db.session import async_session

async def add_columns():
    async with async_session() as session:
        # Добавляем колонки для отслеживания конверсии
        columns_to_add = [
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS metaphysical_profile JSONB",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_journey_stage VARCHAR(100)",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS psychological_summary TEXT",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS has_started_journey BOOLEAN DEFAULT FALSE",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS has_completed_journey BOOLEAN DEFAULT FALSE",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS has_visited_platform BOOLEAN DEFAULT FALSE",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS has_purchased_flow BOOLEAN DEFAULT FALSE",
        ]
        
        for sql in columns_to_add:
            try:
                await session.execute(text(sql))
                print(f"✓ {sql}")
            except Exception as e:
                print(f"✗ {sql}: {e}")
        
        await session.commit()
        print("\nAll columns added successfully!")

asyncio.run(add_columns())
