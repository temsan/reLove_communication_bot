from typing import Optional, Dict, Any, List, Union
from sqlalchemy import create_engine, select, update, or_
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError
import logging
import os
import json
from datetime import datetime
from pathlib import Path
import sys

# Добавляем корень проекта в PYTHONPATH для корректного импорта
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from relove_bot.db.models import User, GenderEnum, UserActivityLog, Base
from relove_bot.db.database import get_db_url

logger = logging.getLogger(__name__)

class DatabaseService:
    """Сервис для работы с базой данных пользователей"""
    
    def __init__(self, db_url: Optional[str] = None):
        """Инициализация сервиса с подключением к БД"""
        self.db_url = db_url or get_db_url()
        self.engine = create_engine(self.db_url)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        
        # Создаем таблицы, если их нет
        Base.metadata.create_all(bind=self.engine)
    
    def get_session(self) -> Session:
        """Получить новую сессию БД"""
        return self.SessionLocal()
    
    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Получить данные пользователя по ID"""
        try:
            with self.get_session() as session:
                user = session.get(User, user_id)
                if user:
                    return self._user_to_dict(user)
                return None
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при получении пользователя {user_id}: {e}")
            return None
    
    def get_user_profile_summary(self, user_id: int, refresh: bool = False) -> Optional[Dict[str, Any]]:
        """
        Получить выжимку профиля пользователя
        
        Args:
            user_id: ID пользователя
            refresh: Если True, обновить сводку перед возвратом
            
        Returns:
            Словарь с данными профиля или None в случае ошибки
        """
        try:
            with self.get_session() as session:
                user = session.get(User, user_id)
                if not user:
                    return None
                    
                # Если нужно обновить сводку или её нет
                if refresh or not user.profile_summary:
                    profile_data = self._generate_profile_summary(user)
                    user.profile_summary = profile_data
                    session.commit()
                
                # Возвращаем как словарь, если это строка JSON, иначе как есть
                if isinstance(user.profile_summary, str):
                    try:
                        return json.loads(user.profile_summary)
                    except (json.JSONDecodeError, TypeError):
                        return {"summary": user.profile_summary}
                return user.profile_summary or {"summary": "Информация о профиле отсутствует"}
                
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при получении профиля пользователя {user_id}: {e}")
            return None
            
    def _generate_profile_summary(self, user: User) -> Dict[str, Any]:
        """Сгенерировать сводку профиля на основе данных пользователя"""
        summary = {
            "user_id": user.id,
            "name": f"{user.first_name or ''} {user.last_name or ''}".strip() or "Анонимный пользователь",
            "gender": user.gender.value if user.gender else "не указан",
            "registration_date": user.registration_date.isoformat() if user.registration_date else None,
            "last_seen": user.last_seen_date.isoformat() if user.last_seen_date else None,
            "markers": user.markers or {},
            "is_active": user.is_active,
            "is_admin": user.is_admin,
            "analysis_timestamp": datetime.utcnow().isoformat()
        }
        
        # Добавляем дополнительную аналитику, если есть маркеры
        if user.markers:
            summary["analysis"] = self._analyze_markers(user.markers)
            
        return summary
        
    def _analyze_markers(self, markers: Dict[str, Any]) -> Dict[str, Any]:
        """Проанализировать маркеры пользователя"""
        analysis = {}
        
        # Анализ эмоциональных маркеров
        emotional_markers = ["mood", "emotional_state", "stress_level"]
        emotional_data = {k: v for k, v in markers.items() if k in emotional_markers}
        if emotional_data:
            analysis["emotional"] = self._analyze_emotional_markers(emotional_data)
            
        # Анализ поведенческих маркеров
        behavioral_markers = ["activity_level", "interaction_frequency", "preferred_topics"]
        behavioral_data = {k: v for k, v in markers.items() if k in behavioral_markers}
        if behavioral_data:
            analysis["behavioral"] = behavioral_data
            
        # Анализ социальных маркеров
        social_markers = ["social_activity", "relationship_status", "communication_style"]
        social_data = {k: v for k, v in markers.items() if k in social_markers}
        if social_data:
            analysis["social"] = social_data
            
        # Анализ результатов диагностики
        diagnostic_markers = ["psychotype", "journey_stage", "diagnostic_results"]
        diagnostic_data = {k: v for k, v in markers.items() if k in diagnostic_markers}
        if diagnostic_data:
            analysis["diagnostic"] = self._analyze_diagnostic_markers(diagnostic_data)
            
        return analysis
        
    def _analyze_emotional_markers(self, markers: Dict[str, Any]) -> Dict[str, Any]:
        """Проанализировать эмоциональные маркеры"""
        result = {
            "overall_mood": None,
            "stability": "средняя",
            "trend": "стабильный",
            "risk_factors": []
        }
        
        # Анализ настроения
        if "mood" in markers:
            mood = markers["mood"]
            if isinstance(mood, str):
                mood = mood.lower()
                
            mood_map = {
                "happy": "хорошее",
                "sad": "плохое",
                "neutral": "нейтральное",
                "anxious": "тревожное",
                "excited": "приподнятое"
            }
            
            result["overall_mood"] = mood_map.get(mood, mood)
            
        # Анализ уровня стресса
        if "stress_level" in markers:
            stress = markers["stress_level"]
            if isinstance(stress, (int, float)):
                if stress > 7:
                    result["risk_factors"].append("высокий уровень стресса")
                elif stress > 4:
                    result["risk_factors"].append("умеренный уровень стресса")
                    
        return result
    
    def _analyze_diagnostic_markers(self, markers: Dict[str, Any]) -> Dict[str, Any]:
        """Проанализировать маркеры диагностики"""
        result = {
            "psychotype": None,
            "journey_stage": None,
            "recommendations": [],
            "last_diagnostic": None
        }
        
        # Анализ психотипа
        if "psychotype" in markers:
            psychotype = markers["psychotype"]
            result["psychotype"] = {
                "type": psychotype,
                "description": self._get_psychotype_description(psychotype)
            }
            
        # Анализ этапа пути героя
        if "journey_stage" in markers:
            stage = markers["journey_stage"]
            result["journey_stage"] = {
                "stage": stage,
                "description": self._get_journey_stage_description(stage)
            }
            
        # Анализ результатов диагностики
        if "diagnostic_results" in markers:
            diagnostic = markers["diagnostic_results"]
            if isinstance(diagnostic, dict):
                result["last_diagnostic"] = {
                    "timestamp": diagnostic.get("created_at"),
                    "answers": diagnostic.get("answers", {}),
                    "recommended_stream": diagnostic.get("recommended_stream")
                }
                
                # Формируем рекомендации на основе результатов
                if result["psychotype"] and result["journey_stage"]:
                    result["recommendations"] = self._generate_diagnostic_recommendations(
                        result["psychotype"]["type"],
                        result["journey_stage"]["stage"]
                    )
                    
        return result
        
    def _get_psychotype_description(self, psychotype: str) -> Dict[str, Any]:
        """Получить описание психотипа"""
        descriptions = {
            "matrix": {
                "name": "Матричный тип",
                "description": "Находится в начале пути трансформации, сознание под влиянием матричных программ",
                "strengths": [
                    "Высокая адаптивность к социальным нормам",
                    "Хорошая способность к аналитическому мышлению",
                    "Сильная мотивация к достижению целей"
                ],
                "challenges": [
                    "Ограниченное восприятие реальности",
                    "Зависимость от внешних оценок",
                    "Страх выхода из зоны комфорта"
                ]
            },
            "seeker": {
                "name": "Искатель",
                "description": "Начал задавать вопросы и искать ответы за пределами привычной реальности",
                "strengths": [
                    "Открытость новому опыту",
                    "Готовность к изменениям",
                    "Развитая интуиция"
                ],
                "challenges": [
                    "Неуверенность в выбранном пути",
                    "Периодические сомнения",
                    "Сложности с интеграцией нового опыта"
                ]
            },
            "transformer": {
                "name": "Трансформер",
                "description": "Активно работает над своей трансформацией и помогает другим на их пути",
                "strengths": [
                    "Глубокое понимание процессов трансформации",
                    "Способность к эмпатии и поддержке других",
                    "Сильная связь с высшим Я"
                ],
                "challenges": [
                    "Баланс между личным ростом и помощью другим",
                    "Интеграция духовного опыта в повседневную жизнь",
                    "Работа с кармическими задачами"
                ]
            }
        }
        return descriptions.get(psychotype, {
            "name": "Не определен",
            "description": "Психотип не определен",
            "strengths": [],
            "challenges": []
        })
        
    def _get_journey_stage_description(self, stage: str) -> Dict[str, Any]:
        """Получить описание этапа пути героя"""
        descriptions = {
            "ordinary_world": {
                "name": "Обычный мир",
                "description": "Находится в привычной реальности, но чувствует, что что-то не так",
                "next_steps": [
                    "Начать задавать себе важные вопросы",
                    "Изучить материалы о трансформации сознания",
                    "Найти единомышленников"
                ]
            },
            "call_to_adventure": {
                "name": "Зов к приключению",
                "description": "Получил знак или импульс, что пора что-то менять в своей жизни",
                "next_steps": [
                    "Признать необходимость изменений",
                    "Исследовать новые возможности",
                    "Подготовиться к трансформации"
                ]
            },
            "refusal": {
                "name": "Отказ от призыва",
                "description": "Испытывает страх и сомнения перед началом пути трансформации",
                "next_steps": [
                    "Работать со страхами и ограничениями",
                    "Найти поддержку и вдохновение",
                    "Сделать первый шаг к изменениям"
                ]
            },
            "meeting_mentor": {
                "name": "Встреча с наставником",
                "description": "Готов принять помощь и руководство на своем пути",
                "next_steps": [
                    "Найти подходящего наставника или сообщество",
                    "Открыться новому опыту",
                    "Начать практиковать полученные знания"
                ]
            },
            "crossing_threshold": {
                "name": "Переход порога",
                "description": "Сделал решительный шаг в новую реальность",
                "next_steps": [
                    "Интегрировать новый опыт",
                    "Развивать новые навыки",
                    "Поддерживать связь с наставником"
                ]
            }
        }
        return descriptions.get(stage, {
            "name": "Не определен",
            "description": "Этап пути не определен",
            "next_steps": []
        })
        
    def _generate_diagnostic_recommendations(self, psychotype: str, journey_stage: str) -> List[str]:
        """Сгенерировать рекомендации на основе психотипа и этапа пути"""
        recommendations = {
            ("matrix", "ordinary_world"): [
                "Начните с базового потока трансформации",
                "Изучите материалы о природе реальности",
                "Присоединитесь к сообществу единомышленников"
            ],
            ("matrix", "call_to_adventure"): [
                "Пройдите поток пробуждения",
                "Исследуйте новые возможности",
                "Начните вести дневник трансформации"
            ],
            ("seeker", "refusal"): [
                "Пройдите поток преодоления страхов",
                "Работайте с ограничивающими убеждениями",
                "Найдите поддержку в сообществе"
            ],
            ("seeker", "meeting_mentor"): [
                "Присоединитесь к потоку наставничества",
                "Регулярно практикуйте полученные знания",
                "Делитесь своим опытом с другими"
            ],
            ("transformer", "crossing_threshold"): [
                "Пройдите продвинутый поток трансформации",
                "Начните помогать другим на их пути",
                "Интегрируйте духовный опыт в повседневную жизнь"
            ]
        }
        return recommendations.get((psychotype, journey_stage), [
            "Начните с базового потока трансформации",
            "Изучите материалы о природе реальности",
            "Присоединитесь к сообществу единомышленников"
        ])
    
    def get_user_history_summary(self, user_id: int, days: int = 30, limit: int = 100) -> Dict[str, Any]:
        """
        Получить сводку по истории общения пользователя с ботом
        
        Args:
            user_id: ID пользователя
            days: Количество дней для анализа
            limit: Максимальное количество записей для анализа
            
        Returns:
            Словарь с анализом истории общения
        """
        try:
            with self.get_session() as session:
                # Получаем историю активности
                from datetime import datetime, timedelta
                from sqlalchemy import desc
                
                time_threshold = datetime.utcnow() - timedelta(days=days)
                
                # Получаем последние записи активности
                activities = session.query(UserActivityLog).filter(
                    UserActivityLog.user_id == user_id,
                    UserActivityLog.timestamp >= time_threshold
                ).order_by(desc(UserActivityLog.timestamp)).limit(limit).all()
                
                if not activities:
                    return {
                        "status": "no_data",
                        "message": f"Нет данных о деятельности за последние {days} дней",
                        "analysis_timestamp": datetime.utcnow().isoformat()
                    }
                
                # Анализируем активность
                activity_summary = self._analyze_activity(activities)
                
                # Формируем итоговый результат
                result = {
                    "status": "success",
                    "total_activities": len(activities),
                    "time_period": {
                        "start": min(a.timestamp.isoformat() for a in activities),
                        "end": max(a.timestamp.isoformat() for a in activities),
                        "days": days
                    },
                    "activity_summary": activity_summary,
                    "analysis_timestamp": datetime.utcnow().isoformat()
                }
                
                # Обновляем историю в профиле пользователя
                user = session.get(User, user_id)
                if user:
                    if user.history_summary is None or not isinstance(user.history_summary, dict):
                        user.history_summary = {}
                    
                    if "history" not in user.history_summary:
                        user.history_summary["history"] = []
                    
                    # Добавляем новый анализ в историю (сохраняем последние 10 анализов)
                    user.history_summary["history"].insert(0, {
                        "timestamp": datetime.utcnow().isoformat(),
                        "analysis": activity_summary
                    })
                    
                    # Ограничиваем историю 10 последними анализами
                    if len(user.history_summary["history"]) > 10:
                        user.history_summary["history"] = user.history_summary["history"][:10]
                    
                    session.commit()
                
                return result
                
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при получении истории пользователя {user_id}: {e}")
            return {
                "status": "error",
                "message": str(e),
                "analysis_timestamp": datetime.utcnow().isoformat()
            }
    
    def _analyze_activity(self, activities: list) -> Dict[str, Any]:
        """Проанализировать активность пользователя"""
        from collections import defaultdict
        
        # Собираем статистику по типам активности
        activity_types = defaultdict(int)
        activity_hours = defaultdict(int)
        activity_days = defaultdict(int)
        
        for activity in activities:
            activity_types[activity.activity_type] += 1
            activity_hours[activity.timestamp.hour] += 1
            activity_days[activity.timestamp.weekday()] += 1
        
        # Анализ наиболее активного времени
        peak_hour = max(activity_hours.items(), key=lambda x: x[1])[0] if activity_hours else None
        
        # Анализ наиболее активного дня недели
        weekdays = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
        peak_day = weekdays[max(activity_days.items(), key=lambda x: x[1])[0]] if activity_days else None
        
        # Собираем результаты анализа
        return {
            "total_activities": len(activities),
            "activity_types": dict(activity_types),
            "peak_hour": peak_hour,
            "peak_day": peak_day,
            "first_activity": activities[-1].timestamp.isoformat(),
            "last_activity": activities[0].timestamp.isoformat(),
            "activity_frequency": self._calculate_activity_frequency(activities)
        }
    
    def _calculate_activity_frequency(self, activities: list) -> Dict[str, float]:
        """Рассчитать частоту активности"""
        if not activities:
            return {}
            
        # Сортируем по времени
        sorted_activities = sorted(activities, key=lambda x: x.timestamp)
        
        # Рассчитываем интервалы между активностями
        intervals = []
        for i in range(1, len(sorted_activities)):
            delta = sorted_activities[i].timestamp - sorted_activities[i-1].timestamp
            intervals.append(delta.total_seconds() / 3600)  # в часах
        
        # Рассчитываем статистику
        if not intervals:
            return {}
            
        avg_interval = sum(intervals) / len(intervals)
        max_interval = max(intervals)
        min_interval = min(intervals)
        
        # Определяем частоту
        if avg_interval < 1:
            frequency = "очень высокая"
        elif avg_interval < 6:
            frequency = "высокая"
        elif avg_interval < 24:
            frequency = "средняя"
        else:
            frequency = "низкая"
            
        return {
            "average_interval_hours": round(avg_interval, 2),
            "max_interval_hours": round(max_interval, 2),
            "min_interval_hours": round(min_interval, 2),
            "frequency_level": frequency
        }
    
    def get_user_markers(self, user_id: int) -> Dict[str, Any]:
        """Получить маркеры пользователя"""
        try:
            with self.get_session() as session:
                user = session.get(User, user_id)
                if user and user.markers:
                    return user.markers
                return {}
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при получении маркеров пользователя {user_id}: {e}")
            return {}
    
    def update_user_marker(self, user_id: int, key: str, value: Any) -> bool:
        """Обновить маркер пользователя"""
        try:
            with self.get_session() as session:
                user = session.get(User, user_id)
                if not user:
                    return False
                
                if user.markers is None:
                    user.markers = {}
                
                user.markers[key] = value
                session.commit()
                return True
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Ошибка при обновлении маркера пользователя {user_id}: {e}")
            return False
    
    def log_activity(self, user_id: int, activity_type: str, details: Optional[Dict] = None) -> bool:
        """Записать активность пользователя"""
        try:
            with self.get_session() as session:
                activity = UserActivityLog(
                    user_id=user_id,
                    activity_type=activity_type,
                    details=details or {}
                )
                session.add(activity)
                session.commit()
                return True
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Ошибка при записи активности пользователя {user_id}: {e}")
            return False
    
    def search_users_by_markers(self, markers: Dict[str, Any], limit: int = 10) -> List[Dict[str, Any]]:
        """Поиск пользователей по маркерам"""
        try:
            with self.get_session() as session:
                query = select(User)
                
                # Добавляем условия для каждого маркера
                for key, value in markers.items():
                    query = query.where(User.markers[key].astext == str(value))
                
                users = session.execute(query.limit(limit)).scalars().all()
                return [self._user_to_dict(user) for user in users]
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при поиске пользователей по маркерам: {e}")
            return []
    
    def _user_to_dict(self, user: User) -> Dict[str, Any]:
        """Конвертировать объект User в словарь"""
        def safe_serialize(obj):
            """Безопасно сериализовать объект в JSON-совместимый формат"""
            if obj is None:
                return None
            if hasattr(obj, 'isoformat'):
                return obj.isoformat()
            if hasattr(obj, 'value'):  # Для enum
                return obj.value
            return str(obj)
            
        # Преобразуем историю и профиль в словари, если они в формате JSON
        try:
            profile_summary = (
                json.loads(user.profile_summary) 
                if isinstance(user.profile_summary, str) 
                else user.profile_summary
            )
        except (json.JSONDecodeError, TypeError):
            profile_summary = user.profile_summary
            
        try:
            history_summary = (
                json.loads(user.history_summary)
                if isinstance(user.history_summary, str)
                else user.history_summary
            )
        except (json.JSONDecodeError, TypeError):
            history_summary = user.history_summary
        
        # Формируем словарь с пользователем
        user_dict = {
            "id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "gender": user.gender.value if user.gender else None,
            "profile_summary": profile_summary,
            "history_summary": history_summary,
            "markers": user.markers or {},
            "is_admin": user.is_admin,
            "is_active": user.is_active,
            "registration_date": safe_serialize(user.registration_date),
            "last_seen_date": safe_serialize(user.last_seen_date)
        }
        
        # Удаляем None значения для чистоты вывода
        return {k: v for k, v in user_dict.items() if v is not None}

# Создаем глобальный экземпляр сервиса
db_service = DatabaseService()

def get_db_service() -> DatabaseService:
    """Получить экземпляр сервиса БД"""
    return db_service
