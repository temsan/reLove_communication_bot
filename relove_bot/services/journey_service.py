"""
Сервис для отслеживания и консолидации пути пользователя.
Разделения, консолидации, анализ за периоды.
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import logging

from relove_bot.services.natasha_service import get_natasha_service
from relove_bot.services.prompt_selector import DialogTopic

logger = logging.getLogger(__name__)


class JourneyService:
    """Сервис для работы с путем пользователя."""

    def __init__(self):
        """Инициализируй сервис."""
        self.user_journeys = {}  # {user_id: [journey_entries]}

    def add_journey_entry(
        self,
        user_id: str,
        message: str,
        response: str,
        topic: DialogTopic,
        timestamp: Optional[datetime] = None
    ):
        """
        Добавь запись в путь пользователя.

        Args:
            user_id: ID пользователя
            message: Сообщение пользователя
            response: Ответ Наташи
            topic: Тема диалога
            timestamp: Время (по умолчанию сейчас)
        """
        if user_id not in self.user_journeys:
            self.user_journeys[user_id] = []

        entry = {
            "timestamp": timestamp or datetime.now(),
            "message": message,
            "response": response,
            "topic": topic.value,
            "topic_name": self._get_topic_name(topic),
        }

        self.user_journeys[user_id].append(entry)
        logger.info(f"Journey entry added for user {user_id}: {topic}")

    def get_journey_for_period(
        self,
        user_id: str,
        period: str = "week"
    ) -> List[Dict]:
        """
        Получи путь пользователя за период.

        Args:
            user_id: ID пользователя
            period: Период (yesterday, week, month, или число дней)

        Returns:
            Список записей за период
        """
        if user_id not in self.user_journeys:
            return []

        now = datetime.now()
        start_date = self._get_period_start(now, period)

        entries = [
            entry
            for entry in self.user_journeys[user_id]
            if entry["timestamp"] >= start_date
        ]

        return sorted(entries, key=lambda x: x["timestamp"])

    def consolidate_journey(
        self,
        user_id: str,
        period: str = "week"
    ) -> Dict:
        """
        Консолидируй путь пользователя за период.

        Args:
            user_id: ID пользователя
            period: Период (yesterday, week, month, или число дней)

        Returns:
            Dict с консолидированной информацией
        """
        entries = self.get_journey_for_period(user_id, period)

        if not entries:
            return {
                "period": period,
                "total_entries": 0,
                "message": "Нет записей за этот период",
            }

        # Подсчитай статистику
        topics_count = {}
        for entry in entries:
            topic = entry["topic_name"]
            topics_count[topic] = topics_count.get(topic, 0) + 1

        # Получи основные темы
        main_topics = sorted(
            topics_count.items(),
            key=lambda x: x[1],
            reverse=True
        )[:3]

        # Создай консолидацию
        consolidation = {
            "period": period,
            "period_name": self._get_period_name(period),
            "total_entries": len(entries),
            "date_range": {
                "from": entries[0]["timestamp"].strftime("%d.%m.%Y"),
                "to": entries[-1]["timestamp"].strftime("%d.%m.%Y"),
            },
            "topics": dict(main_topics),
            "entries": entries,
        }

        return consolidation

    def get_all_separations(self, user_id: str) -> Dict:
        """
        Получи все разделения пути пользователя.
        Разделения по темам, датам, типам.

        Args:
            user_id: ID пользователя

        Returns:
            Dict с разделениями
        """
        if user_id not in self.user_journeys:
            return {"message": "Нет записей"}

        entries = self.user_journeys[user_id]

        # Разделение по темам
        by_topic = {}
        for entry in entries:
            topic = entry["topic_name"]
            if topic not in by_topic:
                by_topic[topic] = []
            by_topic[topic].append(entry)

        # Разделение по датам
        by_date = {}
        for entry in entries:
            date = entry["timestamp"].strftime("%d.%m.%Y")
            if date not in by_date:
                by_date[date] = []
            by_date[date].append(entry)

        # Разделение по неделям
        by_week = {}
        for entry in entries:
            week = entry["timestamp"].strftime("Неделя %W (%Y)")
            if week not in by_week:
                by_week[week] = []
            by_week[week].append(entry)

        return {
            "total_entries": len(entries),
            "by_topic": {
                topic: len(entries_list)
                for topic, entries_list in by_topic.items()
            },
            "by_date": {
                date: len(entries_list)
                for date, entries_list in by_date.items()
            },
            "by_week": {
                week: len(entries_list)
                for week, entries_list in by_week.items()
            },
            "topics_detail": by_topic,
            "dates_detail": by_date,
            "weeks_detail": by_week,
        }

    def get_journey_summary(
        self,
        user_id: str,
        period: str = "week"
    ) -> str:
        """
        Получи текстовое резюме пути за период.

        Args:
            user_id: ID пользователя
            period: Период

        Returns:
            Текстовое резюме
        """
        consolidation = self.consolidate_journey(user_id, period)

        if consolidation.get("total_entries", 0) == 0:
            return f"📭 Нет записей за {consolidation.get('period_name', period)}"

        summary = f"""
