import asyncio
from relove_bot.db.session import SessionLocal
from relove_bot.db.models import User

from relove_bot.db.database import setup_database

async def print_nonempty_summaries():
    await setup_database()
    async with SessionLocal() as session:
        users = (await session.execute(User.__table__.select())).fetchall()
        count = 0
        for row in users:
            user_id = row.id if hasattr(row, 'id') else row[0]
            user = await session.get(User, user_id)
            if not user:
                continue
            summary = None
            if user.context and isinstance(user.context, dict):
                summary = user.context.get('summary')
            if summary and summary.strip():
                print(f"User ID: {user.id}, Username: {user.username}, Summary:\n{summary}\n{'-'*40}")
                count += 1
        print(f"Всего пользователей с непустым summary: {count}")

if __name__ == "__main__":
    asyncio.run(print_nonempty_summaries())
