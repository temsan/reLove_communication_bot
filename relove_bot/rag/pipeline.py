from ..db.session import SessionLocal
from ..db.models import UserActivityLog
from sqlalchemy import select

from .llm import LLM
from ..db.models import User, UserActivityLog
from sqlalchemy import select
from datetime import datetime
from relove_bot.services.llm_service import llm_service
from relove_bot.services.prompts import RAG_TEXT_SUMMARY_PROMPT

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

    # Сохраняем summary и историю диалога в user.context
    user.context = user.context or {}
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
        metadata={"username": user.username, "context": user.context}
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

async def analyze_text(text: str) -> str:
    """
    Анализирует текст с помощью LLM
    """
    try:
        result = await llm_service.analyze_text(
            prompt=text,
            system_prompt="Сделай краткое информативное summary для следующего текста.",
            max_tokens=128
        )
        return result
    except Exception as e:
        logger.error(f"Ошибка при анализе текста: {e}")
        return ""

async def process_text(text: str) -> str:
    """
    Обрабатывает текст с помощью RAG.
    
    Args:
        text: Текст для обработки
        
    Returns:
        str: Результат обработки или пустая строка в случае ошибки
    """
    try:
        result = await llm_service.analyze_text(
            text=text,
            system_prompt=RAG_TEXT_SUMMARY_PROMPT,
            max_tokens=64
        )
        
        if not result:
            return ''
            
        return result.strip()
        
    except Exception as e:
        logger.error(f"Ошибка при обработке текста: {e}", exc_info=True)
        return ''
