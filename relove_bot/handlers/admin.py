import logging
import asyncio
from aiogram import Router, types, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from ..filters.admin import IsAdminFilter

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
    logger.info(f"Admin {admin_id} initiated /fill_profiles.")
    await message.answer("⏳ Начинаю процесс заполнения профилей... (Пока имитация)")

    # TODO: Реальная логика заполнения профилей
    # 1. Получить список всех пользователей из БД.
    # 2. Для каждого пользователя проверить/заполнить недостающие данные (например, запросить у Telegram).
    # 3. Сохранить обновления в БД.
    # Возможно, эту операцию лучше выполнять в фоновом режиме (через APScheduler/Celery)
    await asyncio.sleep(2) # Имитация работы

    await message.answer("✅ Процесс заполнения профилей завершен (Имитация)." )

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
async def handle_broadcast_confirm(callback_query: types.CallbackQuery, state: FSMContext, bot: Bot):
    """Handles the broadcast confirmation."""
    admin_id = callback_query.from_user.id
    fsm_data = await state.get_data()
    criteria = fsm_data.get("criteria", "N/A")
    broadcast_chat_id = fsm_data.get('broadcast_chat_id')
    broadcast_message_id = fsm_data.get('broadcast_message_id')
    reply_markup = fsm_data.get('broadcast_reply_markup')

    logger.info(f"Admin {admin_id} confirmed broadcast with criteria: {criteria}")
    await callback_query.message.edit_text("⏳ Начинаю рассылку...", reply_markup=None)

    # --- TODO: Реальная логика рассылки --- 
    user_ids_to_broadcast = []
    try:
        # 1. Получить список пользователей из БД по критериям `criteria`.
        #    Если criteria == 'all', получить всех.
        #    Нужна функция parse_criteria(criteria) -> db_query_filters.
        #    user_ids_to_broadcast = await get_users_from_db(parse_criteria(criteria))
        #    Пока просто имитация:
        if criteria.lower() == 'all':
            user_ids_to_broadcast = [admin_id] # Отправим только админу для теста
            logger.warning("Broadcasting only to admin as DB fetch is not implemented.")
        else:
            logger.warning(f"Criteria parsing and DB fetch not implemented for: {criteria}")
            await callback_query.message.answer(f"⚠️ Фильтрация по критериям `{criteria}` еще не реализована. Рассылка не будет выполнена.")
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
                    # TODO: Возможно, пометить пользователя как неактивного в БД
                except Exception as e:
                     logger.error(f"Unexpected error sending broadcast to user {user_id}: {e}", exc_info=True)
                     failed_count += 1
                await asyncio.sleep(0.1) # Небольшая задержка для избежания лимитов
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