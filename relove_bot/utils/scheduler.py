from apscheduler.schedulers.asyncio import AsyncIOScheduler
from relove_bot.rag.pipeline import aggregate_profile_summary
from relove_bot.db.session import SessionLocal

async def job_update_user_profiles():
    async with SessionLocal() as session:
        # Получить всех пользователей
        from relove_bot.db.models import User
        result = await session.execute(User.__table__.select())
        users = result.fetchall()
        for user_row in users:
            user_id = user_row.id if hasattr(user_row, 'id') else user_row[0]
            try:
                await aggregate_profile_summary(user_id, session)
            except Exception as e:
                print(f"[Scheduler] Ошибка при обновлении профиля user_id={user_id}: {e}")


def start_scheduler():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(job_update_user_profiles, "interval", minutes=30)
    scheduler.start()
    print("[Scheduler] Фоновая агрегация профилей пользователей запущена (каждые 30 минут)")
