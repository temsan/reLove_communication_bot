from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import List, Dict

from relove_bot.core.knowledge_base import DIAGNOSTIC_QUESTIONS

def get_question_keyboard(question_id: int) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру с вариантами ответов для конкретного вопроса.
    
    Args:
        question_id: ID вопроса из DIAGNOSTIC_QUESTIONS
    
    Returns:
        InlineKeyboardMarkup с вариантами ответов
    """
    keyboard = []
    for option in ["a", "b", "c"]:
        keyboard.append([
            InlineKeyboardButton(
                text=f"Вариант {option.upper()}",
                callback_data=f"answer_{question_id}_{option}"
            )
        ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_start_test_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для начала теста.
    
    Returns:
        InlineKeyboardMarkup с кнопкой начала теста
    """
    keyboard = [
        [
            InlineKeyboardButton(
                text="Начать диагностику",
                callback_data="start_diagnostic"
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_platform_link_keyboard(stream_name: str) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру с ссылкой на платформу.
    
    Args:
        stream_name: Название рекомендуемого потока
    
    Returns:
        InlineKeyboardMarkup с кнопкой перехода на платформу
    """
    keyboard = [
        [
            InlineKeyboardButton(
                text="Перейти на платформу",
                callback_data="go_to_platform"
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard) 