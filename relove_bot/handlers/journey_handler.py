"""
Обработчик команд для получения и просмотра пути пользователя.
"""
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from relove_bot.services.journey_service import get_journey_service

router = Router()


def get_period_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора периода."""
    buttons = [
        [
            InlineKeyboardButton(
                text="📅 Вчера",
                callback_data="period:yesterday"
            ),
            InlineKeyboardButton(
                text="📊 Неделя",
                callback_data="period:week"
            ),
        ],
        [
            InlineKeyboardButton(
                text="📈 Месяц",
                callback_data="period:month"
            ),
            InlineKeyboardButton(
                text="3️⃣ 3 дня",
                callback_data="period:3"
            ),
        ],
        [
            InlineKeyboardButton(
                text="7️⃣ 7 дней",
                callback_data="period:7"
            ),
            InlineKeyboardButton(
                text="3️⃣0️⃣ 30 дней",
                callback_data="period:30"
            ),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("my_journey"))
async def my_journey_command(message: types.Message):
    """Получи мой путь."""
    await message.answer(
        "📖 Выбери период:",
        reply_markup=get_period_keyboard()
    )


@router.message(Command("my_separations"))
async def my_separations_command(message: types.Message):
    """Получи все разделения пути."""
    journey_service = get_journey_service()
    separations = journey_service.get_all_separations(str(message.from_user.id))

    if separations.get("message"):
        await message.answer(separations["message"])
        return

    text = f"""
📊 **Все твои разделения**

📈 Всего записей: {separations['total_entries']}

🎯 **По темам:**
"""
    for topic, count in separations["by_topic"].items():
        text += f"• {topic}: {count}\n"

    text += f"\n📅 **По датам:** {len(separations['by_date'])} дней\n"
    text += f"📆 **По неделям:** {len(separations['by_week'])} недель\n"

    await message.answer(text, parse_mode="Markdown")


@router.message(Command("journey_summary"))
async def journey_summary_command(message: types.Message):
    """Получи резюме пути за неделю."""
    journey_service = get_journey_service()
    summary = journey_service.get_journey_summary(
        str(message.from_user.id),
        period="week"
    )
    await message.answer(summary, parse_mode="Markdown")


@router.callback_query(F.data.startswith("period:"))
async def handle_period_selection(callback: types.CallbackQuery):
    """Обработай выбор периода."""
    period = callback.data.split(":")[1]
    journey_service = get_journey_service()

    # Получи резюме
    summary = journey_service.get_journey_summary(
        str(callback.from_user.id),
        period=period
    )

    await callback.answer()
    await callback.message.edit_text(summary, parse_mode="Markdown")

    # Отправь детальный путь отдельным сообщением
    detailed = journey_service.get_detailed_journey(
        str(callback.from_user.id),
        period=period
    )

    # Разбей на части если слишком длинно
    if len(detailed) > 4096:
        parts = [detailed[i:i+4096] for i in range(0, len(detailed), 4096)]
        for part in parts:
            await callback.message.answer(part, parse_mode="Markdown")
    else:
        await callback.message.answer(detailed, parse_mode="Markdown")
