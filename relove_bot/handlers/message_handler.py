"""
Обработчик сообщений с минималистичным интерфейсом.
Предиктивные ответы в виде бабблов для быстрого выбора.
Отслеживание пути пользователя.
"""
from aiogram import Router, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from relove_bot.services.natasha_service import get_natasha_service
from relove_bot.services.journey_service import get_journey_service

router = Router()


def get_quick_response_buttons(response: str) -> InlineKeyboardMarkup:
    """
    Создай кнопки с предиктивными ответами на основе ответа Наташи.
    Максимум 2 кнопки для минимума кликов.
    """
    buttons = [
        [
            InlineKeyboardButton(
                text="👍 Понял",
                callback_data="response_understood"
            ),
            InlineKeyboardButton(
                text="💬 Еще",
                callback_data="response_more"
            ),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message()
async def handle_user_message(message: types.Message):
    """
    Обработай сообщение пользователя.
    Минимум выборов, максимум простоты.
    Отслеживай путь пользователя.
    """
    try:
        # Получи сервисы
        natasha_service = get_natasha_service()
        journey_service = get_journey_service()
        
        # Получи ответ (автоматический выбор промпта)
        result = await natasha_service.get_response(
            user_id=str(message.from_user.id),
            message=message.text
        )
        
        if result["success"]:
            # Добавь в путь пользователя
            from relove_bot.services.prompt_selector import DialogTopic
            topic = DialogTopic(result["topic_enum"].value)
            journey_service.add_journey_entry(
                user_id=str(message.from_user.id),
                message=message.text,
                response=result["response"],
                topic=topic
            )
            
            # Отправь ответ с кнопками для быстрого взаимодействия
            await message.answer(
                result["response"],
                reply_markup=get_quick_response_buttons(result["response"])
            )
        else:
            # Ошибка - просто отправь сообщение без кнопок
            await message.answer("Извини, что-то пошло не так. Попробуй еще раз.")
    
    except Exception as e:
        # Логируй ошибку и отправь простое сообщение
        await message.answer("Извини, что-то пошло не так. Попробуй еще раз.")


@router.callback_query(lambda c: c.data == "response_understood")
async def handle_understood(callback: types.CallbackQuery):
    """Пользователь понял ответ."""
    await callback.answer("✅")
    await callback.message.delete()


@router.callback_query(lambda c: c.data == "response_more")
async def handle_more(callback: types.CallbackQuery):
    """Пользователь хочет еще информации."""
    await callback.answer()
    # Отправь подсказку для продолжения диалога
    await callback.message.answer(
        "Напиши, что еще тебя интересует 👇"
    )
