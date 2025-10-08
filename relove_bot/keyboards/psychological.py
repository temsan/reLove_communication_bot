from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from ..core.psychological_types import PsychotypeEnum
from ..core.hero_journey import JourneyStageEnum

def get_psychological_type_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру для выбора психологического типа"""
    keyboard = []
    for type_enum in PsychotypeEnum:
        keyboard.append([
            InlineKeyboardButton(
                text=type_enum.value,
                callback_data=type_enum.name
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_journey_stage_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру для выбора этапа путешествия"""
    keyboard = []
    for stage_enum in JourneyStageEnum:
        keyboard.append([
            InlineKeyboardButton(
                text=stage_enum.value,
                callback_data=stage_enum.name
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_question_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру для ответа на вопрос"""
    keyboard = [
        [
            InlineKeyboardButton(
                text="Пропустить вопрос",
                callback_data="skip_question"
            )
        ],
        [
            InlineKeyboardButton(
                text="Завершить этап",
                callback_data="finish_stage"
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_stream_selection_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру для выбора потока reLove"""
    keyboard = [
        [
            InlineKeyboardButton(
                text="🦸 Путь Героя",
                callback_data="stream_hero_path"
            )
        ],
        [
            InlineKeyboardButton(
                text="🌌 Прошлые Жизни",
                callback_data="stream_past_lives"
            )
        ],
        [
            InlineKeyboardButton(
                text="❤️ Открытие Сердца",
                callback_data="stream_heart_opening"
            )
        ],
        [
            InlineKeyboardButton(
                text="🌑 Трансформация Тени",
                callback_data="stream_shadow_work"
            )
        ],
        [
            InlineKeyboardButton(
                text="✨ Пробуждение",
                callback_data="stream_awakening"
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard) 