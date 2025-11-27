"""
Автоматический выбор промпта на основе контекста диалога.
"""
from typing import Optional, Dict, List
from enum import Enum

from relove_bot.services.prompts import (
    NATASHA_PROVOCATIVE_PROMPT,
    ENERGY_RITUAL_PROMPT,
    RELATIONSHIPS_BALANCE_PROMPT,
    PAST_LIVES_PROMPT,
    BUSINESS_CREATIVITY_PROMPT,
    FLEXIBLE_DIAGNOSTIC_PROMPT,
)


class DialogTopic(str, Enum):
    """Темы диалогов."""
    ENERGY = "energy"
    RELATIONSHIPS = "relationships"
    PAST_LIVES = "past_lives"
    BUSINESS = "business"
    GENERAL = "general"
    DIAGNOSTIC = "diagnostic"


class PromptSelector:
    """Автоматический выбор промпта на основе контекста."""

    # Ключевые слова для определения темы
    ENERGY_KEYWORDS = {
        "энергия", "ритуал", "медитация", "ощущение", "вибрация",
        "активация", "чакра", "поток", "центр", "тело",
        "почувствовала", "ощущаю", "чувствую", "вибрирует"
    }

    RELATIONSHIPS_KEYWORDS = {
        "мужчина", "женщина", "отношения", "партнер", "любовь",
        "баланс", "мужское", "женское", "он", "она", "муж", "жена",
        "боюсь", "принять", "воевать", "спасать", "помощь"
    }

    PAST_LIVES_KEYWORDS = {
        "прошлая жизнь", "планета", "храм", "архетип", "суть",
        "ворота", "вспомнила", "помню", "жизнь", "инкарнация",
        "жрица", "воин", "целитель", "король", "исида", "хатхор",
        "осирис", "ра", "египет", "древний"
    }

    BUSINESS_KEYWORDS = {
        "бизнес", "проект", "творчество", "реализация", "дар",
        "миссия", "работа", "карьера", "успех", "деньги",
        "блок", "страх", "готовность", "действие", "поток"
    }

    def __init__(self):
        """Инициализируй селектор."""
        self.topic_prompts = {
            DialogTopic.ENERGY: ENERGY_RITUAL_PROMPT,
            DialogTopic.RELATIONSHIPS: RELATIONSHIPS_BALANCE_PROMPT,
            DialogTopic.PAST_LIVES: PAST_LIVES_PROMPT,
            DialogTopic.BUSINESS: BUSINESS_CREATIVITY_PROMPT,
            DialogTopic.GENERAL: NATASHA_PROVOCATIVE_PROMPT,
            DialogTopic.DIAGNOSTIC: FLEXIBLE_DIAGNOSTIC_PROMPT,
        }

    def detect_topic(
        self,
        message: str,
        conversation_history: Optional[List[Dict]] = None,
        user_profile: Optional[Dict] = None
    ) -> DialogTopic:
        """
        Определи тему диалога на основе сообщения и контекста.

        Args:
            message: Сообщение пользователя
            conversation_history: История диалога
            user_profile: Профиль пользователя

        Returns:
            DialogTopic: Определенная тема
        """
        message_lower = message.lower()

        # Проверь ключевые слова в порядке приоритета
        if self._has_keywords(message_lower, self.PAST_LIVES_KEYWORDS):
            return DialogTopic.PAST_LIVES

        if self._has_keywords(message_lower, self.ENERGY_KEYWORDS):
            return DialogTopic.ENERGY

        if self._has_keywords(message_lower, self.RELATIONSHIPS_KEYWORDS):
            return DialogTopic.RELATIONSHIPS

        if self._has_keywords(message_lower, self.BUSINESS_KEYWORDS):
            return DialogTopic.BUSINESS

        # Если первый контакт или неясная тема
        if not conversation_history or len(conversation_history) == 0:
            return DialogTopic.DIAGNOSTIC

        # Проверь историю для контекста
        if conversation_history:
            history_text = " ".join([
                msg.get("content", "")
                for msg in conversation_history[-5:]  # Последние 5 сообщений
            ]).lower()

            if self._has_keywords(history_text, self.PAST_LIVES_KEYWORDS):
                return DialogTopic.PAST_LIVES

            if self._has_keywords(history_text, self.ENERGY_KEYWORDS):
                return DialogTopic.ENERGY

            if self._has_keywords(history_text, self.RELATIONSHIPS_KEYWORDS):
                return DialogTopic.RELATIONSHIPS

            if self._has_keywords(history_text, self.BUSINESS_KEYWORDS):
                return DialogTopic.BUSINESS

        return DialogTopic.GENERAL

    def select_prompt(
        self,
        message: str,
        conversation_history: Optional[List[Dict]] = None,
        user_profile: Optional[Dict] = None
    ) -> str:
        """
        Выбери промпт на основе контекста.

        Args:
            message: Сообщение пользователя
            conversation_history: История диалога
            user_profile: Профиль пользователя

        Returns:
            str: Выбранный промпт
        """
        topic = self.detect_topic(message, conversation_history, user_profile)
        return self.get_prompt_for_topic(topic)

    def select_combined_prompt(
        self,
        message: str,
        conversation_history: Optional[List[Dict]] = None,
        user_profile: Optional[Dict] = None,
        include_base: bool = True
    ) -> str:
        """
        Выбери комбинированный промпт (основной + специализированный).

        Args:
            message: Сообщение пользователя
            conversation_history: История диалога
            user_profile: Профиль пользователя
            include_base: Включить ли основной промпт

        Returns:
            str: Комбинированный промпт
        """
        topic = self.detect_topic(message, conversation_history, user_profile)
        specialized_prompt = self.get_prompt_for_topic(topic)

        if include_base and topic != DialogTopic.GENERAL:
            return f"{NATASHA_PROVOCATIVE_PROMPT}\n\n{specialized_prompt}"

        return specialized_prompt

    def get_prompt_for_topic(self, topic: DialogTopic) -> str:
        """
        Получи промпт для темы.

        Args:
            topic: Тема диалога

        Returns:
            str: Промпт для темы
        """
        return self.topic_prompts.get(topic, NATASHA_PROVOCATIVE_PROMPT)

    def get_topic_name(self, topic: DialogTopic) -> str:
        """
        Получи название темы на русском.

        Args:
            topic: Тема диалога

        Returns:
            str: Название темы
        """
        names = {
            DialogTopic.ENERGY: "Энергетическая работа",
            DialogTopic.RELATIONSHIPS: "Отношения",
            DialogTopic.PAST_LIVES: "Прошлые жизни",
            DialogTopic.BUSINESS: "Бизнес и творчество",
            DialogTopic.GENERAL: "Общий диалог",
            DialogTopic.DIAGNOSTIC: "Диагностика",
        }
        return names.get(topic, "Неизвестная тема")

    @staticmethod
    def _has_keywords(text: str, keywords: set) -> bool:
        """
        Проверь, содержит ли текст ключевые слова.

        Args:
            text: Текст для проверки
            keywords: Набор ключевых слов

        Returns:
            bool: True если найдены ключевые слова
        """
        return any(keyword in text for keyword in keywords)


