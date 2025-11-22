"""
Тестовый скрипт для проверки подключения к LLM.
Проверяет текущую модель и при необходимости переключается на Grok.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from relove_bot.config import settings
from relove_bot.rag.llm import LLM
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_current_model():
    """Тестирует текущую модель"""
    print("="*60)
    print("LLM Connection Test")
    print("="*60)
    print(f"\n📋 Current settings:")
    print(f"   Model: {settings.model_name}")
    print(f"   API Base: {settings.llm_api_base}")
    print(f"   API Key: {settings.llm_api_key.get_secret_value()[:10]}...")
    
    print(f"\n🔄 Testing connection...")
    
    try:
        llm = LLM()
        
        # Простой тест
        test_prompt = "Привет! Ответь одним словом: работаешь?"
        
        print(f"\n📤 Sending test prompt: '{test_prompt}'")
        
        response = await llm.generate_rag_answer(
            context="",
            question=test_prompt
        )
        
        print(f"\n✅ SUCCESS!")
        print(f"📥 Response: {response}")
        print(f"\n✅ Model {settings.model_name} is working!")
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR!")
        print(f"   Error: {e}")
        print(f"\n❌ Model {settings.model_name} is NOT working!")
        
        return False


async def test_grok_model():
    """Тестирует Grok модель"""
    print("\n" + "="*60)
    print("Testing Grok Model")
    print("="*60)
    
    # Временно меняем настройки
    original_model = settings.model_name
    settings.model_name = "x-ai/grok-beta"
    
    print(f"\n📋 Grok settings:")
    print(f"   Model: {settings.model_name}")
    print(f"   API Base: {settings.llm_api_base}")
    
    try:
        llm = LLM()
        
        test_prompt = "Привет! Ответь одним словом: работаешь?"
        
        print(f"\n📤 Sending test prompt: '{test_prompt}'")
        
        response = await llm.generate_rag_answer(
            context="",
            question=test_prompt
        )
        
        print(f"\n✅ SUCCESS!")
        print(f"📥 Response: {response}")
        print(f"\n✅ Grok model is working!")
        
        # Восстанавливаем настройки
        settings.model_name = original_model
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR!")
        print(f"   Error: {e}")
        print(f"\n❌ Grok model is NOT working!")
        
        # Восстанавливаем настройки
        settings.model_name = original_model
        
        return False


async def main():
    """Главная функция"""
    
    # Тестируем текущую модель
    current_works = await test_current_model()
    
    if current_works:
        print("\n" + "="*60)
        print("✅ Current model is working fine!")
        print("="*60)
        return
    
    # Если не работает, тестируем Grok
    print("\n⚠️ Current model failed. Testing Grok...")
    
    grok_works = await test_grok_model()
    
    if grok_works:
        print("\n" + "="*60)
        print("💡 RECOMMENDATION")
        print("="*60)
        print("\nUpdate your .env file:")
        print("\n# Change this line:")
        print(f"MODEL_NAME={settings.model_name}")
        print("\n# To this:")
        print("MODEL_NAME=x-ai/grok-beta")
        print("\nOr use the free version:")
        print("MODEL_NAME=x-ai/grok-4.1-fast:free")
        print("="*60)
    else:
        print("\n" + "="*60)
        print("❌ Both models failed!")
        print("="*60)
        print("\nPossible issues:")
        print("1. Check your API key")
        print("2. Check internet connection")
        print("3. Check API base URL")
        print("4. Try different model")


if __name__ == "__main__":
    asyncio.run(main())
