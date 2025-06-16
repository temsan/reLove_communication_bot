from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy import select, desc, and_
from sqlalchemy.orm import Session
import logging
import json

# Добавляем корень проекта в PYTHONPATH
import sys
from pathlib import Path
project_root = str(Path(__file__).parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from relove_bot.db.models import UserActivityLog, User
from relove_bot.db.database import get_db_url, SessionLocal

logger = logging.getLogger(__name__)

class MessageHistoryService:
    """Сервис для работы с историей сообщений пользователей"""
    
    def __init__(self, db_session: Optional[Session] = None):
        """Инициализация сервиса"""
        self.db = db_session or SessionLocal()
    
    def get_recent_messages(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Получить последние сообщения пользователя"""
        try:
            stmt = (
                select(UserActivityLog)
                .where(UserActivityLog.user_id == user_id)
                .where(UserActivityLog.activity_type.in_(["message", "command"]))
                .order_by(desc(UserActivityLog.timestamp))
                .limit(limit)
            )
            
            messages = self.db.execute(stmt).scalars().all()
            return [
                {
                    "id": msg.id,
                    "text": msg.details.get("text", "") if msg.details else "",
                    "timestamp": msg.timestamp.isoformat(),
                    "type": msg.activity_type
                }
                for msg in messages
            ]
        except Exception as e:
            logger.error(f"Ошибка при получении истории сообщений для пользователя {user_id}: {e}")
            return []
    
    def get_conversation_history(
        self, 
        user_id: int, 
        days: int = 30,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Получить историю общения за указанный период"""
        try:
            date_from = datetime.utcnow() - timedelta(days=days)
            
            stmt = (
                select(UserActivityLog)
                .where(UserActivityLog.user_id == user_id)
                .where(UserActivityLog.activity_type.in_(["message", "command", "button_press"]))
                .where(UserActivityLog.timestamp >= date_from)
                .order_by(UserActivityLog.timestamp)
                .limit(limit)
            )
            
            messages = self.db.execute(stmt).scalars().all()
            
            # Форматируем сообщения для удобства использования
            formatted_messages = []
            for msg in messages:
                details = msg.details or {}
                formatted_msg = {
                    "id": msg.id,
                    "timestamp": msg.timestamp.isoformat(),
                    "type": msg.activity_type,
                    "content": details.get("text") or details.get("data") or "",
                    "intent": details.get("intent", {}).get("name") if isinstance(details.get("intent"), dict) else None,
                    "entities": details.get("entities", [])
                }
                formatted_messages.append(formatted_msg)
            
            return formatted_messages
            
        except Exception as e:
            logger.error(f"Ошибка при получении истории общения для пользователя {user_id}: {e}")
            return []
    
    def analyze_conversation_patterns(self, user_id: int) -> Dict[str, Any]:
        """Анализ паттернов общения пользователя"""
        try:
            # Получаем историю сообщений за последние 30 дней
            messages = self.get_conversation_history(user_id, days=30)
            
            if not messages:
                return {"status": "no_data", "message": "Недостаточно данных для анализа"}
            
            # Анализ частоты сообщений
            message_count = len(messages)
            days_active = len({msg["timestamp"][:10] for msg in messages})  # Уникальные дни
            avg_messages_per_day = round(message_count / max(1, days_active), 1)
            
            # Анализ временных паттернов
            hour_counts = {i: 0 for i in range(24)}
            for msg in messages:
                try:
                    hour = datetime.fromisoformat(msg["timestamp"]).hour
                    hour_counts[hour] += 1
                except (ValueError, KeyError):
                    continue
            
            # Находим пиковые часы активности
            peak_hours = [
                f"{h:02d}:00-{h+1:02d}:00" 
                for h, count in hour_counts.items() 
                if count == max(hour_counts.values())
            ]
            
            # Анализ интентов (если доступно)
            intents = {}
            for msg in messages:
                if "intent" in msg and msg["intent"]:
                    intent = msg["intent"]
                    intents[intent] = intents.get(intent, 0) + 1
            
            # Определение преобладающего настроения (упрощенно)
            mood_keywords = {
                "positive": ["рад", "отлично", "спасибо", "хорошо", "прекрасно", "замечательно"],
                "negative": ["плохо", "грустно", "устал", "устала", "злюсь", "раздражает"],
                "neutral": ["думаю", "считаю", "может быть", "наверное", "возможно"]
            }
            
            mood_scores = {"positive": 0, "negative": 0, "neutral": 0}
            for msg in messages:
                content = msg.get("content", "").lower()
                for mood, keywords in mood_keywords.items():
                    if any(keyword in content for keyword in keywords):
                        mood_scores[mood] += 1
            
            dominant_mood = max(mood_scores.items(), key=lambda x: x[1])[0] if mood_scores else "neutral"
            
            return {
                "status": "success",
                "message_count": message_count,
                "days_active": days_active,
                "avg_messages_per_day": avg_messages_per_day,
                "peak_hours": peak_hours,
                "top_intents": dict(sorted(intents.items(), key=lambda x: x[1], reverse=True)[:5]),
                "mood_analysis": {
                    "dominant_mood": dominant_mood,
                    "scores": mood_scores
                },
                "analysis_timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Ошибка при анализе паттернов общения для пользователя {user_id}: {e}")
            return {"status": "error", "message": str(e)}
    
    def get_user_engagement_metrics(self, user_id: int) -> Dict[str, Any]:
        """Получить метрики вовлеченности пользователя"""
        try:
            # Получаем историю активности за последние 30 дней
            date_from = datetime.utcnow() - timedelta(days=30)
            
            stmt = (
                select(UserActivityLog)
                .where(UserActivityLog.user_id == user_id)
                .where(UserActivityLog.timestamp >= date_from)
            )
            
            activities = self.db.execute(stmt).scalars().all()
            
            if not activities:
                return {"status": "no_data", "message": "Недостаточно данных для анализа"}
            
            # Группируем по дням
            days_active = {}
            activity_types = {}
            
            for activity in activities:
                day = activity.timestamp.date().isoformat()
                days_active[day] = days_active.get(day, 0) + 1
                
                # Считаем активность по типам
                activity_types[activity.activity_type] = activity_types.get(activity.activity_type, 0) + 1
            
            # Рассчитываем метрики
            total_activities = len(activities)
            unique_days = len(days_active)
            avg_activities_per_day = round(total_activities / unique_days, 1) if unique_days > 0 else 0
            
            # Находим самый активный день
            if days_active:
                peak_day, peak_count = max(days_active.items(), key=lambda x: x[1])
            else:
                peak_day, peak_count = None, 0
            
            return {
                "status": "success",
                "total_activities": total_activities,
                "unique_days": unique_days,
                "avg_activities_per_day": avg_activities_per_day,
                "peak_day": {"date": peak_day, "count": peak_count} if peak_day else None,
                "activity_by_type": activity_types,
                "first_activity_date": min(act.timestamp.isoformat() for act in activities),
                "last_activity_date": max(act.timestamp.isoformat() for act in activities)
            }
            
        except Exception as e:
            logger.error(f"Ошибка при расчете метрик вовлеченности для пользователя {user_id}: {e}")
            return {"status": "error", "message": str(e)}

# Создаем глобальный экземпляр сервиса
message_history_service = MessageHistoryService()

def get_message_history_service() -> MessageHistoryService:
    """Получить экземпляр сервиса истории сообщений"""
    return message_history_service