# Глобальный экземпляр селектора
_prompt_selector = None


def get_prompt_selector() -> PromptSelector:
    """Получи глобальный экземпляр селектора."""
    global _prompt_selector
    if _prompt_selector is None:
        _prompt_selector = PromptSelector()
    return _prompt_selector


def detect_topic(
    message: str,
    conversation_history: Optional[List[Dict]] = None,
    user_profile: Optional[Dict] = None
) -> DialogTopic:
    """
    Определи тему диалога.

    Args:
        message: Сообщение пользователя
        conversation_history: История диалога
        user_profile: Профиль пользователя

    Returns:
        DialogTopic: Определенная тема
    """
    selector = get_prompt_selector()
    return selector.detect_topic(message, conversation_history, user_profile)


def select_prompt(
    message: str,
    conversation_history: Optional[List[Dict]] = None,
    user_profile: Optional[Dict] = None
) -> str:
    """
    Выбери промпт на основе контекста.

    Args:
        message: Сообщение пользователя
        conversation_history: История диалога
        user_profile: Профиль пользователя

    Returns:
        str: Выбранный промпт
    """
    selector = get_prompt_selector()
    return selector.select_prompt(message, conversation_history, user_profile)


def select_combined_prompt(
    message: str,
    conversation_history: Optional[List[Dict]] = None,
    user_profile: Optional[Dict] = None,
    include_base: bool = True
) -> str:
    """
    Выбери комбинированный промпт.

    Args:
        message: Сообщение пользователя
        conversation_history: История диалога
        user_profile: Профиль пользователя
        include_base: Включить ли основной промпт

    Returns:
        str: Комбинированный промпт
    """
    selector = get_prompt_selector()
    return selector.select_combined_prompt(message, conversation_history, user_profile, include_base)
