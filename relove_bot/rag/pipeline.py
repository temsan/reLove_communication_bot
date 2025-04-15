from ..db.session import SessionLocal
from ..db.models import UserActivityLog
from sqlalchemy import select

async def get_user_context(user_id: int, limit: int = 5) -> str:
    async with SessionLocal() as session:
        result = await session.execute(
            select(UserActivityLog.summary)
            .where(UserActivityLog.user_id == user_id)
            .order_by(UserActivityLog.timestamp.desc())
            .limit(limit)
        )
        summaries = [row[0] for row in result.fetchall()]
    return "\n".join(summaries)
