"""
Анализ профиля пользователя и автоматическое написание сообщений.
Анализирует: фото, посты, личный канал, историю, состояние.
"""
from typing import Optional, Dict, List
from datetime import datetime
import logging

from relove_bot.services.natasha_service import get_natasha_service
from relove_bot.services.prompt_selector import DialogTopic

logger = logging.getLogger(__name__)


class ProfileAnalyzer:
    """Анализ профиля пользователя."""

    def __init__(self):
        """Инициализируй анализатор."""
        self.user_profiles = {}  # {user_id: profile_data}

    def analyze_profile(
        self,
        user_id: str,
        photo_url: Optional[str] = None,
        bio: Optional[str] = None,
        posts: Optional[List[str]] = None,
        channel_posts: Optional[List[str]] = None,
        conversation_history: Optional[List[Dict]] = None,
    ) -> Dict:
        """
        Проанализируй профиль пользователя.

        Args:
            user_id: ID пользователя
            photo_url: URL фото профиля
            bio: Биография
            posts: Посты пользователя
            channel_posts: Посты из личного канала
            conversation_history: История диалогов

        Returns:
            Dict с анализом профиля
        """
        profile_data = {
            "user_id": user_id,
            "timestamp": datetime.now(),
            "photo_url": photo_url,
            "bio": bio,
            "posts": posts or [],
            "channel_posts": channel_posts or [],
            "conversation_history": conversation_history or [],
        }

        # Анализируй состояние
        state = self._analyze_state(profile_data)
        profile_data["state"] = state

        # Определи тему
        topic = self._determine_topic(profile_data)
        profile_data["topic"] = topic

        # Сохрани профиль
        self.user_profiles[user_id] = profile_data

        logger.info(f"Profile analyzed for user {user_id}: state={state}, topic={topic}")

        return profile_data

    def generate_message(
        self,
        user_id: str,
        profile_data: Optional[Dict] = None,
    ) -> Optional[str]:
        """
        Сгенерируй сообщение на основе анализа профиля.

        Args:
            user_id: ID пользователя
            profile_data: Данные профиля (если None, используй сохраненные)

        Returns:
            Сгенерированное сообщение или None
        """
        if profile_data is None:
            profile_data = self.user_profiles.get(user_id)

        if not profile_data:
            return None

        state = profile_data.get("state", {})
        topic = profile_data.get("topic")

        # Генерируй сообщение на основе состояния и темы
        message = self._generate_message_by_state(state, topic, profile_data)

        return message

    def _analyze_state(self, profile_data: Dict) -> Dict:
        """Анализируй состояние пользователя."""
        state = {
            "emotional_state": self._analyze_emotional_state(profile_data),
            "energy_level": self._analyze_energy_level(profile_data),
            "focus_areas": self._analyze_focus_areas(profile_data),
            "challenges": self._analyze_challenges(profile_data),
            "growth_indicators": self._analyze_growth(profile_data),
        }
        return state

    def _analyze_emotional_state(self, profile_data: Dict) -> str:
        """Анализируй эмоциональное состояние."""
        text = " ".join([
            profile_data.get("bio", ""),
            " ".join(profile_data.get("posts", [])),
            " ".join(profile_data.get("channel_posts", [])),
        ]).lower()

        # Ключевые слова для определения состояния
        if any(word in text for word in ["грусть", "печаль", "боль", "страдание", "тоска"]):
            return "sadness"
        elif any(word in text for word in ["радость", "счастье", "благодарность", "вдохновение"]):
            return "joy"
        elif any(word in text for word in ["поиск", "вопрос", "неуверенность", "сомнение"]):
            return "uncertainty"
        elif any(word in text for word in ["энергия", "активность", "движение", "действие"]):
            return "active"
        elif any(word in text for word in ["спокойствие", "мир", "гармония", "баланс"]):
            return "peaceful"
        else:
            return "neutral"

    def _analyze_energy_level(self, profile_data: Dict) -> str:
        """Анализируй уровень энергии."""
        posts_count = len(profile_data.get("posts", []))
        channel_posts_count = len(profile_data.get("channel_posts", []))
        total_activity = posts_count + channel_posts_count

        if total_activity > 10:
            return "high"
        elif total_activity > 5:
            return "medium"
        else:
            return "low"

    def _analyze_focus_areas(self, profile_data: Dict) -> List[str]:
        """Анализируй области фокуса."""
        text = " ".join([
            profile_data.get("bio", ""),
            " ".join(profile_data.get("posts", [])),
            " ".join(profile_data.get("channel_posts", [])),
        ]).lower()

        focus_areas = []

        if any(word in text for word in ["энергия", "ритуал", "медитация", "ощущение"]):
            focus_areas.append("energy")
        if any(word in text for word in ["отношения", "мужчина", "женщина", "партнер", "любовь"]):
            focus_areas.append("relationships")
        if any(word in text for word in ["прошлая жизнь", "планета", "храм", "архетип"]):
            focus_areas.append("past_lives")
        if any(word in text for word in ["бизнес", "проект", "творчество", "реализация"]):
            focus_areas.append("business")
        if any(word in text for word in ["трансформация", "изменение", "рост", "развитие"]):
            focus_areas.append("transformation")

        return focus_areas or ["general"]

    def _analyze_challenges(self, profile_data: Dict) -> List[str]:
        """Анализируй вызовы и трудности."""
        text = " ".join([
            profile_data.get("bio", ""),
            " ".join(profile_data.get("posts", [])),
            " ".join(profile_data.get("channel_posts", [])),
        ]).lower()

        challenges = []

        if any(word in text for word in ["страх", "боюсь", "тревога", "беспокойство"]):
            challenges.append("fear")
        if any(word in text for word in ["одиночество", "изоляция", "отчуждение"]):
            challenges.append("loneliness")
        if any(word in text for word in ["неуверенность", "сомнение", "неопределенность"]):
            challenges.append("uncertainty")
        if any(word in text for word in ["блок", "застревание", "стагнация"]):
            challenges.append("stagnation")
        if any(word in text for word in ["конфликт", "борьба", "война", "противоречие"]):
            challenges.append("conflict")

        return challenges

    def _analyze_growth(self, profile_data: Dict) -> List[str]:
        """Анализируй признаки роста."""
        text = " ".join([
            profile_data.get("bio", ""),
            " ".join(profile_data.get("posts", [])),
            " ".join(profile_data.get("channel_posts", [])),
        ]).lower()

        growth = []

        if any(word in text for word in ["осознание", "понимание", "прозрение", "инсайт"]):
            growth.append("awareness")
        if any(word in text for word in ["принятие", "прощение", "отпускание"]):
            growth.append("acceptance")
        if any(word in text for word in ["действие", "шаг", "движение", "начало"]):
            growth.append("action")
        if any(word in text for word in ["благодарность", "признательность", "ценность"]):
            growth.append("gratitude")

        return growth

    def _determine_topic(self, profile_data: Dict) -> str:
        """Определи основную тему."""
        focus_areas = profile_data.get("state", {}).get("focus_areas", ["general"])
        return focus_areas[0] if focus_areas else "general"

    def _generate_message_by_state(
        self,
        state: Dict,
        topic: str,
        profile_data: Dict,
    ) -> str:
        """Сгенерируй сообщение на основе состояния."""
        emotional_state = state.get("emotional_state", "neutral")
        energy_level = state.get("energy_level", "medium")
        challenges = state.get("challenges", [])
        growth = state.get("growth_indicators", [])

        # Базовые сообщения по состоянию
        messages = {
            "sadness": "Вижу, что ты переживаешь. Это требует встречи с собой. Что тебя сейчас волнует?",
            "joy": "Вижу твою радость! Это прекрасно. Что произошло?",
            "uncertainty": "Вижу твои вопросы. Это начало пути. Расскажи, что тебя ищет?",
            "active": "Вижу твою активность! Куда ты движешься?",
            "peaceful": "Вижу твой мир. Что открылось в этом спокойствии?",
            "neutral": "Привет. Что тебя волнует?",
        }

        message = messages.get(emotional_state, messages["neutral"])

        # Добавь контекст на основе вызовов
        if "fear" in challenges:
            message += " Вижу страх. Давай встретимся с ним."
        elif "uncertainty" in challenges:
            message += " Вижу неуверенность. Это нормально на пути."
        elif "stagnation" in challenges:
            message += " Вижу застревание. Пора двигаться."

        # Добавь поддержку на основе роста
        if "awareness" in growth:
            message += " Вижу твое осознание. Продолжай."
        elif "action" in growth:
            message += " Вижу твои действия. Молодец!"

        return message

    def should_write_message(self, user_id: str) -> bool:
        """Определи, нужно ли писать сообщение."""
        profile_data = self.user_profiles.get(user_id)
        if not profile_data:
            return False

        # Пиши, если есть признаки активности или изменений
        state = profile_data.get("state", {})
        challenges = state.get("challenges", [])
        growth = state.get("growth_indicators", [])

        # Пиши, если есть вызовы или признаки роста
        return bool(challenges or growth)


# Глобальный экземпляр анализатора
_profile_analyzer = None


def get_profile_analyzer() -> ProfileAnalyzer:
    """Получи глобальный экземпляр анализатора."""
    global _profile_analyzer
    if _profile_analyzer is None:
        _profile_analyzer = ProfileAnalyzer()
    return _profile_analyzer
