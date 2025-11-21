import logging
from ..db.session import SessionLocal
from ..db.models import UserActivityLog
from sqlalchemy import select

from .llm import LLM
from ..db.models import User, UserActivityLog
from sqlalchemy import select
from datetime import datetime
from relove_bot.services.llm_service import llm_service
from relove_bot.services.prompts import RAG_TEXT_SUMMARY_PROMPT

logger = logging.getLogger(__name__)

async def aggregate_profile_summary(user_id, session):
    """Агрегирует профиль пользователя из его активности"""
    # Собрать все сообщения пользователя
    result = await session.execute(
        select(UserActivityLog)
        .where(UserActivityLog.user_id == user_id)
        .where(UserActivityLog.activity_type == "message")
        .order_by(UserActivityLog.timestamp.asc())
    )
    all_logs = result.scalars().all()
    all_messages = [log.details.get('text', '') if log.details else '' for log in all_logs]
    
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
    
    text_for_summary = (
        "Профиль пользователя:\n" + "\n".join(profile_info) +
        "\n\nСообщения пользователя:\n" + "\n".join(filter(None, all_messages))
    )
    
    if not all_messages and not profile_info:
        return
    
    llm = LLM()
    summary_struct = await llm.analyze_content(
        f"Проанализируй профиль и сообщения пользователя. Определи этап пути героя и дай рекомендации:\n{text_for_summary}"
    )
    
    # Извлекаем summary
    if isinstance(summary_struct, dict):
        summary = summary_struct.get('summary', str(summary_struct))
    else:
        summary = str(summary_struct)
    
    # Сохраняем summary в markers пользователя
    user.markers = user.markers or {}
    user.markers["summary"] = summary
    user.markers["profile_updated_at"] = datetime.now().isoformat()
    await session.commit()
    
    # Сохраняем лог профиля
    log = UserActivityLog(
        user_id=user_id,
        chat_id=None,
        activity_type="profile_summary",
        details={"summary": summary}
    )
    session.add(log)
    await session.commit()

async def get_profile_summary(user_id, session):
    """Получает последний профиль пользователя"""
    # Сначала проверяем markers пользователя
    user = await session.get(User, user_id)
    if user and user.markers and user.markers.get("summary"):
        return user.markers.get("summary", "")
    
    # Если нет в markers, ищем в логах
    result = await session.execute(
        select(UserActivityLog)
        .where(UserActivityLog.user_id == user_id)
        .where(UserActivityLog.activity_type == "profile_summary")
        .order_by(UserActivityLog.timestamp.desc())
        .limit(1)
    )
    log = result.scalar_one_or_none()
    if log and log.details:
        return log.details.get("summary", "")
    
    return ""

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
