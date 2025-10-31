import logging
import asyncio
from aiogram import Router, types, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from ..filters.admin import IsAdminFilter
from relove_bot.config import settings
from relove_bot.utils.fill_profiles import fill_all_profiles

logger = logging.getLogger(__name__)
router = Router()
router.message.filter(IsAdminFilter()) # Применяем фильтр ко всем хендлерам в этом роутере
router.callback_query.filter(IsAdminFilter())

# --- Состояния для FSM рассылки ---
class BroadcastState(StatesGroup):
    waiting_for_message = State()
    waiting_for_criteria = State()
    confirming_broadcast = State() # Добавим состояние подтверждения

# --- Команда /fill_profiles ---
@router.message(Command("fill_profiles"))
async def handle_fill_profiles(message: types.Message):
    """Handles the /fill_profiles command for admins."""
    admin_id = message.from_user.id
    logger.info(f"Admin {admin_id} initiated fill_profiles.")
    await message.answer("⏳ Начинаю массовое обновление профилей...")
    channel_id = settings.our_channel_id
    await fill_all_profiles(channel_id)
    await message.answer("✅ Массовое обновление профилей завершено.")

# --- Команда /broadcast и диалог FSM ---

# Вход в диалог
@router.message(Command("broadcast"))
async def handle_broadcast_start(message: types.Message, state: FSMContext):
    """Starts the broadcast dialogue."""
    await state.clear() # Очищаем предыдущее состояние на всякий случай
    await message.answer(
        "Начинаем создание рассылки.\n" \
        "➡️ **Шаг 1/3:** Отправьте сообщение, которое хотите разослать.\n" \
        "Вы можете использовать форматирование HTML.\n" \
        "Для отмены введите /cancel."
    )
    await state.set_state(BroadcastState.waiting_for_message)
    logger.info(f"Admin {message.from_user.id} started broadcast dialogue.")

# Обработка введенного сообщения для рассылки
@router.message(BroadcastState.waiting_for_message)
async def handle_broadcast_message(message: types.Message, state: FSMContext):
    """Receives the message for broadcasting."""
    # Сохраняем ID и текст сообщения в FSM
    # Копируем сообщение, чтобы сохранить его атрибуты (entities для форматирования)
    try:
        copied_message = await message.copy_to(chat_id=message.chat.id, reply_markup=None) # Копируем без кнопок оригинала
        await copied_message.delete() # Удаляем копию, нам нужны только данные
        await state.update_data(broadcast_message_id=copied_message.message_id,
                                broadcast_chat_id=copied_message.chat.id,
                                broadcast_text=copied_message.text,
                                broadcast_entities=copied_message.entities,
                                broadcast_reply_markup=message.reply_markup) # Сохраняем кнопки, если были
        logger.info(f"Admin {message.from_user.id} provided broadcast message.")
    except TelegramBadRequest as e:
        logger.error(f"Error copying broadcast message: {e}")
        await message.answer("❌ Не удалось обработать ваше сообщение. Попробуйте еще раз или отправьте простой текст.")
        return
    except Exception as e:
         logger.error(f"Unexpected error processing broadcast message: {e}", exc_info=True)
         await message.answer("❌ Произошла непредвиденная ошибка. Попробуйте еще раз.")
         return

    await message.answer(
        "Сообщение для рассылки получено.\n" \
        "➡️ **Шаг 2/3:** Введите критерии отбора пользователей.\n" \
        "*Пример:* `stage=active, registered_before=2024-01-01` (пока не реализовано, просто текст).\n" \
        "Или введите `all`, чтобы отправить всем пользователям.\n" \
        "Для отмены введите /cancel."
    )
    await state.set_state(BroadcastState.waiting_for_criteria)

# Обработка введенных критериев
@router.message(BroadcastState.waiting_for_criteria)
async def handle_broadcast_criteria(message: types.Message, state: FSMContext):
    """Receives the criteria for user selection."""
    criteria_text = message.text
    await state.update_data(criteria=criteria_text)
    logger.info(f"Admin {message.from_user.id} provided criteria: {criteria_text}")

    # Показываем сообщение и критерии для подтверждения
    fsm_data = await state.get_data()
    broadcast_chat_id = fsm_data.get('broadcast_chat_id')
    broadcast_message_id = fsm_data.get('broadcast_message_id')

    confirm_text = (
        f"➡️ **Шаг 3/3: Подтверждение**\n\n"
        f"**Критерии:** `{criteria_text}`\n\n"
        f"**Сообщение для рассылки:** (см. ниже)"
    )

    # Кнопки подтверждения
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="✅ Начать рассылку", callback_data="confirm_broadcast")],
        [types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_broadcast")]
    ])

    await message.answer(confirm_text, reply_markup=keyboard)
    # Отправляем предпросмотр сообщения
    if broadcast_chat_id and broadcast_message_id:
        try:
            await message.bot.copy_message(
                chat_id=message.chat.id,
                from_chat_id=broadcast_chat_id,
                message_id=broadcast_message_id,
                reply_markup=fsm_data.get('broadcast_reply_markup')
            )
        except Exception as e:
             logger.error(f"Error sending preview message: {e}")
             await message.answer("Не удалось отобразить предпросмотр сообщения.")

    await state.set_state(BroadcastState.confirming_broadcast)

