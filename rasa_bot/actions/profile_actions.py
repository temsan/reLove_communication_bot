from typing import Any, Text, Dict, List, Optional
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, UserUttered, ActionExecuted, SessionStarted
import logging
import json

# Импортируем наш сервис для работы с БД
from ..db_service import get_db_service
from ..services.profile_service import ProfileService
from ..enums.gender_enum import GenderEnum

logger = logging.getLogger(__name__)
db_service = get_db_service()

class ActionGetUserProfile(Action):
    """Действие для получения профиля пользователя"""
    
    def name(self) -> Text:
        return "action_get_user_profile"
    
    async def run(self, dispatcher: CollectingDispatcher,
                 tracker: Tracker,
                 domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        # Получаем ID пользователя из слотов или из sender_id
        user_id = tracker.sender_id
        try:
            user_id = int(user_id)
        except (ValueError, TypeError):
            logger.error(f"Некорректный ID пользователя: {user_id}")
            dispatcher.utter_message("Извините, не удалось определить ваш профиль.")
            return []
        
        # Получаем данные пользователя из БД
        user_data = db_service.get_user_by_id(user_id)
        if not user_data:
            dispatcher.utter_message("Извините, ваш профиль не найден.")
            return []
        
        # Формируем сообщение с информацией о пользователе
        message = f"👤 Профиль пользователя {user_data.get('first_name', '')}:"
        
        if user_data.get('gender'):
            gender = "Мужской" if user_data['gender'] == 'male' else "Женский"
            message += f"\n• Пол: {gender}"
            
        if user_data.get('profile_summary'):
            message += f"\n\n📝 О профиле:\n{user_data['profile_summary']}"
        
        if user_data.get('history_summary'):
            message += f"\n\n💬 История общения:\n{user_data['history_summary']}"
        
        # Добавляем маркеры, если они есть
        markers = user_data.get('markers', {})
        if markers:
            message += "\n\n🏷️ Маркеры:"
            for key, value in markers.items():
                message += f"\n• {key}: {value}"
        
        dispatcher.utter_message(message)
        
        # Логируем просмотр профиля
        db_service.log_activity(
            user_id=user_id,
            activity_type="profile_viewed",
            details={"from": "chatbot"}
        )
        
        return []

class ActionAnalyzeProfile(Action):
    """Анализ психологического профиля пользователя"""
    
    def name(self) -> Text:
        return "action_analyze_profile"
    
    async def run(self, dispatcher: CollectingDispatcher,
                 tracker: Tracker,
                 domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        user_id = tracker.sender_id
        try:
            user_id = int(user_id)
        except (ValueError, TypeError):
            logger.error(f"Некорректный ID пользователя: {user_id}")
            dispatcher.utter_message("Извините, не удалось проанализировать ваш профиль.")
            return []
        
        # Получаем данные пользователя
        user_data = db_service.get_user_by_id(user_id)
        if not user_data:
            dispatcher.utter_message("Извините, ваш профиль не найден.")
            return []
        
        # Анализируем профиль
        profile_service = ProfileService(db_service.session)
        analysis_result = await profile_service.analyze_profile(user_id)
        
        if not analysis_result:
            dispatcher.utter_message("Извините, не удалось проанализировать ваш профиль.")
            return []
        
        # Формируем сообщение с анализом
        message = f"🔍 Анализ вашего профиля, {user_data.get('first_name', '')}:\n\n"
        
        if 'psychological_summary' in analysis_result:
            message += analysis_result['psychological_summary'] + "\n\n"
            
        if 'streams' in analysis_result:
            message += f"📊 Ваши потоки: {', '.join(analysis_result['streams'])}\n\n"
            
        if 'gender' in analysis_result:
            gender_text = "женский" if analysis_result['gender'] == GenderEnum.female else "мужской"
            message += f"👤 Пол: {gender_text}\n"
        
        dispatcher.utter_message(message)
        
        # Логируем анализ профиля
        db_service.log_activity(
            user_id=user_id,
            activity_type="profile_analyzed",
            details={"analysis_type": "full"}
        )
        
        return []

class ActionUpdateProfileMarker(Action):
    """Обновление маркера в профиле пользователя"""
    
    def name(self) -> Text:
        return "action_update_profile_marker"
    
    async def run(self, dispatcher: CollectingDispatcher,
                 tracker: Tracker,
                 domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        user_id = tracker.sender_id
        try:
            user_id = int(user_id)
        except (ValueError, TypeError):
            logger.error(f"Некорректный ID пользователя: {user_id}")
            dispatcher.utter_message("Извините, не удалось обновить ваш профиль.")
            return []
        
        # Получаем слоты с данными для обновления
        marker_key = tracker.get_slot("marker_key")
        marker_value = tracker.get_slot("marker_value")
        
        if not marker_key:
            dispatcher.utter_message("Не указан ключ маркера для обновления.")
            return []
        
        # Обновляем маркер в БД
        success = db_service.update_user_marker(user_id, marker_key, marker_value)
        
        if success:
            dispatcher.utter_message(f"✅ Маркер '{marker_key}' успешно обновлен.")
            
            # Логируем обновление маркера
            db_service.log_activity(
                user_id=user_id,
                activity_type="marker_updated",
                details={"marker": marker_key, "value": marker_value}
            )
        else:
            dispatcher.utter_message("❌ Не удалось обновить маркер. Пожалуйста, попробуйте позже.")
        
        return [SlotSet("marker_key", None), SlotSet("marker_value", None)]
