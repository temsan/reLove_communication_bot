from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, UserUttered, ActionExecuted
import logging

# Импортируем наши сервисы
from ..services.profile_analysis_service import get_profile_analysis_service
from ..services.message_history_service import get_message_history_service
from ..db_service import get_db_service

logger = logging.getLogger(__name__)

class ActionAnalyzeUserProfile(Action):
    """Действие для анализа профиля пользователя с учетом истории общения"""
    
    def name(self) -> Text:
        return "action_analyze_user_profile"
    
    async def run(self, dispatcher: CollectingDispatcher,
                 tracker: Tracker,
                 domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        # Получаем ID пользователя
        user_id = tracker.sender_id
        try:
            user_id = int(user_id)
        except (ValueError, TypeError):
            logger.error(f"Некорректный ID пользователя: {user_id}")
            dispatcher.utter_message("Извините, не удалось проанализировать ваш профиль.")
            return []
        
        # Получаем сервисы
        profile_service = get_profile_analysis_service()
        message_service = get_message_history_service()
        db_service = get_db_service()
        
        # Получаем данные пользователя
        user_data = db_service.get_user_by_id(user_id)
        if not user_data:
            dispatcher.utter_message("Извините, ваш профиль не найден.")
            return []
        
        # Отправляем сообщение о начале анализа
        dispatcher.utter_message("🔍 Анализирую ваш профиль и историю общения...")
        
        # Анализируем профиль
        profile_analysis = profile_service.analyze_user_profile(user_id)
        
        # Анализируем историю сообщений
        conversation_analysis = message_service.analyze_conversation_patterns(user_id)
        
        # Формируем и отправляем отчет
        self._send_analysis_report(dispatcher, user_data, profile_analysis, conversation_analysis)
        
        return []
    
    def _send_analysis_report(self, 
                            dispatcher: CollectingDispatcher,
                            user_data: Dict[str, Any],
                            profile_analysis: Dict[str, Any],
                            conversation_analysis: Dict[str, Any]) -> None:
        """Формирование и отправка отчета о анализе"""
        try:
            # Основная информация о пользователе
            user_name = user_data.get("first_name", "Пользователь")
            
            # Начинаем формировать сообщение
            messages = [f"📊 Отчет по анализу профиля {user_name}:"]
            
            # Добавляем анализ профиля, если он есть
            if profile_analysis.get("status") == "success":
                analysis = profile_analysis.get("analysis", {})
                
                # Добавляем рекомендации
                if "recommendations" in analysis and analysis["recommendations"]:
                    messages.append("\n💡 Рекомендации:")
                    for rec in analysis["recommendations"][:3]:  # Ограничиваем количество рекомендаций
                        messages.append(f"• {rec}")
                
                # Добавляем факторы риска
                if "risk_factors" in analysis and analysis["risk_factors"]:
                    risk_factors = [rf for rf in analysis["risk_factors"] 
                                  if rf.get("level") in ["high", "critical"]]
                    
                    if risk_factors:
                        messages.append("\n⚠️ Обратите внимание:")
                        for risk in risk_factors:
                            messages.append(f"• {risk['description']}")
                            if risk.get("suggestion"):
                                messages.append(f"  → {risk['suggestion']}")
            
            # Добавляем анализ беседы, если он есть
            if conversation_analysis.get("status") == "success":
                messages.append("\n💬 Анализ общения:")
                
                # Активность
                if "avg_messages_per_day" in conversation_analysis:
                    messages.append(
                        f"• В среднем вы отправляете {conversation_analysis['avg_messages_per_day']} "
                        f"сообщений в день (всего {conversation_analysis.get('message_count', 0)} сообщений)"
                    )
                
                # Настроение
                if "mood_analysis" in conversation_analysis:
                    mood_map = {
                        "positive": "позитивное",
                        "negative": "негативное",
                        "neutral": "нейтральное"
                    }
                    dominant_mood = conversation_analysis["mood_analysis"].get("dominant_mood", "neutral")
                    messages.append(f"• Преобладающее настроение: {mood_map.get(dominant_mood, 'нейтральное')}")
                
                # Пиковые часы активности
                if "peak_hours" in conversation_analysis and conversation_analysis["peak_hours"]:
                    messages.append(
                        f"• Пиковые часы активности: {', '.join(conversation_analysis['peak_hours'])}"
                    )
            
            # Добавляем общие рекомендации
            messages.extend([
                "\n📌 Общие рекомендации:",
                "• Регулярно отслеживайте свое эмоциональное состояние",
                "• Не стесняйтесь обращаться за помощью, если это необходимо",
                "• Старайтесь поддерживать баланс между работой и отдыхом"
            ])
            
            # Отправляем сообщения частями, чтобы избежать переполнения
            current_message = ""
            for part in messages:
                if len(current_message) + len(part) > 3000:  # Ограничение Telegram на длину сообщения
                    dispatcher.utter_message(current_message)
                    current_message = part + "\n"
                else:
                    current_message += "\n" + part if current_message else part
            
            if current_message:
                dispatcher.utter_message(current_message)
            
        except Exception as e:
            logger.error(f"Ошибка при формировании отчета: {e}")
            dispatcher.utter_message("Произошла ошибка при анализе профиля. Пожалуйста, попробуйте позже.")

class ActionUpdateEmotionalState(Action):
    """Действие для обновления эмоционального состояния пользователя"""
    
    def name(self) -> Text:
        return "action_update_emotional_state"
    
    async def run(self, dispatcher: CollectingDispatcher,
                 tracker: Tracker,
                 domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        # Получаем ID пользователя
        user_id = tracker.sender_id
        try:
            user_id = int(user_id)
        except (ValueError, TypeError):
            logger.error(f"Некорректный ID пользователя: {user_id}")
            dispatcher.utter_message("Извините, не удалось обновить ваше состояние.")
            return []
        
        # Получаем слот с эмоциональным состоянием
        emotional_state = tracker.get_slot("emotional_state")
        
        if not emotional_state:
            dispatcher.utter_message("Не удалось определить ваше эмоциональное состояние.")
            return []
        
        # Обновляем маркер в профиле
        db_service = get_db_service()
        success = db_service.update_user_marker(user_id, "emotional_state", emotional_state)
        
        if success:
            # Логируем обновление состояния
            message_history_service = get_message_history_service()
            message_history_service.log_activity(
                user_id=user_id,
                activity_type="emotional_state_updated",
                details={"state": emotional_state}
            )
            
            # Отправляем ответ в зависимости от состояния
            responses = {
                "happy": "Рад, что у вас хорошее настроение! 😊",
                "sad": "Мне жаль это слышать. Если хотите поговорить, я здесь, чтобы выслушать. 😔",
                "anxious": "Понимаю, что вы чувствуете тревогу. Попробуйте сделать глубокий вдох. 🧘‍♂️",
                "calm": "Приятно видеть, что вы спокойны. 🌿",
                "excited": "Здорово, что вы полны энтузиазма! 🎉",
                "tired": "Похоже, вам нужен отдых. Не забывайте заботиться о себе. 💤"
            }
            
            response = responses.get(emotional_state, 
                                  "Спасибо, что поделились своим состоянием. Это поможет мне лучше вас понять.")
            dispatcher.utter_message(response)
            
            # Дополнительные рекомендации при необходимости
            if emotional_state in ["sad", "anxious"]:
                dispatcher.utter_message("Если ваше состояние сохраняется, возможно, стоит обсудить это с психологом.")
            
        else:
            dispatcher.utter_message("Не удалось обновить ваше состояние. Пожалуйста, попробуйте позже.")
        
        return [SlotSet("emotional_state", None)]

class ActionGetUserInsights(Action):
    """Действие для получения инсайтов о пользователе"""
    
    def name(self) -> Text:
        return "action_get_user_insights"
    
    async def run(self, dispatcher: CollectingDispatcher,
                 tracker: Tracker,
                 domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        # Получаем ID пользователя
        user_id = tracker.sender_id
        try:
            user_id = int(user_id)
        except (ValueError, TypeError):
            logger.error(f"Некорректный ID пользователя: {user_id}")
            dispatcher.utter_message("Извините, не удалось получить информацию.")
            return []
        
        # Получаем сервисы
        message_service = get_message_history_service()
        db_service = get_db_service()
        
        # Получаем данные пользователя
        user_data = db_service.get_user_by_id(user_id)
        if not user_data:
            dispatcher.utter_message("Извините, ваш профиль не найден.")
            return []
        
        # Получаем метрики вовлеченности
        engagement = message_service.get_user_engagement_metrics(user_id)
        
        # Формируем сообщение с инсайтами
        messages = ["💡 Вот что я заметил(а) в вашей активности:"]
        
        if engagement.get("status") == "success":
            messages.append(
                f"• Вы активны в среднем {engagement.get('avg_activities_per_day', 0)} раз в день"
            )
            
            if engagement.get("peak_day"):
                messages.append(
                    f"• Ваш самый активный день: {engagement['peak_day']['date']} "
                    f"({engagement['peak_day']['count']} действий)"
                )
            
            # Анализ типов активности
            activity_types = engagement.get("activity_by_type", {})
            if activity_types:
                top_activities = sorted(activity_types.items(), key=lambda x: x[1], reverse=True)[:3]
                messages.append("\nЧаще всего вы:")
                for activity, count in top_activities:
                    activity_name = self._get_activity_name(activity)
                    messages.append(f"• {activity_name}: {count} раз")
        
        # Добавляем рекомендации на основе активности
        messages.extend([
            "\n📌 Советы по улучшению:",
            "• Старайтесь быть активными в разное время суток",
            "• Не забывайте делать перерывы во время работы",
            "• Попробуйте использовать разные функции бота"
        ])
        
        # Отправляем сообщение
        dispatcher.utter_message("\n".join(messages))
        
        return []
    
    def _get_activity_name(self, activity_type: str) -> str:
        """Получить читаемое название типа активности"""
        names = {
            "message": "Отправляли сообщения",
            "command": "Использовали команды",
            "button_press": "Нажимали кнопки",
            "profile_view": "Просматривали профиль",
            "emotional_state_updated": "Отмечали эмоциональное состояние"
        }
        return names.get(activity_type, activity_type)
