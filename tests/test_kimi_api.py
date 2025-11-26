#!/usr/bin/env python3
"""
Тест доступных операций в Kimi API.
"""
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

api_key = os.getenv('KIMI_API_KEY')
if not api_key:
    print("❌ KIMI_API_KEY не установлен")
    exit(1)

client = OpenAI(
    api_key=api_key,
    base_url="https://api.moonshot.cn/v1"
)

print("🧪 Тестирование Kimi API...\n")

# Тест 1: Проверка доступных моделей
print("1️⃣ Проверка доступных моделей:")
try:
    models = client.models.list()
    print(f"✅ Доступные модели:")
    for model in models.data[:5]:
        print(f"   - {model.id}")
except Exception as e:
    print(f"❌ Ошибка: {e}\n")

# Тест 2: Проверка файлов
print("\n2️⃣ Проверка операций с файлами:")
try:
    files = client.files.list()
    print(f"✅ Загруженные файлы: {len(files.data)}")
except Exception as e:
    print(f"❌ Ошибка: {e}\n")

# Тест 3: Проверка fine-tuning jobs
print("\n3️⃣ Проверка fine-tuning jobs:")
try:
    jobs = client.fine_tuning.jobs.list()
    print(f"✅ Fine-tuning jobs: {len(jobs.data)}")
except Exception as e:
    print(f"❌ Ошибка: {e}")
    print("   (Возможно, Kimi не поддерживает fine-tuning через OpenAI SDK)\n")

# Тест 4: Простой чат
print("\n4️⃣ Тест простого чата:")
try:
    response = client.chat.completions.create(
        model="moonshot-v1-8k",
        messages=[
            {"role": "user", "content": "Привет! Как дела?"}
        ],
        max_tokens=100
    )
    print(f"✅ Ответ: {response.choices[0].message.content[:100]}...")
except Exception as e:
    print(f"❌ Ошибка: {e}\n")

print("\n" + "="*70)
print("Тестирование завершено")
