"""Проверка состояния БД перед заполнением"""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from relove_bot.db.session import async_session
from sqlalchemy import text

async def check():
    async with async_session() as s:
        r = await s.execute(text('''
            SELECT 
                COUNT(*) as total,
                COUNT(profile) as with_profile,
                COUNT(CASE WHEN profile_version = 2 THEN 1 END) as v2_profiles,
                COUNT(CASE WHEN profile_version IS NULL AND profile IS NOT NULL THEN 1 END) as old_format
            FROM users
        '''))
        row = r.fetchone()
        result = dict(row._mapping)
        print(f"\n{'='*60}")
        print("DATABASE STATE")
        print(f"{'='*60}")
        print(f"Total users: {result['total']}")
        print(f"With profile: {result['with_profile']}")
        print(f"V2 profiles (new format): {result['v2_profiles']}")
        print(f"Old format (needs refill): {result['old_format']}")
        print(f"{'='*60}\n")

asyncio.run(check())
