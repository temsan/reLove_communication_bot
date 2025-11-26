#!/usr/bin/env python3
"""
Загрузка датасета и запуск fine-tuning модели Наташи через Google Generative AI API.

Документация: https://ai.google.dev/docs

Google Generative AI поддерживает fine-tuning через Vertex AI.

Задачи:
1. Валидация JSONL файла
2. Загрузка файла в Google Cloud Storage
3. Создание fine-tuning job через Vertex AI
4. Мониторинг прогресса
5. Тестирование fine-tuned модели
"""
import asyncio
import json
import sys
from pathlib import Path
from typing import Optional
import os

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import google.generativeai as genai
from dotenv import load_dotenv
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/finetune_google.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Загружаем переменные окружения
load_dotenv()


class GoogleFineTuner:
    """Класс для fine-tuning модели Наташи на Google Generative AI."""
    
    def __init__(self):
        api_key = os.getenv('GOOGLE_API_KEY')
        if not api_key:
            raise ValueError("GOOGLE_API_KEY не установлен в .env")
        
        # Инициализируем Google Generative AI
        genai.configure(api_key=api_key)
        self.api_key = api_key
        self.uploaded_file_id = None
        self.job_id = None
        self.model_id = None
    
    def validate_jsonl(self, file_path: str) -> bool:
        """Валидирует JSONL файл."""
        logger.info(f"Validating JSONL file: {file_path}")
        
        if not Path(file_path).exists():
            logger.error(f"File not found: {file_path}")
            return False
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                line_count = 0
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        data = json.loads(line)
                        
                        # Проверяем структуру
                        if 'messages' not in data:
                            logger.error(f"Line {line_count + 1}: Missing 'messages' field")
                            return False
                        
                        messages = data['messages']
                        if not isinstance(messages, list) or len(messages) < 2:
                            logger.error(f"Line {line_count + 1}: 'messages' must be a list with at least 2 items")
                            return False
                        
                        # Проверяем роли
                        roles = [msg.get('role') for msg in messages]
                        if 'user' not in roles or 'assistant' not in roles:
                            logger.error(f"Line {line_count + 1}: Must have 'user' and 'assistant' roles")
                            return False
                        
                        line_count += 1
                    
                    except json.JSONDecodeError as e:
                        logger.error(f"Line {line_count + 1}: Invalid JSON - {e}")
                        return False
            
            logger.info(f"✅ Validation passed: {line_count} training examples")
            return True
        
        except Exception as e:
            logger.error(f"Validation error: {e}")
            return False
    
    def upload_file(self, file_path: str) -> Optional[str]:
        """Загружает файл в Google Generative AI."""
        logger.info(f"Uploading file to Google Generative AI: {file_path}")
        
        try:
            file_size = Path(file_path).stat().st_size
            
            # Загружаем файл с указанием MIME type
            response = genai.upload_file(
                path=file_path,
                display_name=Path(file_path).name,
                mime_type='application/json'
            )
            
            self.uploaded_file_id = response.name
            logger.info(f"✅ File uploaded successfully to Google")
            logger.info(f"   File ID: {self.uploaded_file_id}")
            logger.info(f"   Size: {file_size} bytes ({file_size/1024:.2f} KB)")
            logger.info(f"   Display name: {response.display_name}")
            
            return self.uploaded_file_id
        
        except Exception as e:
            logger.error(f"Upload error: {e}")
            return None
    
    def test_model(self, test_prompts: list = None) -> dict:
        """Тестирует модель через Google Generative AI."""
        logger.info(f"\n{'='*70}")
        logger.info("TESTING GOOGLE GENERATIVE AI MODEL")
        logger.info(f"{'='*70}\n")
        
        if not test_prompts:
            test_prompts = [
                "Я чувствую себя потерянным в жизни",
                "Как начать свой бизнес?",
                "Я вспомнил свою прошлую жизнь",
                "Как улучшить отношения с партнером?",
                "Что такое путь героя?"
            ]
        
        results = []
        
        try:
            model = genai.GenerativeModel('gemini-2.5-flash')
            
            for i, prompt in enumerate(test_prompts, 1):
                logger.info(f"Test {i}: {prompt}")
                
                try:
                    response = model.generate_content(
                        prompt,
                        generation_config=genai.types.GenerationConfig(
                            max_output_tokens=500,
                            temperature=0.7
                        )
                    )
                    
                    answer = response.text
                    
                    logger.info(f"Response: {answer[:200]}...")
                    logger.info(f"Tokens used: ~{len(answer.split())}\n")
                    
                    results.append({
                        'prompt': prompt,
                        'response': answer,
                        'tokens': len(answer.split())
                    })
                
                except Exception as e:
                    logger.error(f"Error: {e}\n")
                    results.append({
                        'prompt': prompt,
                        'response': f"Error: {e}",
                        'tokens': 0
                    })
        
        except Exception as e:
            logger.error(f"Model error: {e}")
        
        return results
    
    def save_config(self, output_path: str = "data/google_finetune_config.json"):
        """Сохраняет конфигурацию fine-tuning."""
        config = {
            'provider': 'google',
            'api_base': 'https://generativelanguage.googleapis.com',
            'uploaded_file_id': self.uploaded_file_id,
            'job_id': self.job_id,
            'model_id': self.model_id,
            'timestamp': str(Path(output_path).parent / 'timestamp.txt')
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        logger.info(f"\n✅ Configuration saved to: {output_path}")
        return output_path


async def main():
    """Главная функция."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Upload dataset and test with Google Generative AI"
    )
    parser.add_argument(
        '--file',
        type=str,
        default='data/natasha_finetuning_20251125_153356.jsonl',
        help='Path to JSONL training file'
    )
    parser.add_argument(
        '--validate-only',
        action='store_true',
        help='Only validate the file, do not upload'
    )
    parser.add_argument(
        '--upload-only',
        action='store_true',
        help='Only upload the file'
    )
    parser.add_argument(
        '--test',
        action='store_true',
        help='Test the model'
    )
    
    args = parser.parse_args()
    
    print("\n" + "="*70)
    print("NATASHA FINE-TUNING UPLOADER (GOOGLE)")
    print("="*70 + "\n")
    
    try:
        tuner = GoogleFineTuner()
    except ValueError as e:
        logger.error(f"❌ {e}")
        logger.error("Please set GOOGLE_API_KEY in .env file")
        return
    
    try:
        # Валидация файла
        if not tuner.validate_jsonl(args.file):
            logger.error("❌ Validation failed!")
            return
        
        if args.validate_only:
            logger.info("✅ Validation passed. Exiting.")
            return
        
        # Загрузка файла
        file_id = tuner.upload_file(args.file)
        if not file_id:
            logger.error("❌ Upload failed!")
            return
        
        if args.upload_only:
            logger.info(f"✅ File uploaded. File ID: {file_id}")
            return
        
        # Тестирование модели
        if args.test:
            logger.info("🧪 Testing model...")
            results = tuner.test_model()
            
            # Сохраняем результаты
            test_results_file = f"data/google_test_results.json"
            with open(test_results_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            logger.info(f"✅ Test results saved to: {test_results_file}")
        
        # Сохраняем конфигурацию
        tuner.save_config()
        
        logger.info(f"\n{'='*70}")
        logger.info("SUMMARY")
        logger.info(f"{'='*70}")
        logger.info(f"✅ File uploaded: {file_id}")
        logger.info(f"📝 Note: Google Generative AI doesn't support fine-tuning yet")
        logger.info(f"   Use Vertex AI for fine-tuning capabilities")
        logger.info(f"{'='*70}\n")
    
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())
