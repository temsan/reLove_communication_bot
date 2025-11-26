#!/usr/bin/env python3
"""
Список доступных моделей Google Generative AI.
"""
import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

api_key = os.getenv('GOOGLE_API_KEY')
if not api_key:
    print("❌ GOOGLE_API_KEY не установлен")
    exit(1)

genai.configure(api_key=api_key)

print("🧪 Доступные модели Google Generative AI:\n")

try:
    for model in genai.list_models():
        print(f"Model: {model.name}")
        print(f"  Display name: {model.display_name}")
        print(f"  Description: {model.description}")
        print(f"  Input token limit: {model.input_token_limit}")
        print(f"  Output token limit: {model.output_token_limit}")
        print(f"  Supported methods: {model.supported_generation_methods}")
        print()
except Exception as e:
    print(f"❌ Ошибка: {e}")
