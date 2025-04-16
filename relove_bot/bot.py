import logging
from typing import Tuple
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.base import BaseStorage
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeDefault

from .config import settings

logger = logging.getLogger(__name__)


def create_bot_and_dispatcher(storage: BaseStorage = None) -> Tuple[Bot, Dispatcher]:
    """
    Инициализация и возвращение экземпляров бота и диспетчера.
    :param storage: Хранилище для FSM (по умолчанию MemoryStorage)
    :return: кортеж (bot, dispatcher)
    """
    try:
        bot = Bot(token=settings.bot_token.get_secret_value(), parse_mode=ParseMode.HTML)
        if storage is None:
            storage = MemoryStorage()
        dp = Dispatcher(storage=storage)
        logger.info("Bot and Dispatcher initialized successfully.")
        return bot, dp
    except Exception as e:
        logger.exception(f"Ошибка инициализации бота/диспетчера: {e}")
        raise

# Глобальные экземпляры для совместимости
bot, dp = create_bot_and_dispatcher()

# Список команд бота
DEFAULT_COMMANDS = [
    BotCommand(command="start", description="🚀 Запустить/перезапустить бота"),
    BotCommand(command="help", description="❓ Получить справку"),
    # Добавляйте другие команды сюда
]

ADMIN_COMMANDS = [
    BotCommand(command="fill_profiles", description="[Админ] Заполнить профили пользователей (имитация)"),
    BotCommand(command="broadcast", description="[Админ] Создать рассылку пользователям"),
]

def include_routers(dispatcher: Dispatcher = None) -> None:
    """
    Подключает роутеры из модуля handlers. Добавляйте другие роутеры здесь.
    :param dispatcher: экземпляр Dispatcher (по умолчанию глобальный dp)
    """
    if dispatcher is None:
        dispatcher = dp
    try:
        from .handlers import common, admin  # Импорт внутри функции для избежания циклических зависимостей
        dispatcher.include_router(common.router)
        logger.info("Common router included.")
        dispatcher.include_router(admin.router)
        logger.info("Admin router included.")
        # TODO: Добавлять другие роутеры по мере их создания
    except Exception as e:
        logger.exception(f"Ошибка подключения роутеров: {e}")


async def setup_bot_commands(bot_instance: Bot = None) -> None:
    """
    Устанавливает команды меню бота.
    :param bot_instance: экземпляр Bot (по умолчанию глобальный bot)
    """
    if bot_instance is None:
        bot_instance = bot
    try:
        await bot_instance.set_my_commands(DEFAULT_COMMANDS, BotCommandScopeDefault())
        logger.info("Bot commands set.")
        # Устанавливаем расширенный список команд для админов
        if settings.admin_ids:
            all_commands = DEFAULT_COMMANDS + ADMIN_COMMANDS
            admin_scopes = [BotCommandScopeDefault(chat_id=admin_id) for admin_id in settings.admin_ids]
            for scope in admin_scopes:
                try:
                    await bot_instance.set_my_commands(all_commands, scope)
                except Exception as e:
                    logger.error(f"Failed to set commands for admin scope {scope.chat_id}: {e}")
            logger.info(f"Admin commands set for {len(settings.admin_ids)} admins.")
        else:
            logger.info("Bot commands set for default scope only (no admins configured).")
    except Exception as e:
        logger.exception(f"Ошибка установки команд бота: {e}")