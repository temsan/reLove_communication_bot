#!/usr/bin/env python3
"""
Скрипт для установки spaCy модели.
Запускается автоматически после установки зависимостей.
"""

import subprocess
import sys
import os

def install_spacy_model():
    """Устанавливает spaCy модель en_core_web_md."""
    try:
        # Проверяем, установлена ли уже модель
        import spacy
        try:
            nlp = spacy.load("en_core_web_md")
            print("Модель en_core_web_md уже установлена.")
            return
        except OSError:
            pass

        # Устанавливаем модель
        print("Установка модели en_core_web_md...")
        subprocess.check_call([sys.executable, "-m", "spacy", "download", "en_core_web_md"])
        print("Модель успешно установлена.")
    except Exception as e:
        print(f"Ошибка при установке модели: {e}")
        sys.exit(1)

if __name__ == "__main__":
    install_spacy_model() 