📊 **Твой путь за {consolidation['period_name']}**

📈 Всего записей: {consolidation['total_entries']}
📅 Период: {consolidation['date_range']['from']} - {consolidation['date_range']['to']}

🎯 Основные темы:
"""
        for topic, count in consolidation["topics"].items():
            summary += f"• {topic}: {count} записей\n"

        return summary

    def get_detailed_journey(
        self,
        user_id: str,
        period: str = "week"
    ) -> str:
        """
        Получи детальный путь за период.

        Args:
            user_id: ID пользователя
            period: Период

        Returns:
            Детальное описание пути
        """
        entries = self.get_journey_for_period(user_id, period)

        if not entries:
            return "📭 Нет записей за этот период"

        detailed = f"📖 **Твой путь за {self._get_period_name(period)}**\n\n"

        for i, entry in enumerate(entries, 1):
            time = entry["timestamp"].strftime("%d.%m %H:%M")
            topic = entry["topic_name"]
            message = entry["message"][:50] + "..." if len(entry["message"]) > 50 else entry["message"]

            detailed += f"{i}. [{time}] {topic}\n"
            detailed += f"   Q: {message}\n"
            detailed += f"   A: {entry['response'][:100]}...\n\n"

        return detailed

    @staticmethod
    def _get_period_start(now: datetime, period: str) -> datetime:
        """Получи начало периода."""
        if period == "yesterday":
            return (now - timedelta(days=1)).replace(hour=0, minute=0, second=0)
        elif period == "week":
            return (now - timedelta(days=7)).replace(hour=0, minute=0, second=0)
        elif period == "month":
            return (now - timedelta(days=30)).replace(hour=0, minute=0, second=0)
        elif period.isdigit():
            return (now - timedelta(days=int(period))).replace(hour=0, minute=0, second=0)
        else:
            return (now - timedelta(days=7)).replace(hour=0, minute=0, second=0)

    @staticmethod
    def _get_period_name(period: str) -> str:
        """Получи название периода."""
        if period == "yesterday":
            return "вчера"
        elif period == "week":
            return "за неделю"
        elif period == "month":
            return "за месяц"
        elif period.isdigit():
            days = int(period)
            if days == 1:
                return "за день"
            elif days == 3:
                return "за 3 дня"
            elif days == 7:
                return "за неделю"
            else:
                return f"за {days} дней"
        else:
            return "за период"

    @staticmethod
    def _get_topic_name(topic: DialogTopic) -> str:
        """Получи название темы."""
        names = {
            DialogTopic.ENERGY: "⚡ Энергия",
            DialogTopic.RELATIONSHIPS: "💖 Отношения",
            DialogTopic.PAST_LIVES: "🌙 Прошлые жизни",
            DialogTopic.BUSINESS: "💼 Бизнес",
            DialogTopic.GENERAL: "🤖 Общий",
            DialogTopic.DIAGNOSTIC: "🔍 Диагностика",
        }
        return names.get(topic, str(topic))


# Глобальный экземпляр сервиса
_journey_service = None


def get_journey_service() -> JourneyService:
    """Получи глобальный экземпляр сервиса."""
    global _journey_service
    if _journey_service is None:
        _journey_service = JourneyService()
    return _journey_service
