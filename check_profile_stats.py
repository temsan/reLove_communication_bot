import asyncio
from relove_bot.db.session import async_session
from relove_bot.db.models import User
from sqlalchemy import select, func, case, and_

async def check_stats():
    async with async_session() as session:
        # Всего пользователей
        result = await session.execute(
            select(func.count(User.id))
        )
        total = result.scalar()
        
        # Profile заполнено
        result = await session.execute(
            select(func.count(case((User.profile != None, 1))))
        )
        profile_filled = result.scalar()
        
        # Profile v2 (новый формат)
        result = await session.execute(
            select(func.count(case((User.profile_version == 2, 1))))
        )
        profile_v2 = result.scalar()
        
        # Gender заполнено
        result = await session.execute(
            select(func.count(case((User.gender != None, 1))))
        )
        gender_filled = result.scalar()
        
        # Hero stage заполнено
        result = await session.execute(
            select(func.count(case((User.hero_stage != None, 1))))
        )
        hero_stage_filled = result.scalar()
        
        # Photo заполнено
        result = await session.execute(
            select(func.count(case((User.photo_jpeg != None, 1))))
        )
        photo_filled = result.scalar()
        
        # Metaphysics заполнено
        result = await session.execute(
            select(func.count(case((User.metaphysics != None, 1))))
        )
        metaphysics_filled = result.scalar()
        
        # Streams заполнено
        result = await session.execute(
            select(func.count(case((User.streams != None, 1))))
        )
        streams_filled = result.scalar()
        
        print(f'\n{"="*60}')
        print(f'СТАТИСТИКА ЗАПОЛНЕНИЯ ПРОФИЛЕЙ ПОЛЬЗОВАТЕЛЕЙ')
        print(f'{"="*60}')
        print(f'Всего пользователей: {total}')
        print(f'Profile заполнено: {profile_filled} ({profile_filled*100//total if total else 0}%)')
        print(f'Profile v2 (новый формат): {profile_v2} ({profile_v2*100//total if total else 0}%)')
        print(f'Gender заполнено: {gender_filled} ({gender_filled*100//total if total else 0}%)')
        print(f'Hero stage заполнено: {hero_stage_filled} ({hero_stage_filled*100//total if total else 0}%)')
        print(f'Photo заполнено: {photo_filled} ({photo_filled*100//total if total else 0}%)')
        print(f'Metaphysics заполнено: {metaphysics_filled} ({metaphysics_filled*100//total if total else 0}%)')
        print(f'Streams заполнено: {streams_filled} ({streams_filled*100//total if total else 0}%)')
        print(f'{"="*60}\n')

if __name__ == '__main__':
    asyncio.run(check_stats())
