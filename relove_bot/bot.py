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

def include_routers(dispatcher: Dispatcher = None) -> None:
    """
    Подключает роутеры из модуля handlers. Добавляйте другие роутеры здесь.
    :param dispatcher: экземпляр Dispatcher (по умолчанию глобальный dp)
    """
    if dispatcher is None:
        dispatcher = dp
    try:
        from .handlers import common  # Импорт внутри функции для избежания циклических зависимостей
        dispatcher.include_router(common.router)
        logger.info("Common router included.")
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
    except Exception as e:
        logger.exception(f"Ошибка установки команд бота: {e}")