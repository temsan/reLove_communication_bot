import asyncio
import logging
import sys
import os
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
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
from .middlewares.session_check import SessionCheckMiddleware
from .middlewares.profile_update import ProfileUpdateMiddleware
from .db.session import async_session

# Создаем директорию для логов если её нет
os.makedirs(settings.LOG_DIR, exist_ok=True)

# Настройка логирования с ротацией
def setup_logging():
    """Настраивает логирование с ротацией по размеру и времени"""
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, settings.LOG_LEVEL))
    
    # Удаляем существующие обработчики
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Форматтер
    formatter = logging.Formatter(settings.LOG_FORMAT)
    
    # Консольный обработчик
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Файловый обработчик с ротацией по размеру (10 MB)
    # Если файл превышает 10 MB, создается резервная копия
    # На Windows используем только RotatingFileHandler (TimedRotatingFileHandler может иметь проблемы)
    try:
        size_handler = RotatingFileHandler(
            filename=settings.log_file_path,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=10,  # Хранить 10 резервных копий
            encoding='utf-8',
            delay=False
        )
        size_handler.setFormatter(formatter)
        logger.addHandler(size_handler)
    except Exception as e:
        print(f"⚠️ Ошибка при настройке ротации логов: {e}", flush=True)
        # Fallback на простой FileHandler
        simple_handler = logging.FileHandler(settings.log_file_path, encoding='utf-8')
        simple_handler.setFormatter(formatter)
        logger.addHandler(simple_handler)
    
    return logger

logger = setup_logging()

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
        try:
            await setup_bot_commands()
        except Exception as e:
            logger.warning(f"⚠️ Не удалось установить команды бота: {e}")
        
        # Восстановление активных сессий из БД
        await restore_active_sessions()
        
        # Запуск фоновых задач (отключено для отладки)
        # background_tasks = await start_background_tasks()
        
        # Запуск бота
        logger.info("✅ Starting bot...")
        await dp.start_polling(bot)
        
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user")
    except Exception as e:
        error_msg = str(e).lower()
        if "connection refused" in error_msg or "refused" in error_msg:
            logger.error(
                "❌ БД недоступна! Убедитесь, что Docker контейнеры запущены:\n"
                "   docker-compose up -d"
            )
        else:
            logger.error(f"❌ Ошибка при запуске бота: {e}", exc_info=True)
    finally:
        # Закрытие сессии бота
        try:
            await bot.session.close()
        except Exception as e:
            logger.warning(f"⚠️ Ошибка при закрытии сессии бота: {e}")

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
        error_msg = str(e).lower()
        
        if "connection refused" in error_msg or "refused" in error_msg:
            logger.warning(
                "⚠️ БД недоступна при восстановлении сессий. "
                "Убедитесь, что Docker контейнеры запущены: docker-compose up -d"
            )
        elif "timeout" in error_msg:
            logger.warning(f"⏱️ Таймаут при подключении к БД: {e}")
        else:
            logger.error(f"❌ Ошибка при восстановлении сессий: {e}")
        
        # Продолжаем работу бота даже если БД недоступна
        logger.info("Бот продолжит работу без восстановленных сессий")

async def start_background_tasks():
    """Запускает фоновые задачи"""
    try:
        from relove_bot.tasks.background_tasks import (
            profile_rotation_task,
            log_archive_task,
            check_proactive_triggers_task,
            send_proactive_messages_task
        )
        
        # Запускаем задачи
        tasks = [
            asyncio.create_task(profile_rotation_task()),
            asyncio.create_task(log_archive_task()),
            asyncio.create_task(check_proactive_triggers_task()),
            asyncio.create_task(send_proactive_messages_task(bot))
        ]
        
        logger.info("Background tasks started: profile rotation, log archive, proactive triggers, proactive messages")
        
        return tasks
        
    except Exception as e:
        logger.error(f"Error starting background tasks: {e}")
        return []

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped!")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)