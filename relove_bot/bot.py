import asyncio
import logging
import sys
from typing import Tuple
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.base import BaseStorage
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import BotCommand, BotCommandScopeDefault

from .config import settings
from .handlers import (
    psychological_journey,
    platform_integration,
    common,
    admin
)
from .middlewares.database import DatabaseMiddleware
from .middlewares.logging import LoggingMiddleware
from .db.session import async_session

# Настройка логирования
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format=settings.LOG_FORMAT,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(settings.log_file_path)
    ]
)
logger = logging.getLogger(__name__)

def create_bot_and_dispatcher(storage: BaseStorage = None) -> Tuple[Bot, Dispatcher]:
    """
    Инициализация и возвращение экземпляров бота и диспетчера.
    :param storage: Хранилище для FSM (по умолчанию MemoryStorage)
    :return: кортеж (bot, dispatcher)
    """
    try:
        bot = Bot(token=settings.BOT_TOKEN, parse_mode=ParseMode.HTML)
        # Всегда используем MemoryStorage для упрощения
        storage = MemoryStorage()
        dp = Dispatcher(storage=storage)
        logger.info("Bot and Dispatcher initialized with MemoryStorage.")
        return bot, dp
    except Exception as e:
        logger.exception(f"Ошибка инициализации бота/диспетчера: {e}")
        raise

# Глобальные экземпляры для совместимости
bot, dp = create_bot_and_dispatcher()

# Регистрация middleware
dp.update.middleware(DatabaseMiddleware(async_session))
dp.update.middleware(LoggingMiddleware())

# Регистрация хендлеров
dp.include_router(common.router)
dp.include_router(admin.router)
dp.include_router(psychological_journey.router)
dp.include_router(platform_integration.router)

# Список команд бота
DEFAULT_COMMANDS = [
    BotCommand(command="start", description="🚀 Запустить/перезапустить бота"),
    BotCommand(command="help", description="❓ Получить справку"),
    BotCommand(command="start_journey", description="🎯 Пройти диагностику психотипа и пути героя"),
    BotCommand(command="platform", description="🌟 Перейти на платформу relove.ru"),
]

ADMIN_COMMANDS = [
    BotCommand(command="fill_profiles", description="[Админ] Заполнить профили пользователей (имитация)"),
    BotCommand(command="broadcast", description="[Админ] Создать рассылку пользователям"),
]

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

async def main():
    """Основная функция запуска бота"""
    try:
        # Установка команд бота
        await setup_bot_commands()
        
        # Запуск бота
        logger.info("Starting bot...")
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
    finally:
        # Закрытие сессии бота
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped!")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)