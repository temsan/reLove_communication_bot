#!/usr/bin/env python3
import os
from dotenv import load_dotenv

load_dotenv()

key = os.getenv('KIMI_API_KEY')
print(f"KIMI_API_KEY: {key}")
print(f"Длина: {len(key) if key else 0}")

# Проверяем, может ли это быть ключ для другого сервиса
if key:
    if key.startswith('sk-'):
        print("✓ Начинается с 'sk-' (OpenAI формат)")
    if 'ENhKl' in key:
        print("✓ Содержит 'ENhKl' (похоже на Kimi ключ)")
    
    # Проверяем длину
    if len(key) == 51:
        print("✓ Длина 51 символ (типично для Kimi)")
