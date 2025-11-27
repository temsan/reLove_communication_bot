"""
Стартовое меню - максимально простое.
Минимум текста, максимум простоты.
"""
from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

router = Router()


def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Главная клавиатура - максимум 2 кнопки."""
    buttons = [
        [
            KeyboardButton(text="💬 Написать Наташе"),
            KeyboardButton(text="⚡ Выбрать тему"),
        ]
    ]
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        one_time_keyboard=False
    )


@router.message(Command("start"))
async def start_command(message: types.Message):
    """Стартовое сообщение."""
    await message.answer(
        "👋 Привет! Я Наташа.\n\n"
        "Просто напиши мне, что тебя волнует.",
        reply_markup=get_main_keyboard()
    )


@router.message(lambda msg: msg.text == "💬 Написать Наташе")
async def write_to_natasha(message: types.Message):
    """Переход к написанию сообщения."""
    await message.answer(
        "Напиши, что тебя волнует 👇"
    )


@router.message(lambda msg: msg.text == "⚡ Выбрать тему")
async def select_theme(message: types.Message):
    """Переход к выбору темы."""
    from relove_bot.handlers.quick_menu_handler import get_theme_quick_menu
    
    await message.answer(
        "Выбери тему:",
        reply_markup=get_theme_quick_menu()
    )
