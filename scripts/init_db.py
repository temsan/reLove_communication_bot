#!/usr/bin/env python3
"""
Скрипт для инициализации базы данных.
Создает базу данных и применяет миграции.
"""

import os
import sys
import subprocess
from pathlib import Path

def init_database():
    """Инициализирует базу данных."""
    try:
        # Проверяем наличие .env файла
        if not Path(".env").exists():
            print("Ошибка: файл .env не найден.")
            print("Создайте файл .env с настройками базы данных.")
            sys.exit(1)

        # Применяем миграции
        print("Применение миграций...")
        subprocess.check_call([sys.executable, "-m", "alembic", "upgrade", "head"])
        print("Миграции успешно применены.")

    except subprocess.CalledProcessError as e:
        print(f"Ошибка при применении миграций: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Неожиданная ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    init_database() 