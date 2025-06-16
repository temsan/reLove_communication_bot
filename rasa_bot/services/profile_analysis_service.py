from typing import Dict, Any, List, Optional, Tuple, Union, DefaultDict
from datetime import datetime, timedelta
import logging
import json
import re
from collections import defaultdict, Counter
from pathlib import Path
import sys

# Добавляем корень проекта в PYTHONPATH
project_root = str(Path(__file__).parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from relove_bot.db.models import User, UserActivityLog, GenderEnum
from .message_history_service import get_message_history_service
from ..db_service import get_db_service

# Типы анализа
ANALYSIS_TYPES = [
    "emotional",      # Эмоциональное состояние
    "behavioral",     # Поведенческие паттерны
    "social",         # Социальные аспекты
    "cognitive",      # Когнитивные особенности
    "motivational"    # Мотивационные факторы
]

logger = logging.getLogger(__name__)

class ProfileAnalysisService:
    """Сервис для анализа психологического профиля пользователя"""
    
    def __init__(self):
        self.db_service = get_db_service()
        self.message_service = get_message_history_service()
        
        # Загружаем ключевые слова для анализа (можно вынести в конфиг)
        self.keywords = {
            # Эмоциональные состояния
            "anxiety": ["тревож", "беспоко", "страх", "паник", "волнуюсь", "боюсь", "испуг"],
            "depression": ["груст", "тоск", "плохое настроение", "нет сил", "устал", "устала", "подавлен"],
            "stress": ["стресс", "напряж", "устал", "устала", "выгорание", "утомлен"],
            "positive": ["рад", "счастлив", "отлично", "хорошо", "прекрасно", "замечательно", "восторг"],
            "anger": ["злой", "зла", "злюсь", "разозлился", "разозлилась", "раздражен", "бесит"],
            
            # Социальные аспекты
            "relationships": ["отношен", "парень", "девушка", "муж", "жена", "любов", "расста"],
            "family": ["семья", "мама", "папа", "родител", "брат", "сестра", "дети", "ребенок"],
            "work": ["работа", "начальник", "коллега", "проект", "дедлайн", "зарплата", "карьера"],
            "health": ["здоровье", "болит", "врач", "больничн", "лекарств", "анализ", "самочувствие"],
            
            # Когнитивные аспекты
            "planning": ["планирую", "цель", "планы", "намерен", "хочу", "мечтаю", "стремлюсь"],
            "reflection": ["думаю", "размышляю", "кажется", "возможно", "наверное", "может быть"],
            "certainty": ["точно", "конечно", "несомненно", "определенно", "точно знаю"],
            "uncertainty": ["не знаю", "сомневаюсь", "не уверен", "не уверена", "не понимаю"],
            
            # Поведенческие паттерны
            "activity": ["сделал", "сделала", "завершил", "завершила", "выполнил", "выполнила"],
            "procrastination": ["потом", "завтра", "некогда", "не хочу", "не могу", "лень"],
            "help": ["помоги", "подскажи", "посоветуй", "как быть", "что делать"],
            "gratitude": ["спасибо", "благодар", "признателен", "признательна", "ценю"]
        }
        
        # Веса для разных типов анализа
        self.weights = {
            "emotional": 0.4,
            "behavioral": 0.3,
            "social": 0.2,
            "cognitive": 0.1
        }
        
        # Минимальное количество сообщений для анализа
        self.MIN_MESSAGES_FOR_ANALYSIS = 5
    
    def analyze_user_profile(self, user_id: int, refresh: bool = False) -> Dict[str, Any]:
        """
        Комплексный анализ профиля пользователя
        
        Args:
            user_id: ID пользователя
            refresh: Если True, обновить сводки перед анализом
            
        Returns:
            Словарь с результатами анализа
        """
        try:
            # Получаем данные пользователя с учетом необходимости обновления
            user_data = self.db_service.get_user_by_id(user_id)
            if not user_data:
                return {"status": "error", "message": "Профиль пользователя не найден"}
            
            # Получаем актуальные сводки
            profile_summary = self.db_service.get_user_profile_summary(user_id, refresh=refresh)
            history_summary = self.db_service.get_user_history_summary(user_id)
            
            # Анализируем историю сообщений
            conversation_analysis = self.analyze_conversation(user_id)
            
            # Анализируем маркеры профиля
            profile_analysis = self.analyze_profile_markers(user_data)
            
            # Анализируем активность пользователя
            activity_analysis = self.analyze_user_activity(user_id)
            
            # Комплексный анализ
            comprehensive_analysis = self._perform_comprehensive_analysis(
                user_data, 
                profile_summary, 
                history_summary, 
                conversation_analysis, 
                profile_analysis,
                activity_analysis
            )
            
            # Формируем общий анализ
            analysis = {
                "user_id": user_id,
                "timestamp": datetime.utcnow().isoformat(),
                "profile_summary": profile_summary,
                "history_summary": history_summary,
                "conversation_analysis": conversation_analysis,
                "profile_markers_analysis": profile_analysis,
                "activity_analysis": activity_analysis,
                "comprehensive_analysis": comprehensive_analysis,
                "recommendations": self._generate_recommendations(
                    comprehensive_analysis,
                    conversation_analysis, 
                    profile_analysis,
                    activity_analysis
                ),
                "risk_factors": self._identify_risk_factors(
                    comprehensive_analysis,
                    conversation_analysis, 
                    profile_analysis,
                    activity_analysis
                )
            }
            
            # Сохраняем результаты анализа
            self._save_analysis_results(user_id, analysis)
            
            return {"status": "success", "analysis": analysis}
            
        except Exception as e:
            logger.error(f"Ошибка при анализе профиля пользователя {user_id}: {e}", exc_info=True)
            return {"status": "error", "message": f"Ошибка при анализе профиля: {str(e)}"}
    
    def analyze_conversation(self, user_id: int, days: int = 30, limit: int = 1000) -> Dict[str, Any]:
        """
        Анализ истории сообщений пользователя
        
        Args:
            user_id: ID пользователя
            days: Количество дней для анализа
            limit: Максимальное количество сообщений для анализа
            
        Returns:
            Словарь с результатами анализа
        """
        try:
            # Получаем историю сообщений
            messages = self.message_service.get_conversation_history(user_id, days=days, limit=limit)
            
            if not messages or len(messages) < self.MIN_MESSAGES_FOR_ANALYSIS:
                return {
                    "status": "no_data", 
                    "message": f"Недостаточно данных для анализа (минимум {self.MIN_MESSAGES_FOR_ANALYSIS} сообщений)"
                }
            
            # Инициализация счетчиков
            emotion_scores = {"positive": 0, "negative": 0, "neutral": 0}
            keyword_matches = {key: 0 for key in self.keywords}
            message_lengths = []
            timestamps = []
            
            # Анализ каждого сообщения
            for msg in messages:
                content = msg.get("content", "").lower()
                timestamps.append(msg.get("timestamp"))
                message_lengths.append(len(content.split()))
                
                # Анализ по ключевым словам с учетом контекста
                for category, keywords in self.keywords.items():
                    # Проверяем наличие ключевых слов с учетом границ слов
                    for keyword in keywords:
                        # Используем регулярное выражение для поиска целых слов
                        if re.search(rf'\b{re.escape(keyword)}\w*', content):
                            keyword_matches[category] += 1
                            break  # Учитываем только одно вхождение на категорию
                
                # Анализ эмоциональной окраски с учетом контекста
                positive_matches = any(re.search(rf'\b{re.escape(word)}\w*', content) for word in self.keywords["positive"])
                negative_keywords = self.keywords["anxiety"] + self.keywords["depression"] + self.keywords["anger"]
                negative_matches = any(re.search(rf'\b{re.escape(word)}\w*', content) for word in negative_keywords)
                
                if positive_matches:
                    emotion_scores["positive"] += 1
                elif negative_matches:
                    emotion_scores["negative"] += 1
                else:
                    emotion_scores["neutral"] += 1
            
            # Анализ временных паттернов
            time_analysis = self._analyze_message_timings(timestamps) if timestamps else {}
            
            # Анализ длины сообщений
            length_analysis = self._analyze_message_lengths(message_lengths) if message_lengths else {}
            
            # Определяем доминирующую эмоцию
            dominant_emotion = max(emotion_scores.items(), key=lambda x: x[1])[0] if emotion_scores else "neutral"
            
            # Рассчитываем общий эмоциональный тон (от -1 до 1)
            total = sum(emotion_scores.values())
            emotional_tone = (
                (emotion_scores["positive"] - emotion_scores["negative"]) / total 
                if total > 0 else 0
            )
            
            # Нормализуем количество совпадений по ключевым словам
            total_matches = sum(keyword_matches.values())
            normalized_keywords = {
                k: round(v / total_matches * 100, 2) 
                for k, v in keyword_matches.items() 
                if v > 0
            } if total_matches > 0 else {}
            
            # Анализ тем разговора
            topic_analysis = self._analyze_topics(keyword_matches)
            
            return {
                "status": "success",
                "message_count": len(messages),
                "time_period": {
                    "start": min(timestamps) if timestamps else None,
                    "end": max(timestamps) if timestamps else None,
                    "days": days
                },
                "emotion_scores": emotion_scores,
                "emotional_tone": round(emotional_tone, 2),
                "dominant_emotion": dominant_emotion,
                "keyword_matches": normalized_keywords,
                "topic_analysis": topic_analysis,
                "time_analysis": time_analysis,
                "length_analysis": length_analysis,
                "analysis_timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Ошибка при анализе переписки пользователя {user_id}: {e}", exc_info=True)
            return {"status": "error", "message": f"Ошибка при анализе переписки: {str(e)}"}
    
    def analyze_profile_markers(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Анализ маркеров профиля пользователя"""
        try:
            markers = user_data.get("markers", {})
            if not markers:
                return {"status": "no_data", "message": "В профиле отсутствуют маркеры для анализа"}
            
            analysis = {}
            
            # Анализ маркеров тревожности
            if "anxiety_level" in markers:
                analysis["anxiety"] = self._analyze_anxiety(markers["anxiety_level"])
            
            # Анализ маркеров настроения
            if "mood" in markers:
                analysis["mood"] = self._analyze_mood(markers["mood"])
            
            # Анализ социальных аспектов
            if "social_activity" in markers:
                analysis["social"] = self._analyze_social(markers["social_activity"])
            
            return {
                "status": "success",
                "markers_analysis": analysis,
                "analysis_timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Ошибка при анализе маркеров профиля: {e}")
            return {"status": "error", "message": str(e)}
    
    def _analyze_anxiety(self, level: str) -> Dict[str, Any]:
        """Анализ уровня тревожности"""
        levels = {
            "low": {"level": 1, "description": "Низкий уровень тревожности"},
            "medium": {"level": 2, "description": "Умеренный уровень тревожности"},
            "high": {"level": 3, "description": "Высокий уровень тревожности"}
        }
        
        return levels.get(level.lower(), {"level": 0, "description": "Неизвестный уровень тревожности"})
    
    def _analyze_mood(self, mood: str) -> Dict[str, Any]:
        """Анализ настроения"""
        moods = {
            "happy": {"level": 3, "description": "Хорошее настроение"},
            "neutral": {"level": 2, "description": "Нейтральное настроение"},
            "sad": {"level": 1, "description": "Подавленное настроение"},
            "anxious": {"level": 1, "description": "Тревожное настроение"}
        }
        
        return moods.get(mood.lower(), {"level": 2, "description": "Неизвестное состояние настроения"})
    
    def _analyze_social(self, activity: str) -> Dict[str, Any]:
        """Анализ социальной активности
        
        Args:
            activity: Уровень социальной активности (high/medium/low)
            
        Returns:
            Словарь с анализом социальной активности
            
        Raises:
            ValueError: Если передан некорректный тип активности
        """
        if not isinstance(activity, str):
            raise ValueError("Параметр 'activity' должен быть строкой")
            
        activities = {
            "high": {"level": 3, "description": "Высокая социальная активность"},
            "medium": {"level": 2, "description": "Умеренная социальная активность"},
            "low": {"level": 1, "description": "Низкая социальная активность"}
        }
        
        return activities.get(activity.lower(), {"level": 2, "description": "Уровень активности не определен"})
    
    def _analyze_emotional_risks(
        self, 
        conv_analysis: Dict[str, Any], 
        profile_analysis: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Анализ эмоциональных факторов риска"""
        risks = []
        
        # Анализ эмоционального тона переписки
        emotional_tone = conv_analysis.get("emotional_tone", 0)
        if emotional_tone < -0.5:
            risks.append({
                "type": "emotional",
                "level": "high",
                "description": "Ярко выраженный негативный эмоциональный фон",
                "evidence": f"Эмоциональный тон переписки: {emotional_tone:.2f} (шкала от -1 до 1)"
            })
        elif emotional_tone < -0.2:
            risks.append({
                "type": "emotional",
                "level": "medium",
                "description": "Негативный эмоциональный фон",
                "evidence": f"Эмоциональный тон переписки: {emotional_tone:.2f}"
            })
        
        # Анализ ключевых слов, связанных с тревожностью и депрессией
        keywords = conv_analysis.get("keyword_matches", {})
        
        if keywords.get("anxiety", 0) > 10:
            risks.append({
                "type": "emotional",
                "level": "high",
                "description": "Высокий уровень тревожности",
                "evidence": f"Обнаружено {keywords['anxiety']}% совпадений с ключевыми словами тревожности"
            })
        elif keywords.get("anxiety", 0) > 5:
            risks.append({
                "type": "emotional",
                "level": "medium",
                "description": "Признаки тревожности",
                "evidence": f"Обнаружено {keywords['anxiety']}% совпадений с ключевыми словами тревожности"
            })
            
        if keywords.get("depression", 0) > 10:
            risks.append({
                "type": "emotional",
                "level": "high",
                "description": "Признаки депрессивного состояния",
                "evidence": f"Обнаружено {keywords['depression']}% совпадений с ключевыми словами депрессии"
            })
            
        # Анализ маркеров профиля
        markers = profile_analysis.get("markers_analysis", {})
        if "emotional" in markers:
            emotional_markers = markers["emotional"]
            risk_factors = emotional_markers.get("risk_factors", [])
            for factor in risk_factors:
                risks.append({
                    "type": "emotional",
                    "level": "medium",
                    "description": factor,
                    "evidence": "Выявлено на основе анализа маркеров профиля"
                })
        
        return risks
        
    def _analyze_behavioral_risks(
        self, 
        conv_analysis: Dict[str, Any], 
        activity_analysis: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Анализ поведенческих факторов риска"""
        risks = []
        
        # Анализ активности
        if activity_analysis.get("status") == "success":
            activity_level = activity_analysis.get("activity_level", "normal")
            if activity_level == "low":
                risks.append({
                    "type": "behavioral",
                    "level": "medium",
                    "description": "Низкая активность пользователя",
                    "evidence": "Пользователь редко взаимодействует с ботом"
                })
            elif activity_level == "very_low":
                risks.append({
                    "type": "behavioral",
                    "level": "high",
                    "description": "Крайне низкая активность пользователя",
                    "evidence": "Пользователь практически не взаимодействует с ботом"
                })
        
        # Анализ паттернов прокрастинации
        keywords = conv_analysis.get("keyword_matches", {})
        if keywords.get("procrastination", 0) > 15:
            risks.append({
                "type": "behavioral",
                "level": "medium",
                "description": "Признаки прокрастинации",
                "evidence": f"Высокая частота упоминаний откладывания дел: {keywords['procrastination']}%"
            })
            
        return risks
        
    def _analyze_social_risks(
        self, 
        conv_analysis: Dict[str, Any], 
        profile_analysis: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Анализ социальных факторов риска"""
        risks = []
        
        # Анализ социальных тем в переписке
        keywords = conv_analysis.get("keyword_matches", {})
        social_topics = ["relationships", "family", "work"]
        social_mentions = sum(keywords.get(topic, 0) for topic in social_topics)
        
        if social_mentions < 5:
            risks.append({
                "type": "social",
                "level": "low",
                "description": "Низкая вовлеченность в социальные темы",
                "evidence": f"Упоминание социальных тем: {social_mentions:.1f}%"
            })
            
        # Анализ маркеров социальной активности
        markers = profile_analysis.get("markers_analysis", {})
        if "social" in markers and markers["social"].get("level") == "low":
            risks.append({
                "type": "social",
                "level": "medium",
                "description": "Низкая социальная активность",
                "evidence": "На основе анализа маркеров профиля"
            })
            
        return risks
        
    def _analyze_cognitive_risks(self, conv_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Анализ когнитивных факторов риска"""
        risks = []
        
        # Анализ неопределенности в высказываниях
        keywords = conv_analysis.get("keyword_matches", {})
        if keywords.get("uncertainty", 0) > 20:
            risks.append({
                "type": "cognitive",
                "level": "medium",
                "description": "Повышенная неопределенность в высказываниях",
                "evidence": f"Высокая частота выражений неопределенности: {keywords['uncertainty']}%"
            })
            
        # Анализ когнитивных искажений (упрощенный)
        if keywords.get("certainty", 0) > 25 and keywords.get("reflection", 0) < 5:
            risks.append({
                "type": "cognitive",
                "level": "low",
                "description": "Возможны когнитивные искажения",
                "evidence": "Высокая уверенность в сочетании с низкой рефлексией"
            })
            
        return risks

    def _generate_recommendations(self, comprehensive_analysis: Dict, conv_analysis: Dict, profile_analysis: Dict, activity_analysis: Dict) -> List[str]:
        """Генерация рекомендаций на основе анализа"""
        recommendations = []
        
        # Проверяем наличие данных анализа
        if conv_analysis.get("status") != "success" or profile_analysis.get("status") != "success":
            return ["Недостаточно данных для формирования рекомендаций"]
        
        # Анализ эмоционального состояния
        emotion = conv_analysis.get("dominant_emotion", "neutral")
        if emotion == "negative":
            recommendations.append("Рекомендуется обратить внимание на техники релаксации и управления стрессом.")
        
        # Анализ ключевых слов
        keywords = conv_analysis.get("keyword_matches", {})
        if keywords.get("anxiety", 0) > 5:
            recommendations.append("Обнаружены признаки тревожности. Возможно, стоит обсудить это с психологом.")
        
        if keywords.get("depression", 0) > 5:
            recommendations.append("Замечены признаки подавленного состояния. Рекомендуется консультация специалиста.")
        
        # Анализ маркеров профиля
        markers = profile_analysis.get("markers_analysis", {})
        
        if "anxiety" in markers and markers["anxiety"]["level"] >= 2:
            recommendations.append("У вас повышенный уровень тревожности. Попробуйте дыхательные упражнения или медитацию.")
        
        if "mood" in markers and markers["mood"]["level"] == 1:
            recommendations.append("Ваше настроение кажется подавленным. Возможно, стоит поговорить с кем-то о своих переживаниях.")
        
        if "social" in markers and markers["social"]["level"] == 1:
            recommendations.append("Низкая социальная активность может влиять на ваше эмоциональное состояние. Попробуйте больше общаться с близкими.")
        
        if not recommendations:
            recommendations.append("Ваше состояние в норме. Продолжайте заботиться о своем психологическом благополучии.")
        
        return recommendations
    
    def _identify_risk_factors(self, conv_analysis: Dict, profile_analysis: Dict) -> List[Dict[str, Any]]:
        """Идентификация факторов риска"""
        risk_factors = []
        
        # Проверяем наличие данных анализа
        if conv_analysis.get("status") != "success" or profile_analysis.get("status") != "success":
            return [{"level": "low", "description": "Недостаточно данных для оценки рисков"}]
        
        # Анализ эмоционального состояния
        emotion = conv_analysis.get("dominant_emotion")
        if emotion == "negative":
            risk_factors.append({
                "level": "medium",
                "description": "Преобладание негативных эмоций в общении",
                "suggestion": "Рекомендуется консультация психолога"
            })
        
        # Анализ ключевых слов
        keywords = conv_analysis.get("keyword_matches", {})
        
        if keywords.get("suicidal", 0) > 0:
            risk_factors.append({
                "level": "critical",
                "description": "Обнаружены признаки суицидальных мыслей",
                "suggestion": "Необходима срочная консультация специалиста"
            })
        
        if keywords.get("violence", 0) > 0:
            risk_factors.append({
                "level": "high",
                "description": "Обнаружены упоминания о насилии",
                "suggestion": "Рекомендуется консультация специалиста"
            })
        
        # Анализ маркеров профиля
        markers = profile_analysis.get("markers_analysis", {})
        
        if "anxiety" in markers and markers["anxiety"]["level"] >= 3:
            risk_factors.append({
                "level": "high",
                "description": "Высокий уровень тревожности",
                "suggestion": "Рекомендуется консультация психотерапевта"
            })
        
        if not risk_factors:
            risk_factors.append({
                "level": "none",
                "description": "Значительные факторы риска не выявлены",
                "suggestion": "Продолжайте следить за своим состоянием"
            })
        
        return risk_factors

# Создаем глобальный экземпляр сервиса
profile_analysis_service = ProfileAnalysisService()

def get_profile_analysis_service() -> ProfileAnalysisService:
    """Получить экземпляр сервиса анализа профиля"""
    return profile_analysis_service
