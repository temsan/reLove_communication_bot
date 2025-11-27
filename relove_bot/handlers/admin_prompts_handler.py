"""
Админ-обработчик для управления промптами Наташи.
Видимость только для админа.
"""
import os
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from relove_bot.services.natasha_service import get_natasha_service
from relove_bot.services.prompt_selector import DialogTopic

router = Router()

# Админ ID - загружается из переменной окружения
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))


def is_admin(user_id: int) -> bool:
    """Проверь, является ли пользователь админом."""
    return user_id == ADMIN_ID and ADMIN_ID != 0


def get_topic_keyboard() -> InlineKeyboardMarkup:
    """Получи клавиатуру с темами."""
    buttons = [
        [
            InlineKeyboardButton(
                text="⚡ Энергия",
                callback_data=f"set_topic:{DialogTopic.ENERGY.value}",
            ),
            InlineKeyboardButton(
                text="💖 Отношения",
                callback_data=f"set_topic:{DialogTopic.RELATIONSHIPS.value}",
            ),
        ],
        [
            InlineKeyboardButton(
                text="🌙 Прошлые жизни",
                callback_data=f"set_topic:{DialogTopic.PAST_LIVES.value}",
            ),
            InlineKeyboardButton(
                text="💼 Бизнес",
                callback_data=f"set_topic:{DialogTopic.BUSINESS.value}",
            ),
        ],
        [
            InlineKeyboardButton(
                text="🤖 Авто",
                callback_data="set_topic:auto",
            ),
            InlineKeyboardButton(
                text="❌ Отмена",
                callback_data="set_topic:cancel",
            ),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("admin_prompts"))
async def admin_prompts_menu(message: types.Message):
    """Админ-меню для управления промптами."""
    if not is_admin(message.from_user.id):
        # Молча игнорируй - не показывай, что команда существует
        return

    text = """
🎯 **Админ-меню промптов Наташи**

Выберите действие:
• `/set_topic_for <user_id> <topic>` - установить тему для пользователя
• `/clear_history <user_id>` - очистить историю диалога
• `/stats` - статистика по диалогам
• `/topics` - список доступных тем

**Доступные темы:**
• `energy` - Энергетическая работа
• `relationships` - Отношения
• `past_lives` - Прошлые жизни
• `business` - Бизнес
• `general` - Общий диалог
• `diagnostic` - Диагностика
"""
    await message.answer(text, parse_mode="Markdown")


@router.message(Command("set_topic_for"))
async def set_topic_for_user(message: types.Message):
    """Установи тему для пользователя."""
    if not is_admin(message.from_user.id):
        return  # Молча игнорируй

    args = message.text.split()
    if len(args) < 3:
        await message.answer(
            "❌ Использование: `/set_topic_for <user_id> <topic>`",
            parse_mode="Markdown",
        )
        return

    try:
        user_id = args[1]
        topic_str = args[2]

        # Проверь, существует ли такая тема
        try:
            topic = DialogTopic(topic_str)
        except ValueError:
            await message.answer(
                f"❌ Неизвестная тема: {topic_str}\n"
                f"Доступные: energy, relationships, past_lives, business, general, diagnostic"
            )
            return

        # Установи тему
        natasha_service = get_natasha_service()
        natasha_service.set_user_topic_override(user_id, topic)

        await message.answer(
            f"✅ Тема установлена для пользователя {user_id}:\n"
            f"📌 {natasha_service.selector.get_topic_name(topic)}"
        )

    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")


@router.message(Command("clear_history"))
async def clear_user_history(message: types.Message):
    """Очисти историю диалога пользователя."""
    if not is_admin(message.from_user.id):
        return  # Молча игнорируй

    args = message.text.split()
    if len(args) < 2:
        await message.answer(
            "❌ Использование: `/clear_history <user_id>`",
            parse_mode="Markdown",
        )
        return

    try:
        user_id = args[1]
        natasha_service = get_natasha_service()
        natasha_service.clear_conversation_history(user_id)

        await message.answer(f"✅ История диалога очищена для пользователя {user_id}")

    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")


@router.message(Command("stats"))
async def show_statistics(message: types.Message):
    """Покажи статистику по диалогам."""
    if not is_admin(message.from_user.id):
        return  # Молча игнорируй

    try:
        natasha_service = get_natasha_service()
        stats = natasha_service.get_statistics()

        text = f"""
📊 **Статистика диалогов**

👥 Всего пользователей: {stats['total_users']}
💬 Всего сообщений: {stats['total_messages']}
📈 Среднее сообщений на пользователя: {stats['avg_messages_per_user']:.1f}
"""
        await message.answer(text, parse_mode="Markdown")

    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")


@router.message(Command("topics"))
async def show_available_topics(message: types.Message):
    """Покажи доступные темы."""
    if not is_admin(message.from_user.id):
        return  # Молча игнорируй

    try:
        natasha_service = get_natasha_service()
        topics = natasha_service.get_available_topics()

        text = "📌 **Доступные темы:**\n\n"
        for topic_id, topic_name in topics.items():
            text += f"• `{topic_id}` - {topic_name}\n"

        await message.answer(text, parse_mode="Markdown")

    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")


@router.callback_query(F.data.startswith("set_topic:"))
async def handle_topic_selection(callback: types.CallbackQuery):
    """Обработай выбор темы через кнопку."""
    if not is_admin(callback.from_user.id):
        await callback.answer()  # Молча игнорируй
        return

    topic_str = callback.data.split(":")[1]

    if topic_str == "cancel":
        await callback.message.delete()
        await callback.answer("❌ Отменено")
        return

    if topic_str == "auto":
        # Отключи принудительную тему
        natasha_service = get_natasha_service()
        natasha_service.set_user_topic_override(str(callback.from_user.id), None)
        await callback.answer("✅")
        await callback.message.delete()
        await callback.message.answer("✅ Автоматический выбор включен")
        return

    try:
        topic = DialogTopic(topic_str)
        natasha_service = get_natasha_service()
        natasha_service.set_user_topic_override(str(callback.from_user.id), topic)

        await callback.answer("✅")
        await callback.message.delete()
        await callback.message.answer(
            f"✅ Тема установлена: {natasha_service.selector.get_topic_name(topic)}"
        )

    except Exception as e:
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


@router.message(Command("my_topic"))
async def show_my_topic(message: types.Message):
    """Покажи текущую тему для админа."""
    if not is_admin(message.from_user.id):
        return  # Молча игнорируй

    try:
        natasha_service = get_natasha_service()
        topic = natasha_service.get_user_topic_override(str(message.from_user.id))

        if topic:
            text = (
                f"📌 Текущая тема: {natasha_service.selector.get_topic_name(topic)}\n\n"
                f"Нажми кнопку ниже, чтобы изменить:"
            )
        else:
            text = (
                "🤖 Текущий режим: Автоматический выбор\n\n"
                "Нажми кнопку ниже, чтобы установить фиксированную тему:"
            )

        await message.answer(text, reply_markup=get_topic_keyboard())

    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
