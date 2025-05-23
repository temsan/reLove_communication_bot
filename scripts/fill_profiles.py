#!/usr/bin/env python3
# Отключаем предупреждения до импорта других библиотек
import warnings
warnings.filterwarnings('ignore', category=FutureWarning, module='transformers*')
warnings.filterwarnings('ignore', category=UserWarning, module='transformers*')

import os
import sys
import asyncio
import logging
from dotenv import load_dotenv

# Добавляем корень проекта в PYTHONPATH для корректного импорта
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from relove_bot.config import settings, reload_settings # reload_settings может быть нужен для инициализации
from relove_bot.services.batch_profile_fill_service import process_all_channel_profiles_batch
from relove_bot.db.database import setup_database # Оставляем для возможной инициализации БД перед запуском сервиса

# Настройка логирования - только критические ошибки и прогресс
# Основное логирование будет происходить внутри сервиса
logging.basicConfig(
    level=logging.CRITICAL, # Устанавливаем CRITICAL по умолчанию для корневого логгера
    format='%(asctime)s - %(levelname)s - %(message)s', # Упрощенный формат для скрипта
    handlers=[
        logging.StreamHandler(), # Вывод в консоль
        logging.FileHandler('fill_profiles_critical.log', mode='a') # Запись критических ошибок в файл
    ]
)

# Настраиваем логгер конкретно для этого скрипта, если нужно выводить INFO о старте/завершении
script_logger = logging.getLogger(__name__)
script_logger.setLevel(logging.INFO) # Позволяем INFO для сообщений о старте/окончании

# Отключаем детальное логирование для других модулей на уровне этого скрипта,
# чтобы не дублировать логи сервисов, если они настроены иначе.
# Логирование relove_bot будет управляться его собственными настройками.
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy').setLevel(logging.WARNING)
logging.getLogger('aiosqlite').setLevel(logging.WARNING)
logging.getLogger('asyncio').setLevel(logging.WARNING)

# Загружаем настройки из .env. `override=True` перезапишет системные переменные, если они есть.
load_dotenv(override=True)
reload_settings() # Перезагружаем настройки, чтобы учесть .env файл

async def main():
    script_logger.info("Запуск скрипта заполнения профилей...")
    try:
        # Опционально: инициализация БД, если это не делается автоматически при импорте сервисов
        # await setup_database() 
        
        # Вызов основной сервисной функции
        # Имя канала можно передать из настроек или как аргумент командной строки
        target_channel = settings.our_channel_id # Используем ID нашего основного канала
        if not target_channel:
            script_logger.critical("Целевой канал для заполнения профилей не указан в настройках (OUR_CHANNEL_ID).")
            return

        await process_all_channel_profiles_batch(channel_username=target_channel)
        
        script_logger.info("Скрипт заполнения профилей успешно завершил работу.")
        
    except Exception as e:
        script_logger.critical(f"КРИТИЧЕСКАЯ ОШИБКА в скрипте fill_profiles.py: {e}", exc_info=True)
    except KeyboardInterrupt:
        script_logger.info("\nСкрипт остановлен пользователем.")
    finally:
        script_logger.info("Завершение работы скрипта fill_profiles.")

if __name__ == "__main__":
    asyncio.run(main())