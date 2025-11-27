"""
Сервис для работы с Наташей - автоматический выбор промптов и управление диалогами.
"""
from typing import Optional, Dict, List
import logging

from relove_bot.services.prompt_selector import (
    PromptSelector,
    DialogTopic,
    get_prompt_selector,
)

logger = logging.getLogger(__name__)


class NatashaService:
    """Сервис для работы с Наташей."""

    def __init__(self, llm_client):
        """
        Инициализируй сервис.

        Args:
            llm_client: Клиент LLM (OpenAI, Kimi и т.д.)
        """
        self.llm = llm_client
        self.selector = get_prompt_selector()
        self.conversation_history = {}
        self.user_settings = {}  # Настройки пользователя (админ может менять)

    async def get_response(
        self,
        user_id: str,
        message: str,
        user_profile: Optional[Dict] = None,
        force_topic: Optional[DialogTopic] = None,
    ) -> Dict:
        """
        Получи ответ Наташи с автоматическим выбором промпта.

        Args:
            user_id: ID пользователя
            message: Сообщение пользователя
            user_profile: Профиль пользователя
            force_topic: Принудительная тема (для админов)

        Returns:
            Dict с ответом и метаданными
        """
        # Получи историю диалога
        history = self.conversation_history.get(user_id, [])

        # Определи тему
        if force_topic:
            topic = force_topic
            logger.info(f"User {user_id}: Topic forced to {topic}")
        else:
            topic = self.selector.detect_topic(
                message,
                conversation_history=history,
                user_profile=user_profile,
            )
            logger.info(f"User {user_id}: Topic detected = {topic}")

        # Выбери промпт
        system_prompt = self.selector.select_combined_prompt(
            message,
            conversation_history=history,
            user_profile=user_profile,
        )

        # Подготовь сообщения
        messages = [
            {"role": "system", "content": system_prompt},
            *history,
            {"role": "user", "content": message},
        ]

        try:
            # Отправь запрос к LLM
            response = await self.llm.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
                temperature=0.8,
                max_tokens=500,
            )

            answer = response.choices[0].message.content

            # Сохрани в историю
            history.append({"role": "user", "content": message})
            history.append({"role": "assistant", "content": answer})
            self.conversation_history[user_id] = history[-10:]  # Последние 10 сообщений

            return {
                "success": True,
                "response": answer,
                "topic": self.selector.get_topic_name(topic),
                "topic_enum": topic,
            }

        except Exception as e:
            logger.error(f"Error getting response for user {user_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "topic": self.selector.get_topic_name(topic),
            }

    def set_user_topic_override(self, user_id: str, topic: Optional[DialogTopic]):
        """
        Установи принудительную тему для пользователя (админ функция).

        Args:
            user_id: ID пользователя
            topic: Тема или None для отключения
        """
        if topic is None:
            self.user_settings.pop(user_id, None)
            logger.info(f"Topic override removed for user {user_id}")
        else:
            self.user_settings[user_id] = {"forced_topic": topic}
            logger.info(f"Topic override set for user {user_id}: {topic}")

    def get_user_topic_override(self, user_id: str) -> Optional[DialogTopic]:
        """
        Получи принудительную тему для пользователя.

        Args:
            user_id: ID пользователя

        Returns:
            DialogTopic или None
        """
        settings = self.user_settings.get(user_id, {})
        return settings.get("forced_topic")

    def clear_conversation_history(self, user_id: str):
        """
        Очисти историю диалога пользователя.

        Args:
            user_id: ID пользователя
        """
        self.conversation_history.pop(user_id, None)
        logger.info(f"Conversation history cleared for user {user_id}")

    def get_conversation_history(self, user_id: str) -> List[Dict]:
        """
        Получи историю диалога пользователя.

        Args:
            user_id: ID пользователя

        Returns:
            Список сообщений
        """
        return self.conversation_history.get(user_id, [])

    def get_available_topics(self) -> Dict[str, str]:
        """
        Получи доступные темы.

        Returns:
            Dict с темами и их названиями
        """
        return {
            topic.value: self.selector.get_topic_name(topic)
            for topic in DialogTopic
        }

    def get_statistics(self) -> Dict:
        """
        Получи статистику по диалогам.

        Returns:
            Dict со статистикой
        """
        total_users = len(self.conversation_history)
        total_messages = sum(
            len(history) for history in self.conversation_history.values()
        )

        return {
            "total_users": total_users,
            "total_messages": total_messages,
            "avg_messages_per_user": (
                total_messages / total_users if total_users > 0 else 0
            ),
        }


# Глобальный экземпляр сервиса
_natasha_service = None


def get_natasha_service(llm_client=None) -> NatashaService:
    """Получи глобальный экземпляр сервиса."""
    global _natasha_service
    if _natasha_service is None:
        if llm_client is None:
            raise ValueError("LLM client is required for first initialization")
        _natasha_service = NatashaService(llm_client)
    return _natasha_service
