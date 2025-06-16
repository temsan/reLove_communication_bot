from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import Dict

def get_diagnostic_keyboard(options: Dict[str, str]) -> InlineKeyboardMarkup:
    """Создает клавиатуру с вариантами ответов для диагностического теста"""
    keyboard = []
    
    for key, text in options.items():
        keyboard.append([
            InlineKeyboardButton(
                text=text,
                callback_data=f"answer_{key}"
            )
        ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard) 