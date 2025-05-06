#!/usr/bin/env python3
import os
import sys
import asyncio
import logging
from tqdm import tqdm
from dotenv import load_dotenv

# Добавляем корень проекта в PYTHONPATH для корректного импорта
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from relove_bot.utils.custom_logging import setup_logging
from relove_bot.config import settings, reload_settings
from relove_bot.utils.fill_profiles import fill_all_profiles

# Настройка логирования - уменьшаем уровень логирования для tqdm
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)  # Устанавливаем уровень логирования на ERROR

load_dotenv(override=True)
reload_settings()

class TqdmLoggingHandler(logging.Handler):
    def emit(self, record):
        # Пропускаем все сообщения кроме ошибок
        if record.levelno >= logging.ERROR:
            tqdm.write(self.format(record))

# Настраиваем обработчик для логирования
tqdm_handler = TqdmLoggingHandler()
tqdm_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(tqdm_handler)

async def main():
    try:
        print("Начало обработки профилей пользователей...")
        batch_size = 200
        
        with tqdm(total=None, desc="Обработка пользователей", unit="пользователей") as pbar:
            # Запускаем процесс обновления профилей
            processed_count = await fill_all_profiles(
                channel_id_or_username=settings.our_channel_id,
                batch_size=batch_size,
                progress_callback=lambda: pbar.update(1)
            )
        
        print(f"\nОбработка завершена. Всего обработано пользователей: {processed_count}")
        
    except Exception as e:
        logger.error(f"Ошибка при выполнении скрипта: {e}", exc_info=True)
        return 1
    return 0

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("Скрипт остановлен пользователем")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
        sys.exit(1)