from ..db.session import SessionLocal
from ..db.models import UserActivityLog
from sqlalchemy import select

from .llm import LLM
from ..db.models import User, UserActivityLog
from sqlalchemy import select
from datetime import datetime

async def aggregate_profile_summary(user_id, session):
    # Собрать все сообщения пользователя
    result = await session.execute(
        select(UserActivityLog.summary)
        .where(UserActivityLog.user_id == user_id)
        .where(UserActivityLog.activity_type == "message")
        .order_by(UserActivityLog.timestamp.asc())
    )
    all_messages = [row[0] for row in result.fetchall()]
    # Собрать профильные данные пользователя
    user = await session.get(User, user_id)
    profile_info = []
    if user:
        if user.username:
            profile_info.append(f"Username: {user.username}")
        if user.first_name:
            profile_info.append(f"Имя: {user.first_name}")
        if user.last_name:
            profile_info.append(f"Фамилия: {user.last_name}")
        # bio и др. поля можно добавить по необходимости
    text_for_summary = (
        "Профиль пользователя:\n" + "\n".join(profile_info) +
        "\n\nСообщения пользователя:\n" + "\n".join(all_messages)
    )
    if not all_messages and not profile_info:
        return
    llm = LLM()
    summary_struct = await llm.analyze_content(
        f"Проанализируй профиль и сообщения пользователя. Определи этап пути героя и дай рекомендации, как его пробудить:\n{text_for_summary}"
    )
    # Получаем эмбеддинг summary профиля
    from ..db.vector import upsert_user_embedding
    from .llm import get_text_embedding
    embedding = await get_text_embedding(summary)

    # Примитивное извлечение этапа пути героя из summary (можно заменить на NLP)
    import re
    stage = None
    stage_match = re.search(r"Этап пути героя: ([^\n]+)", summary)
    if stage_match:
        stage = stage_match.group(1).strip()
    # Сохраняем этап, summary и историю диалога в user.context
    user.context = user.context or {}
    if stage:
        user.context["hero_path_stage"] = stage
    user.context["summary"] = summary
    # Формируем сжатый контекст для общения и пробуждения пользователя (relove_context)
    # Например, summary + ключевые выводы для пробуждения и направления в relove (мужской/женский)
    # Здесь можно использовать simple NLP или шаблон, либо добавить анализ пола пользователя
    relove_context = f"Профиль: {summary}\nПоток: {'мужской' if user.username and user.username.endswith('man') else 'женский'}\nРекомендация: Сфокусируйся на пробуждении и развитии в потоке reLove."
    user.context["relove_context"] = relove_context
    await session.commit()

    # Сохраняем эмбеддинг в Qdrant
    upsert_user_embedding(
        user_id=user_id,
        embedding=embedding,
        metadata={"username": user.username, "hero_path_stage": user.context.get("hero_path_stage")}
    )
    log = UserActivityLog(
        user_id=user_id,
        chat_id=None,
        activity_type="profile_summary",
        timestamp=datetime.utcnow(),
        details=None,
        summary=summary
    )
    session.add(log)
    await session.commit()

async def get_profile_summary(user_id, session):
    result = await session.execute(
        select(UserActivityLog.summary)
        .where(UserActivityLog.user_id == user_id)
        .where(UserActivityLog.activity_type == "profile_summary")
        .order_by(UserActivityLog.timestamp.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    return row or ""
