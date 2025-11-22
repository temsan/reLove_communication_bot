#!/usr/bin/env python3
"""
Скрипт для генерации документации.
Создает HTML документацию из docstrings и markdown файлов.
"""

import os
import sys
import subprocess
from pathlib import Path

def build_docs():
    """Генерирует документацию."""
    try:
        # Проверяем наличие директории docs
        if not Path("docs").exists():
            print("Ошибка: директория docs не найдена.")
            sys.exit(1)

        # Генерируем документацию
        print("Генерация документации...")
        subprocess.check_call([
            sys.executable, "-m", "sphinx",
            "-b", "html",
            "docs/",
            "docs/_build/html"
        ])
        print("Документация успешно сгенерирована.")

    except subprocess.CalledProcessError as e:
        print(f"Ошибка при генерации документации: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Неожиданная ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    build_docs() 