#!/usr/bin/env python3
import os
from dotenv import load_dotenv

load_dotenv()

key = os.getenv('KIMI_API_KEY')
print(f"KIMI_API_KEY установлен: {bool(key)}")
if key:
    print(f"Первые 10 символов: {key[:10]}...")
    print(f"Длина ключа: {len(key)}")
    print(f"Начинается с 'sk-': {key.startswith('sk-')}")
else:
    print("KIMI_API_KEY не найден в .env")
