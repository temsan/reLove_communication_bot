import asyncio
from typing import Dict, List, Optional
from relove_bot.db.models import User
from relove_bot.db.database import get_db_session

class InMemoryUserIndex:
    def __init__(self, users: List[User]):
        self.by_id: Dict[int, User] = {u.id: u for u in users}
        self.by_username: Dict[str, User] = {u.username: u for u in users if u.username}
        self.by_first_name: Dict[str, List[User]] = {}
        for u in users:
            if u.first_name:
                self.by_first_name.setdefault(u.first_name.lower(), []).append(u)

    def find_by_id(self, user_id: int) -> Optional[User]:
        return self.by_id.get(user_id)

    def find_by_username(self, username: str) -> Optional[User]:
        return self.by_username.get(username)

    def find_by_first_name(self, name: str) -> List[User]:
        return self.by_first_name.get(name.lower(), [])

from sqlalchemy import select

async def load_all_users():
    async for session in get_db_session():
        from relove_bot.db.models import User
        result = await session.execute(select(User))
        users = result.scalars().all()
        return users

# Глобальный индекс (инициализируется при старте)
user_memory_index: Optional[InMemoryUserIndex] = None

async def build_user_memory_index():
    global user_memory_index
    users = await load_all_users()
    user_memory_index = InMemoryUserIndex(users)
    print(f"[MemoryIndex] Загружено пользователей в память: {len(users)}")
