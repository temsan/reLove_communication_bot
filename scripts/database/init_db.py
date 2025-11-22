"""Initialize database tables."""
import asyncio
from relove_bot.db.database import setup_database


async def init_db():
    """Create all tables."""
    success = await setup_database()
    if success:
        print("Database tables created successfully!")
    else:
        print("Failed to initialize database!")


if __name__ == "__main__":
    asyncio.run(init_db())
