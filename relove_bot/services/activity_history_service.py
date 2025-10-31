"""
Сервис для работы с историей активности пользователей из UserActivityLog.
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, and_
from relove_bot.db.models import UserActivityLog

logger = logging.getLogger(__name__)


class ActivityHistoryService:
    """Сервис для работы с историей активности пользователей"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_recent_messages(
        self,
        user_id: int,
        days: int = 30,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Получает последние сообщения пользователя из UserActivityLog.
        
        Args:
            user_id: ID пользователя
            days: Количество дней для выборки
            limit: Максимальное количество записей
            
        Returns:
            Список сообщений в формате [{"role": "user", "content": "..."}, ...]
        """
        try:
            time_threshold = datetime.utcnow() - timedelta(days=days)
            
            query = (
                select(UserActivityLog)
                .where(
                    and_(
                        UserActivityLog.user_id == user_id,
                        UserActivityLog.timestamp >= time_threshold,
                        UserActivityLog.activity_type.in_(["message", "command"])
                    )
                )
                .order_by(desc(UserActivityLog.timestamp))
                .limit(limit)
            )
            
            result = await self.session.execute(query)
            activities = result.scalars().all()
            
            messages = []
            for activity in reversed(activities):  # Разворачиваем, чтобы было в хронологическом порядке
                details = activity.details or {}
                text = details.get("text") or details.get("command") or ""
                
                if text:
                    messages.append({
                        "role": "user",
                        "content": text,
                        "timestamp": activity.timestamp.isoformat(),
                        "type": activity.activity_type
                    })
            
            return messages
            
        except Exception as e:
            logger.error(f"Ошибка при получении истории сообщений для пользователя {user_id}: {e}", exc_info=True)
            return []
    
    async def get_conversation_text(
        self,
        user_id: int,
        days: int = 30,
        limit: int = 100
    ) -> str:
        """
        Получает текст всех сообщений пользователя для анализа.
        
        Args:
            user_id: ID пользователя
            days: Количество дней для выборки
            limit: Максимальное количество записей
            
        Returns:
            Текст всех сообщений, объединённый через перенос строки
        """
        messages = await self.get_recent_messages(user_id, days, limit)
        
        if not messages:
            return ""
        
        # Форматируем как диалог
        conversation_lines = []
        for msg in messages:
            conversation_lines.append(f"Пользователь ({msg['timestamp'][:10]}): {msg['content']}")
        
        return "\n".join(conversation_lines)
    
    async def get_activity_summary(
        self,
        user_id: int,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Получает сводку по активности пользователя.
        
        Returns:
            Словарь с метриками активности
        """
        try:
            time_threshold = datetime.utcnow() - timedelta(days=days)
            
            query = (
                select(UserActivityLog)
                .where(
                    and_(
                        UserActivityLog.user_id == user_id,
                        UserActivityLog.timestamp >= time_threshold
                    )
                )
                .order_by(desc(UserActivityLog.timestamp))
            )
            
            result = await self.session.execute(query)
            activities = result.scalars().all()
            
            if not activities:
                return {
                    "total_activities": 0,
                    "messages_count": 0,
                    "commands_count": 0,
                    "first_activity": None,
                    "last_activity": None
                }
            
            # Подсчитываем статистику
            messages_count = sum(1 for a in activities if a.activity_type == "message")
            commands_count = sum(1 for a in activities if a.activity_type == "command")
            
            return {
                "total_activities": len(activities),
                "messages_count": messages_count,
                "commands_count": commands_count,
                "first_activity": min(a.timestamp for a in activities).isoformat(),
                "last_activity": max(a.timestamp for a in activities).isoformat(),
                "days_analyzed": days
            }
            
        except Exception as e:
            logger.error(f"Ошибка при получении сводки активности для пользователя {user_id}: {e}", exc_info=True)
            return {}

