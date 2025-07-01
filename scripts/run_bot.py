#!/usr/bin/env python3
"""
Скрипт для запуска бота.
Проверяет наличие необходимых файлов и запускает бота.
"""

import os
import sys
import subprocess
from pathlib import Path

def run_bot():
    """Запускает бота."""
    try:
        # Проверяем наличие .env файла
        if not Path(".env").exists():
            print("Ошибка: файл .env не найден.")
            print("Создайте файл .env с настройками бота.")
            sys.exit(1)

        # Проверяем наличие базы данных
        if not Path("alembic/versions").exists():
            print("Ошибка: директория с миграциями не найдена.")
            print("Запустите скрипт инициализации базы данных: python scripts/init_db.py")
            sys.exit(1)

        # Запускаем бота
        print("Запуск бота...")
        subprocess.check_call([sys.executable, "-m", "relove_bot.bot"])

    except subprocess.CalledProcessError as e:
        print(f"Ошибка при запуске бота: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Неожиданная ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_bot() 