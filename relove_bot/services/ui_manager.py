"""
UI Manager для создания адаптивных интерфейсов в стиле relove.ru
"""
import enum
from typing import List, Dict, Optional
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from relove_bot.db.models import JourneyStageEnum


class KeyboardStyle(enum.Enum):
    """Стили клавиатур"""
    RELOVE = "relove"
    MINIMAL = "minimal"
    PROVOCATIVE = "provocative"


class UIManager:
    """Менеджер для создания UI элементов в стиле relove.ru"""
    
    # Эмодзи для стилей
    RELOVE_EMOJIS = {
        "fire": "🔥",
        "check": "✅",
        "circle": "⚪️",
        "star": "✨",
        "heart": "❤️",
        "skull": "💀",
        "fear": "😰",
        "vampire": "🧛",
        "light": "☀️",
        "dark": "🌑"
    }
    
    # Quick replies для каждого этапа пути героя
    STAGE_QUICK_REPLIES = {
        JourneyStageEnum.ORDINARY_WORLD: [
            ("Да, чувствую дискомфорт", "quick_yes_discomfort"),
            ("Нет, всё нормально", "quick_no_normal"),
            ("Расскажи больше", "quick_tell_more")
        ],
        JourneyStageEnum.CALL_TO_ADVENTURE: [
            ("Интересно, продолжай", "quick_interested"),
            ("Боюсь", "quick_afraid"),
            ("Что мне делать?", "quick_what_to_do")
        ],
        JourneyStageEnum.REFUSAL: [
            ("Не готов(а)", "quick_not_ready"),
            ("Боюсь изменений", "quick_fear_change"),
            ("Расскажи больше", "quick_tell_more")
        ],
        JourneyStageEnum.MEETING_MENTOR: [
            ("Готов(а) действовать", "quick_ready_act"),
            ("Что делать?", "quick_what_to_do"),
            ("Дай инструкцию", "quick_give_instruction")
        ],
        JourneyStageEnum.CROSSING_THRESHOLD: [
            ("Начинаю", "quick_starting"),
            ("Продолжай вести", "quick_continue_guide"),
            ("Что дальше?", "quick_what_next")
        ],
        JourneyStageEnum.TESTS_ALLIES_ENEMIES: [
            ("Готов(а) принять 💀", "quick_accept_death"),
            ("Боюсь 😰", "quick_afraid"),
            ("Продолжай", "quick_continue")
        ],
        JourneyStageEnum.APPROACH: [
            ("Готов(а) к главному", "quick_ready_main"),
            ("Нужна поддержка", "quick_need_support"),
            ("Продолжай", "quick_continue")
        ],
        JourneyStageEnum.ORDEAL: [
            ("Принимаю", "quick_accept"),
            ("Страшно", "quick_scary"),
            ("Держи за руку", "quick_hold_hand")
        ],
        JourneyStageEnum.REWARD: [
            ("Вижу результат", "quick_see_result"),
            ("Что дальше?", "quick_what_next"),
            ("Продолжай", "quick_continue")
        ],
        JourneyStageEnum.ROAD_BACK: [
            ("Интегрирую опыт", "quick_integrate"),
            ("Как применить?", "quick_how_apply"),
            ("Продолжай", "quick_continue")
        ],
        JourneyStageEnum.RESURRECTION: [
            ("Чувствую трансформацию", "quick_feel_transform"),
            ("Что изменилось?", "quick_what_changed"),
            ("Продолжай", "quick_continue")
        ],
        JourneyStageEnum.RETURN_WITH_ELIXIR: [
            ("Готов(а) делиться", "quick_ready_share"),
            ("Что дальше?", "quick_what_next"),
            ("Спасибо", "quick_thanks")
        ]
    }
    
    def create_quick_replies(
        self,
        stage: JourneyStageEnum,
        style: KeyboardStyle = KeyboardStyle.RELOVE
    ) -> InlineKeyboardMarkup:
        """
        Создаёт quick reply кнопки для этапа пути героя
        
        Args:
            stage: Текущий этап пути героя
            style: Стиль клавиатуры
        
        Returns:
            InlineKeyboardMarkup с кнопками
        """
        replies = self.STAGE_QUICK_REPLIES.get(stage, [
            ("Продолжай", "quick_continue"),
            ("Расскажи больше", "quick_tell_more")
        ])
        
        # Ограничиваем до 3 кнопок
        replies = replies[:3]
        
        buttons = []
        for text, callback_data in replies:
            buttons.append([InlineKeyboardButton(text=text, callback_data=callback_data)])
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def format_progress_indicator(
        self,
        current_stage: JourneyStageEnum,
        completed_stages: List[str]
    ) -> str:
        """
        Форматирует индикатор прогресса с эмодзи
        
        Args:
            current_stage: Текущий этап
            completed_stages: Список завершённых этапов
        
        Returns:
            Строка с визуальным индикатором
        """
        all_stages = list(JourneyStageEnum)
        completed_set = set(completed_stages)
        
        lines = ["**🗺 Твой путь героя:**\n"]
        
        for stage in all_stages:
            if stage.value in completed_set:
                emoji = self.RELOVE_EMOJIS["check"]
            elif stage == current_stage:
                emoji = self.RELOVE_EMOJIS["fire"]
            else:
                emoji = self.RELOVE_EMOJIS["circle"]
            
            lines.append(f"{emoji} {stage.value}")
        
        # Расчёт процента завершения
        total_stages = len(all_stages)
        completed_count = len(completed_set)
        progress_percent = int((completed_count / total_stages) * 100)
        
        lines.append(f"\n**Прогресс:** {progress_percent}%")
        
        return "\n".join(lines)
    
    def apply_relove_styling(
        self,
        text: str,
        emphasis: List[str] = None
    ) -> str:
        """
        Применяет минималистичный стиль relove.ru к тексту
        
        Args:
            text: Исходный текст
            emphasis: Список фраз для выделения жирным
        
        Returns:
            Отформатированный текст
        """
        # Разбиваем на абзацы
        paragraphs = text.split('\n\n')
        
        formatted = []
        for para in paragraphs:
            # Ограничиваем длину абзаца
            if len(para) > 200:
                # Разбиваем длинный абзац
                sentences = para.split('. ')
                current_para = []
                current_length = 0
                
                for sentence in sentences:
                    if current_length + len(sentence) > 200 and current_para:
                        formatted.append('. '.join(current_para) + '.')
                        current_para = [sentence]
                        current_length = len(sentence)
                    else:
                        current_para.append(sentence)
                        current_length += len(sentence)
                
                if current_para:
                    formatted.append('. '.join(current_para))
            else:
                formatted.append(para)
        
        result = '\n\n'.join(formatted)
        
        # Выделяем ключевые фразы жирным
        if emphasis:
            for phrase in emphasis:
                result = result.replace(phrase, f"**{phrase}**")
        
        return result
    
    def create_inline_keyboard(
        self,
        buttons: List[Dict[str, str]],
        style: KeyboardStyle = KeyboardStyle.RELOVE
    ) -> InlineKeyboardMarkup:
        """
        Создаёт inline клавиатуру
        
        Args:
            buttons: Список словарей с text и callback_data
            style: Стиль клавиатуры
        
        Returns:
            InlineKeyboardMarkup
        """
        keyboard_buttons = []
        
        for button in buttons:
            text = button.get("text", "")
            callback_data = button.get("callback_data", "")
            
            # Добавляем эмодзи в зависимости от стиля
            if style == KeyboardStyle.PROVOCATIVE:
                if "принять" in text.lower():
                    text = f"{self.RELOVE_EMOJIS['skull']} {text}"
                elif "боюсь" in text.lower():
                    text = f"{self.RELOVE_EMOJIS['fear']} {text}"
            
            keyboard_buttons.append([InlineKeyboardButton(text=text, callback_data=callback_data)])
        
        return InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
