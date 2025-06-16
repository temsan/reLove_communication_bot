from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, UserUttered, ActionExecuted
import logging

logger = logging.getLogger(__name__)

class ActionDefaultFallback(Action):
    """Обработка непонятных сообщений"""
    def name(self) -> Text:
        return "action_default_fallback"

    async def run(self, dispatcher: CollectingDispatcher,
                 tracker: Tracker,
                 domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        # Получаем последнее сообщение пользователя
        last_message = tracker.latest_message.get('text', '')
        logger.warning(f"Неизвестное сообщение от пользователя: {last_message}")
        
        dispatcher.utter_message(text="Извините, я не совсем понял. Можете переформулировать?")
        return []

class ActionContactSupport(Action):
    """Обработка запроса на связь с поддержкой"""
    def name(self) -> Text:
        return "action_contact_support"

    async def run(self, dispatcher: CollectingDispatcher,
                 tracker: Tracker,
                 domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        # Здесь может быть логика создания тикета в вашей системе
        dispatcher.utter_message(
            text="Ваш запрос передан в службу поддержки. Мы свяжемся с вами в ближайшее время."
        )
        return []

class ActionFaqResponse(Action):
    """Ответы на часто задаваемые вопросы"""
    def name(self) -> Text:
        return "action_faq_response"

    async def run(self, dispatcher: CollectingDispatcher,
                 tracker: Tracker,
                 domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        # Получаем последнее намерение пользователя
        intent = tracker.latest_message['intent'].get('name')
        
        # Простые ответы на частые вопросы
        faq_responses = {
            "faq": "Я чат-бот, созданный для помощи пользователям. Я могу отвечать на вопросы, помогать с настройками и решать различные задачи.",
            "how_it_works": "Я работаю на основе искусственного интеллекта, который анализирует ваши сообщения и подбирает подходящий ответ.",
            "capabilities": "Я умею отвечать на вопросы, помогать с навигацией, обрабатывать запросы и многое другое. Спрашивайте!"
        }
        
        # Проверяем, есть ли ответ на этот вопрос
        response = faq_responses.get(intent, "Извините, я не совсем понял ваш вопрос. Можете уточнить?")
        dispatcher.utter_message(text=response)
        
        return []

class ActionRestart(Action):
    """Сброс диалога"""
    def name(self) -> Text:
        return "action_restart"

    async def run(self, dispatcher: CollectingDispatcher,
                 tracker: Tracker,
                 domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        # Очищаем слоты
        return [SlotSet(slot, None) for slot in tracker.slots]
