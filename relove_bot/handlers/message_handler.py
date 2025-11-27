"""
Обработчик сообщений с минималистичным интерфейсом.
Предиктивные ответы в виде бабблов для быстрого выбора.
Отслеживание пути пользователя.
Максимум простоты, минимум кликов.
"""
from aiogram import Router, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from relove_bot.services.natasha_service import get_natasha_service
from relove_bot.services.journey_service import get_journey_service

router = Router()


def get_predictive_bubbles(response: str, topic: str) -> InlineKeyboardMarkup:
    """
    Создай умные предиктивные бабблы на основе ответа и темы.
    Максимум 2 кнопки для минимума кликов.
    """
    # Предиктивные ответы в зависимости от темы
    predictive_responses = {
        "energy": [
            ("✨ Почувствовать еще", "action_feel_more"),
            ("🔮 Углубиться", "action_deepen"),
        ],
        "relationships": [
            ("💭 Понять себя", "action_understand_self"),
            ("🤝 Принять", "action_accept"),
        ],
        "past_lives": [
            ("🌙 Вспомнить", "action_remember"),
            ("🔗 Связать с сейчас", "action_connect"),
        ],
        "business": [
            ("🎯 Действовать", "action_act"),
            ("💡 Переосмыслить", "action_rethink"),
        ],
        "general": [
            ("👍 Понял", "response_understood"),
            ("💬 Еще", "response_more"),
        ],
    }

    buttons_data = predictive_responses.get(topic, predictive_responses["general"])
    buttons = [[
        InlineKeyboardButton(text=buttons_data[0][0], callback_data=buttons_data[0][1]),
        InlineKeyboardButton(text=buttons_data[1][0], callback_data=buttons_data[1][1]),
    ]]
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message()
async def handle_user_message(message: types.Message):
    """
    Обработай сообщение пользователя.
    Минимум выборов, максимум простоты.
    Отслеживай путь пользователя.
    Умные предиктивные бабблы.
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
            
            # Отправь ответ с умными предиктивными бабблами
            await message.answer(
                result["response"],
                reply_markup=get_predictive_bubbles(result["response"], topic.value)
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
    await callback.message.answer("Напиши, что еще тебя интересует 👇")


@router.callback_query(lambda c: c.data == "action_feel_more")
async def handle_feel_more(callback: types.CallbackQuery):
    """Пользователь хочет почувствовать еще."""
    await callback.answer()
    await callback.message.delete()
    await callback.message.answer("Углубляйся в ощущение. Что ты чувствуешь? 👇")


@router.callback_query(lambda c: c.data == "action_deepen")
async def handle_deepen(callback: types.CallbackQuery):
    """Пользователь хочет углубиться."""
    await callback.answer()
    await callback.message.delete()
    await callback.message.answer("Расскажи подробнее 👇")


@router.callback_query(lambda c: c.data == "action_understand_self")
async def handle_understand_self(callback: types.CallbackQuery):
    """Пользователь хочет понять себя."""
    await callback.answer()
    await callback.message.delete()
    await callback.message.answer("Что ты о себе узнала? 👇")


@router.callback_query(lambda c: c.data == "action_accept")
async def handle_accept(callback: types.CallbackQuery):
    """Пользователь готов принять."""
    await callback.answer()
    await callback.message.delete()
    await callback.message.answer("Как это меняет твое понимание? 👇")


@router.callback_query(lambda c: c.data == "action_remember")
async def handle_remember(callback: types.CallbackQuery):
    """Пользователь хочет вспомнить."""
    await callback.answer()
    await callback.message.delete()
    await callback.message.answer("Что еще ты помнишь? 👇")


@router.callback_query(lambda c: c.data == "action_connect")
async def handle_connect(callback: types.CallbackQuery):
    """Пользователь хочет связать с сейчас."""
    await callback.answer()
    await callback.message.delete()
    await callback.message.answer("Как это связано с твоей жизнью сейчас? 👇")


@router.callback_query(lambda c: c.data == "action_act")
async def handle_act(callback: types.CallbackQuery):
    """Пользователь готов действовать."""
    await callback.answer()
    await callback.message.delete()
    await callback.message.answer("Какой первый шаг? 👇")


@router.callback_query(lambda c: c.data == "action_rethink")
async def handle_rethink(callback: types.CallbackQuery):
    """Пользователь хочет переосмыслить."""
    await callback.answer()
    await callback.message.delete()
    await callback.message.answer("Что изменилось в твоем понимании? 👇")
