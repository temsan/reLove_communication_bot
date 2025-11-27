"""
Стартовое меню - максимально простое.
Минимум текста, максимум простоты.
Одна кнопка - просто начни писать.
"""
from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

router = Router()


def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Главная клавиатура - одна кнопка для начала."""
    buttons = [
        [KeyboardButton(text="💬 Начать")]
    ]
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        one_time_keyboard=False
    )


@router.message(Command("start"))
async def start_command(message: types.Message):
    """Стартовое сообщение - максимум простоты."""
    await message.answer(
        "👋 Привет! Я Наташа.\n\n"
        "Просто напиши, что тебя волнует.",
        reply_markup=get_main_keyboard()
    )


@router.message(lambda msg: msg.text == "💬 Начать")
async def start_writing(message: types.Message):
    """Начни писать."""
    await message.answer("Слушаю 👇")
