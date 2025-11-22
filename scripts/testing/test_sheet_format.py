#!/usr/bin/env python3
"""
Тестовый скрипт для проверки создания листа с точным форматированием.
"""
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))

# Загружаем переменные окружения
load_dotenv()

from relove_bot.services.google_sheets_service import GoogleSheetsService

# ID таблицы и листа
SPREADSHEET_ID = "1X5oX4zVlstaaqqcUkW2cMvxlGTV1vIHKLR2WSKr1O3c"
SOURCE_SHEET_NAME = "ritual_meditations"
TEST_SHEET_NAME = "TEST_Кинкаку-дзи"

def test_sheet_creation():
    """Тестирует создание листа с дублированием форматирования."""
    try:
        print("🧪 Инициализирую Google Sheets сервис...")
        # Проверяем наличие файла учётных данных
        creds_path = os.getenv('GOOGLE_CREDENTIALS_PATH', 'credentials/google_service_account.json')
        if not os.path.exists(creds_path):
            print(f"⚠️  Файл учётных данных не найден: {creds_path}")
            print(f"📝 Создаю папку credentials...")
            os.makedirs('credentials', exist_ok=True)
            print(f"⚠️  Пожалуйста, скопируй файл google_service_account.json в папку credentials/")
            print(f"   Затем запусти тест снова.")
            return False
        
        sheets_service = GoogleSheetsService()
        
        print(f"📋 Получаю ID исходного листа '{SOURCE_SHEET_NAME}'...")
        source_sheet_id = sheets_service.get_sheet_id(SPREADSHEET_ID, SOURCE_SHEET_NAME)
        if source_sheet_id is None:
            print(f"❌ Лист '{SOURCE_SHEET_NAME}' не найден")
            return False
        print(f"✓ ID исходного листа: {source_sheet_id}")
        
        print(f"\n📄 Дублирую лист как '{TEST_SHEET_NAME}'...")
        new_sheet_id = sheets_service.duplicate_sheet(SPREADSHEET_ID, source_sheet_id, TEST_SHEET_NAME)
        if new_sheet_id is None:
            print(f"❌ Ошибка при дублировании листа")
            return False
        print(f"✓ Новый лист создан с ID: {new_sheet_id}")
        
        print(f"\n📝 Подготавливаю тестовые данные...")
        test_rows = [
            ['Дата', 'Название ритуала', 'ФИО', 'Стадия пути героя', 'Разделение', 'Анализ'],
            ['15.11.2025', 'Кинкаку-дзи', 'Тестовый участник 1', 'Трансформация', 'Тестовое разделение 1', 'Тестовый анализ 1'],
            ['15.11.2025', 'Кинкаку-дзи', 'Тестовый участник 2', 'Зов к приключению', 'Тестовое разделение 2', 'Тестовый анализ 2'],
            ['15.11.2025', 'Кинкаку-дзи', 'Тестовый участник 3', 'Преодоление порога', 'Тестовое разделение 3', 'Тестовый анализ 3'],
        ]
        
        print(f"📤 Загружаю данные на новый лист...")
        if not sheets_service.update_rows_preserve_format(SPREADSHEET_ID, TEST_SHEET_NAME, test_rows):
            print(f"❌ Ошибка при загрузке данных")
            return False
        print(f"✓ Данные загружены ({len(test_rows)} строк)")
        
        print(f"\n🎨 Применяю пастельные цвета (индекс 0 - лавандовый)...")
        if not sheets_service.apply_pastel_colors(SPREADSHEET_ID, TEST_SHEET_NAME, len(test_rows), color_index=0):
            print(f"❌ Ошибка при применении цветов")
            return False
        print(f"✓ Цвета применены")
        
        print(f"\n✅ Тест успешно завершен!")
        print(f"📊 Проверь лист '{TEST_SHEET_NAME}' в Google Sheets:")
        print(f"   - Структура должна совпадать с '{SOURCE_SHEET_NAME}'")
        print(f"   - Заголовок: глубокий фиолетовый с белым текстом")
        print(f"   - Данные: лавандовый фон")
        print(f"   - Высота строк: 50px (заголовок), 200px (данные)")
        print(f"   - Перенос текста: включен")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_sheet_creation()
    sys.exit(0 if success else 1)
