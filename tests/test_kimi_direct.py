#!/usr/bin/env python3
"""
Тест Kimi API с прямыми HTTP запросами.
Основано на документации Moonshot AI.
"""
import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv('KIMI_API_KEY')
if not api_key:
    print("❌ KIMI_API_KEY не установлен")
    exit(1)

print("🧪 Тестирование Kimi API (прямые HTTP запросы)\n")

# Kimi API endpoints
BASE_URL = "https://api.moonshot.cn/v1"
HEADERS = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

# Тест 1: Проверка моделей
print("1️⃣ Проверка доступных моделей:")
try:
    response = requests.get(
        f"{BASE_URL}/models",
        headers=HEADERS,
        timeout=10
    )
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Доступные модели:")
        for model in data.get('data', [])[:5]:
            print(f"   - {model.get('id')}")
    else:
        print(f"❌ Ошибка: {response.text}")
except Exception as e:
    print(f"❌ Ошибка: {e}\n")

# Тест 2: Простой чат
print("\n2️⃣ Тест простого чата:")
try:
    response = requests.post(
        f"{BASE_URL}/chat/completions",
        headers=HEADERS,
        json={
            "model": "moonshot-v1-8k",
            "messages": [
                {"role": "user", "content": "Привет! Как дела?"}
            ],
            "temperature": 0.7,
            "max_tokens": 100
        },
        timeout=30
    )
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        answer = data['choices'][0]['message']['content']
        print(f"✅ Ответ: {answer[:100]}...")
    else:
        print(f"❌ Ошибка: {response.text}")
except Exception as e:
    print(f"❌ Ошибка: {e}\n")

# Тест 3: Загрузка файла
print("\n3️⃣ Тест загрузки файла:")
try:
    # Создаем тестовый файл
    test_file = "test_upload.jsonl"
    with open(test_file, 'w') as f:
        f.write('{"messages": [{"role": "user", "content": "test"}, {"role": "assistant", "content": "test"}]}\n')
    
    with open(test_file, 'rb') as f:
        files = {'file': (test_file, f, 'application/jsonl')}
        data = {'purpose': 'fine-tune'}
        
        response = requests.post(
            f"{BASE_URL}/files",
            headers={"Authorization": f"Bearer {api_key}"},  # Без Content-Type для multipart
            files=files,
            data=data,
            timeout=30
        )
    
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        file_data = response.json()
        print(f"✅ Файл загружен: {file_data.get('id')}")
    else:
        print(f"❌ Ошибка: {response.text}")
    
    # Удаляем тестовый файл
    os.remove(test_file)
except Exception as e:
    print(f"❌ Ошибка: {e}\n")

# Тест 4: Проверка fine-tuning
print("\n4️⃣ Проверка fine-tuning:")
try:
    response = requests.get(
        f"{BASE_URL}/fine_tuning/jobs",
        headers=HEADERS,
        timeout=10
    )
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Fine-tuning jobs: {len(data.get('data', []))}")
    elif response.status_code == 404:
        print(f"⚠️  Fine-tuning endpoint не найден (404)")
        print(f"   Возможно, Kimi не поддерживает fine-tuning")
    else:
        print(f"❌ Ошибка: {response.text}")
except Exception as e:
    print(f"❌ Ошибка: {e}\n")

print("\n" + "="*70)
print("Тестирование завершено")
