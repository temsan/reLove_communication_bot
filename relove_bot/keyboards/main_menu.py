"""
Главное меню и клавиатуры для дружелюбного интерфейса.
"""
from aiogram.types import (
    ReplyKeyboardMarkup, 
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)


def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Главное меню с основными действиями"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🎯 Диагностика"),
                KeyboardButton(text="🌀 Потоки reLove")
            ],
            [
                KeyboardButton(text="📊 Мой профиль"),
                KeyboardButton(text="💡 Анализ готовности")
            ],
            [
                KeyboardButton(text="❓ Помощь")
            ]
        ],
        resize_keyboard=True,
        input_field_placeholder="Выбери действие или напиши мне..."
    )
    return keyboard


def get_session_actions_keyboard() -> InlineKeyboardMarkup:
    """Кнопки действий во время сессии"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📊 Сводка сессии",
                    callback_data="session_summary"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🌌 Мой метафизический профиль",
                    callback_data="metaphysical_profile"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🛑 Завершить сессию",
                    callback_data="end_session"
                )
            ]
        ]
    )
    return keyboard


def get_quick_responses_keyboard(stage: str = "start") -> InlineKeyboardMarkup:
    """Предиктивные быстрые ответы в зависимости от этапа"""
    
    if stage == "start":
        # Начало сессии
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Да, готов(а)", callback_data="quick_yes"),
                    InlineKeyboardButton(text="🤔 Расскажи подробнее", callback_data="quick_tell_more")
                ],
                [
                    InlineKeyboardButton(text="⏸ Не сейчас", callback_data="quick_not_now")
                ]
            ]
        )
    elif stage == "deep_work":
        # Глубокая работа
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="💭 Продолжай", callback_data="quick_continue"),
                    InlineKeyboardButton(text="🎯 Дай инсайт", callback_data="quick_insight")
                ],
                [
                    InlineKeyboardButton(text="📊 Что дальше?", callback_data="quick_what_next")
                ]
            ]
        )
    elif stage == "stream_offer":
        # Предложение потока
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="🌀 Узнать о потоках", callback_data="show_streams")
                ],
                [
                    InlineKeyboardButton(text="💬 Продолжить сессию", callback_data="quick_continue"),
                    InlineKeyboardButton(text="🛑 Завершить", callback_data="end_session")
                ]
            ]
        )
    else:
        # По умолчанию
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="💬 Продолжить", callback_data="quick_continue")
                ]
            ]
        )
    
    return keyboard


def get_streams_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с потоками reLove"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎯 Путь Героя",
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
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Назад в меню",
                    callback_data="back_to_menu"
                )
            ]
        ]
    )
    return keyboard


def get_profile_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для просмотра профиля"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🌌 Метафизический профиль",
                    callback_data="metaphysical_profile"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🎯 Мой путь героя",
                    callback_data="my_journey"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📊 История сессий",
                    callback_data="session_history"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Назад в меню",
                    callback_data="back_to_menu"
                )
            ]
        ]
    )
    return keyboard


def get_diagnostic_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для диагностики"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Начать диагностику",
                    callback_data="start_diagnostic"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❓ Что это такое?",
                    callback_data="diagnostic_info"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Назад в меню",
                    callback_data="back_to_menu"
                )
            ]
        ]
    )
    return keyboard
