"""
Быстрое меню для выбора темы (опционально).
Максимум 2 кнопки, минимум выборов.
"""
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from relove_bot.services.natasha_service import get_natasha_service
from relove_bot.services.prompt_selector import DialogTopic

router = Router()


def get_theme_quick_menu() -> InlineKeyboardMarkup:
    """
    Создай быстрое меню выбора темы.
    Только самые популярные темы.
    """
    buttons = [
        [
            InlineKeyboardButton(
                text="⚡ Энергия",
                callback_data="quick_theme:energy"
            ),
            InlineKeyboardButton(
                text="💖 Отношения",
                callback_data="quick_theme:relationships"
            ),
        ],
        [
            InlineKeyboardButton(
                text="🌙 Прошлые жизни",
                callback_data="quick_theme:past_lives"
            ),
            InlineKeyboardButton(
                text="💼 Бизнес",
                callback_data="quick_theme:business"
            ),
        ],
        [
            InlineKeyboardButton(
                text="🤖 Авто",
                callback_data="quick_theme:auto"
            ),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("theme"))
async def quick_theme_menu(message: types.Message):
    """Быстрое меню выбора темы."""
    await message.answer(
        "Выбери тему (или оставь авто):",
        reply_markup=get_theme_quick_menu()
    )


@router.callback_query(F.data.startswith("quick_theme:"))
async def handle_quick_theme(callback: types.CallbackQuery):
    """Обработай выбор темы."""
    theme_str = callback.data.split(":")[1]
    
    try:
        natasha_service = get_natasha_service()
        
        if theme_str == "auto":
            # Отключи принудительную тему
            natasha_service.set_user_topic_override(
                str(callback.from_user.id),
                None
            )
            await callback.answer("✅ Авто режим")
            await callback.message.edit_text("✅ Авто режим включен")
        else:
            # Установи тему
            topic = DialogTopic(theme_str)
            natasha_service.set_user_topic_override(
                str(callback.from_user.id),
                topic
            )
            await callback.answer("✅")
            await callback.message.edit_text(
                f"✅ Тема: {natasha_service.selector.get_topic_name(topic)}"
            )
    
    except Exception as e:
        await callback.answer("❌ Ошибка")