# Обработка колбека подтверждения рассылки
@router.callback_query(BroadcastState.confirming_broadcast, F.data == "confirm_broadcast")
async def handle_broadcast_confirm(callback_query: types.CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession):
    """Handles the broadcast confirmation."""
    admin_id = callback_query.from_user.id
    fsm_data = await state.get_data()
    criteria = fsm_data.get("criteria", "N/A")
    broadcast_chat_id = fsm_data.get('broadcast_chat_id')
    broadcast_message_id = fsm_data.get('broadcast_message_id')
    reply_markup = fsm_data.get('broadcast_reply_markup')

    logger.info(f"Admin {admin_id} confirmed broadcast with criteria: {criteria}")
    await callback_query.message.edit_text("⏳ Начинаю рассылку...", reply_markup=None)

    # Реализована логика рассылки с фильтрацией по критериям
    user_ids_to_broadcast = []
    try:
        # 1. Получить список пользователей из БД по критериям
        from relove_bot.utils.broadcast_parser import parse_criteria
        from relove_bot.db.repository import UserRepository
        
        criteria_filters = parse_criteria(criteria)
        user_repo = UserRepository(session)
        
        try:
            users = await user_repo.get_users_by_criteria(**criteria_filters)
            user_ids_to_broadcast = [user.id for user in users]
            logger.info(f"Found {len(user_ids_to_broadcast)} users for broadcast with criteria: {criteria}")
        except Exception as e:
            logger.error(f"Error fetching users for broadcast: {e}", exc_info=True)
            await callback_query.message.answer(
                f"❌ Ошибка при получении списка пользователей: {e}\n"
                "Проверь корректность критериев."
            )
            await state.clear()
            return
        
        if not user_ids_to_broadcast:
            await callback_query.message.answer("⚠️ Не найдено пользователей по указанным критериям.")
            await state.clear()
            return

        # 2. Пройтись по списку ID и отправить сообщение.
        #    ВАЖНО: Соблюдать лимиты Telegram (не более 30 сообщений в секунду).
        #    Добавить обработку ошибок (user blocked bot, chat not found, etc.).
        sent_count = 0
        failed_count = 0
        if broadcast_chat_id and broadcast_message_id:
            for user_id in user_ids_to_broadcast:
                try:
                    await bot.copy_message(
                        chat_id=user_id,
                        from_chat_id=broadcast_chat_id,
                        message_id=broadcast_message_id,
                        reply_markup=reply_markup
                    )
                    sent_count += 1
                    logger.debug(f"Broadcast message sent to user {user_id}")
                except (TelegramBadRequest, TelegramForbiddenError) as e:
                    logger.warning(f"Failed to send broadcast to user {user_id}: {e}")
                    failed_count += 1
                    # Помечаем пользователя как неактивного, если он заблокировал бота
                    if "blocked" in str(e).lower() or "forbidden" in str(e).lower():
                        try:
                            from relove_bot.db.repository import UserRepository
                            user_repo = UserRepository(session)
                            await user_repo.update(user_id, {"is_active": False})
                            logger.info(f"Marked user {user_id} as inactive due to blocking bot")
                        except Exception as update_error:
                            logger.warning(f"Failed to update user {user_id} status: {update_error}")
                except Exception as e:
                     logger.error(f"Unexpected error sending broadcast to user {user_id}: {e}", exc_info=True)
                     failed_count += 1
                # Соблюдаем лимит Telegram: не более 30 сообщений в секунду
                # Отправляем с задержкой 0.04 секунды между сообщениями (25 msg/sec для безопасности)
                if (sent_count + failed_count) % 25 == 0 and (sent_count + failed_count) > 0:
                    await asyncio.sleep(1)  # Пауза каждые 25 сообщений
                else:
                    await asyncio.sleep(0.04)  # Небольшая задержка между сообщениями
        else:
            logger.error("Could not find message data to broadcast.")
            await callback_query.message.answer("❌ Ошибка: Не найдены данные сообщения для рассылки.")
            await state.clear()
            return

        await callback_query.message.answer(f"✅ Рассылка завершена.\nУспешно отправлено: {sent_count}\nОшибок: {failed_count}")
        logger.info(f"Broadcast finished for admin {admin_id}. Sent: {sent_count}, Failed: {failed_count}")

    except Exception as e:
        logger.error(f"Error during broadcast execution: {e}", exc_info=True)
        await callback_query.message.answer(f"❌ Произошла ошибка во время рассылки: {e}")
    finally:
        await state.clear()

# --- Обработка отмены --- 
@router.message(Command("cancel"), F.state != None)
async def handle_cancel_dialogue(message: types.Message, state: FSMContext):
    """Handles cancellation of any state."""
    current_state = await state.get_state()
    logger.info(f"Admin {message.from_user.id} cancelled state {current_state}")
    await state.clear()
    await message.answer("Действие отменено.", reply_markup=types.ReplyKeyboardRemove())

# Обработка колбека отмены
@router.callback_query(BroadcastState.confirming_broadcast, F.data == "cancel_broadcast")
async def handle_cancel_broadcast_callback(callback_query: types.CallbackQuery, state: FSMContext):
    """Handles cancellation via callback button."""
    logger.info(f"Admin {callback_query.from_user.id} cancelled broadcast via button.")
    await state.clear()
    await callback_query.message.edit_text("Рассылка отменена.", reply_markup=None)
    await callback_query.answer() 