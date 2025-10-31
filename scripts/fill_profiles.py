#!/usr/bin/env python3
# Включаем отладочный режим
import os
import sys
import asyncio
import logging
import traceback
from pathlib import Path
from dotenv import load_dotenv
from tqdm import tqdm
from tqdm.asyncio import tqdm_asyncio
import functools
from relove_bot.db.session import get_session
from relove_bot.db.repository import UserRepository
from relove_bot.services.profile_service import ProfileService
from relove_bot.utils.fill_profiles import fill_all_profiles

# Настройка логирования до импорта других модулей
log_file = Path('fill_profiles_debug.log')
try:
    log_file.unlink(missing_ok=True)  # Удаляем старый лог-файл, если он существует
except Exception as e:
    print(f"Не удалось удалить старый лог-файл: {e}")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('fill_profiles_debug.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
logger.info('=' * 80)
logger.info('НАЧАЛО РАБОТЫ СКРИПТА fill_profiles.py')
logger.info('=' * 80)

# Отключаем предупреждения до импорта других библиотек
import warnings
warnings.filterwarnings('ignore', category=FutureWarning, module='transformers*')
warnings.filterwarnings('ignore', category=UserWarning, module='transformers*')

# Добавляем корень проекта в PYTHONPATH для корректного импорта
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

logger.info(f"Python path: {sys.path}")
logger.info(f"Текущая директория: {os.getcwd()}")
logger.info(f"Файл скрипта: {__file__}")
logger.info(f"Абсолютный путь к скрипту: {os.path.abspath(__file__)}")

# Проверяем доступность файлов и директорий
try:
    logger.info(f"Проверка доступа к лог-файлу: {log_file.absolute()}")
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write("Тест записи в лог-файл\n")
    logger.info("Успешная запись в лог-файл")
except Exception as e:
    logger.error(f"Ошибка при записи в лог-файл: {e}")
    logger.error(f"Текущие права доступа: {os.access('.', os.W_OK)}")

# Импортируем наши модули
try:
    logger.info("Импортируем настройки...")
    from relove_bot.config import settings, reload_settings
    from relove_bot.utils.fill_profiles import fill_all_profiles
    from relove_bot.db.database import setup_database
    logger.info("Все модули успешно импортированы")
except ImportError as e:
    logger.critical(f"Ошибка импорта модулей: {e}")
    logger.critical(f"sys.path: {sys.path}")
    raise

# Отключаем детальное логирование для других модулей на уровне этого скрипта,
# чтобы не дублировать логи сервисов, если они настроены иначе.
# Логирование relove_bot будет управляться его собственными настройками.
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy').setLevel(logging.WARNING)
logging.getLogger('aiosqlite').setLevel(logging.WARNING)
logging.getLogger('asyncio').setLevel(logging.WARNING)

# Устанавливаем уровень логирования для Telethon
logging.getLogger('telethon').setLevel(logging.WARNING)

# Загружаем настройки из .env. `override=True` перезапишет системные переменные, если они есть.
load_dotenv(override=True)
reload_settings() # Перезагружаем настройки, чтобы учесть .env файл

async def main():
    logger.info("1. Начало выполнения функции main()")
    try:
        logger.info("2. Проверка настроек...")
        logger.info(f"  - DB_URL: {'установлен' if settings.db_url else 'не установлен'}")
        logger.info(f"  - BOT_TOKEN: {'установлен' if settings.bot_token else 'не установлен'}")
        logger.info(f"  - OUR_CHANNEL_ID: {settings.our_channel_id}")
        
        logger.info("3. Инициализация базы данных...")
        db_initialized = await setup_database()
        if not db_initialized:
            logger.error("Ошибка инициализации базы данных")
            return
        
        logger.info("4. Запуск скрипта заполнения профилей...")
        await fill_all_profiles()
        
        logger.info("Скрипт заполнения профилей успешно завершил работу.")
        
    except Exception as e:
        logger.critical(f"КРИТИЧЕСКАЯ ОШИБКА в скрипте fill_profiles.py: {e}", exc_info=True)
    except KeyboardInterrupt:
        logger.info("\nСкрипт остановлен пользователем.")
    finally:
        logger.info("Завершение работы скрипта fill_profiles.")

if __name__ == "__main__":
    asyncio.run(main())