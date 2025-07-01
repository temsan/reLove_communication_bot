from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_platform_keyboard(show_purchase: bool = False) -> InlineKeyboardMarkup:
    """Создает клавиатуру для взаимодействия с платформой"""
    keyboard = []
    
    if not show_purchase:
        keyboard.append([
            InlineKeyboardButton(
                text="🎯 Перейти на платформу",
                callback_data="visit_platform"
            )
        ])
    else:
        keyboard.append([
            InlineKeyboardButton(
                text="💫 Узнать о потоках",
                callback_data="show_flows"
            )
        ])
    
    keyboard.append([
        InlineKeyboardButton(
            text="❓ Задать вопрос",
            callback_data="ask_question"
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard) 