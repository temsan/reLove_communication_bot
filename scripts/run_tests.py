#!/usr/bin/env python3
"""
Скрипт для запуска тестов.
Запускает все тесты с покрытием кода.
"""

import os
import sys
import subprocess
from pathlib import Path

def run_tests():
    """Запускает тесты."""
    try:
        # Проверяем наличие тестов
        if not Path("tests").exists():
            print("Ошибка: директория tests не найдена.")
            sys.exit(1)

        # Запускаем тесты с покрытием
        print("Запуск тестов...")
        subprocess.check_call([
            sys.executable, "-m", "pytest",
            "--cov=relove_bot",
            "--cov-report=term-missing",
            "--cov-report=html",
            "tests/"
        ])
        print("Тесты успешно завершены.")

    except subprocess.CalledProcessError as e:
        print(f"Ошибка при запуске тестов: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Неожиданная ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_tests() 