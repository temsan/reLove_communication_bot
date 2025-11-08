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
    admin,
    provocative_natasha,
    flexible_diagnostic
)
from .middlewares.database import DatabaseMiddleware
from .middlewares.logging import LoggingMiddleware
from .middlewares.session_check import SessionCheckMiddleware
from .middlewares.profile_update import ProfileUpdateMiddleware
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
        bot = Bot(token=settings.bot_token.get_secret_value(), parse_mode=ParseMode.HTML)
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
dp.update.middleware(ProfileUpdateMiddleware())
dp.update.middleware(SessionCheckMiddleware())

# Регистрация хендлеров
dp.include_router(common.router)
dp.include_router(admin.router)
dp.include_router(psychological_journey.router)
dp.include_router(platform_integration.router)
dp.include_router(provocative_natasha.router)
dp.include_router(flexible_diagnostic.router)

# Список команд бота
DEFAULT_COMMANDS = [
    BotCommand(command="start", description="🚀 Запустить/перезапустить бота"),
    BotCommand(command="help", description="❓ Получить справку"),
    BotCommand(command="start_journey", description="🎯 Пройти диагностику психотипа и пути героя"),
    BotCommand(command="diagnostic", description="💬 Гибкая диагностика через диалог (LLM)"),
    BotCommand(command="natasha", description="🔥 Провокативная сессия с Наташей"),
    BotCommand(command="my_session_summary", description="📊 Сводка текущей сессии"),
    BotCommand(command="my_metaphysical_profile", description="🌌 Мой метафизический профиль"),
    BotCommand(command="streams", description="🌀 Потоки reLove"),
    BotCommand(command="analyze_readiness", description="📈 Анализ готовности к потокам"),
    BotCommand(command="end_session", description="🛑 Завершить сессию"),
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
        
        # Восстановление активных сессий из БД
        await restore_active_sessions()
        
        # Запуск бота
        logger.info("Starting bot...")
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
    finally:
        # Закрытие сессии бота
        await bot.session.close()

async def restore_active_sessions():
    """Восстанавливает активные сессии из БД при перезапуске"""
    try:
        from relove_bot.services.session_service import SessionService
        
        async with async_session() as session:
            service = SessionService(session)
            restored_sessions = await service.restore_active_sessions()
            
            if restored_sessions:
                logger.info(
                    f"Restored {len(restored_sessions)} active sessions: "
                    f"{list(restored_sessions.keys())}"
                )
            else:
                logger.info("No active sessions to restore")
                
    except Exception as e:
        logger.error(f"Error restoring active sessions: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped!")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)