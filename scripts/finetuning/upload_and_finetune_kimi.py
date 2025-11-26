#!/usr/bin/env python3
"""
Загрузка датасета и запуск fine-tuning модели Наташи через Kimi (Moonshot AI) API.

Документация: https://platform.moonshot.ai/docs/guide/migrating-from-openai-to-kimi

Kimi имеет совместимость с OpenAI API, поэтому можно использовать OpenAI SDK
с изменением base_url и API ключа.

Задачи:
1. Валидация JSONL файла
2. Загрузка файла в Kimi
3. Создание fine-tuning job
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

from openai import OpenAI
from dotenv import load_dotenv
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/finetune_kimi.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Загружаем переменные окружения
load_dotenv()

# Kimi API endpoint
KIMI_API_BASE = "https://api.moonshot.cn/v1"


class KimiFineTuner:
    """Класс для fine-tuning модели Наташи на Kimi."""
    
    def __init__(self):
        api_key = os.getenv('KIMI_API_KEY')
        if not api_key:
            raise ValueError("KIMI_API_KEY не установлен в .env")
        
        # Используем OpenAI SDK с Kimi endpoint
        self.client = OpenAI(
            api_key=api_key,
            base_url=KIMI_API_BASE
        )
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
        """Загружает файл в Kimi."""
        logger.info(f"Uploading file to Kimi: {file_path}")
        
        try:
            with open(file_path, 'rb') as f:
                response = self.client.files.create(
                    file=f,
                    purpose='fine-tune'
                )
            
            self.uploaded_file_id = response.id
            logger.info(f"✅ File uploaded successfully to Kimi")
            logger.info(f"   File ID: {self.uploaded_file_id}")
            logger.info(f"   Size: {response.size} bytes")
            logger.info(f"   Created: {response.created_at}")
            
            return self.uploaded_file_id
        
        except Exception as e:
            logger.error(f"Upload error: {e}")
            return None
    
    def create_fine_tuning_job(
        self,
        file_id: str,
        model: str = "moonshot-v1-8k",
        n_epochs: int = 3,
        learning_rate_multiplier: float = 0.1,
        batch_size: Optional[int] = None,
        suffix: str = "natasha-v1"
    ) -> Optional[str]:
        """Создает fine-tuning job в Kimi."""
        logger.info(f"\nCreating fine-tuning job in Kimi...")
        logger.info(f"  Model: {model}")
        logger.info(f"  Epochs: {n_epochs}")
        logger.info(f"  Learning rate multiplier: {learning_rate_multiplier}")
        logger.info(f"  Suffix: {suffix}")
        
        try:
            params = {
                'training_file': file_id,
                'model': model,
                'hyperparameters': {
                    'n_epochs': n_epochs,
                    'learning_rate_multiplier': learning_rate_multiplier
                },
                'suffix': suffix
            }
            
            if batch_size:
                params['hyperparameters']['batch_size'] = batch_size
            
            response = self.client.fine_tuning.jobs.create(**params)
            
            self.job_id = response.id
            logger.info(f"✅ Fine-tuning job created successfully in Kimi")
            logger.info(f"   Job ID: {self.job_id}")
            logger.info(f"   Status: {response.status}")
            logger.info(f"   Created: {response.created_at}")
            
            return self.job_id
        
        except Exception as e:
            logger.error(f"Job creation error: {e}")
            return None
    
    def get_job_status(self, job_id: str) -> dict:
        """Получает статус fine-tuning job."""
        try:
            response = self.client.fine_tuning.jobs.retrieve(job_id)
            
            status_info = {
                'id': response.id,
                'status': response.status,
                'model': response.model,
                'created_at': response.created_at,
                'updated_at': response.updated_at,
                'fine_tuned_model': response.fine_tuned_model,
                'organization_id': getattr(response, 'organization_id', None),
                'result_files': getattr(response, 'result_files', []),
                'training_file': response.training_file,
                'validation_file': getattr(response, 'validation_file', None),
                'error': getattr(response, 'error', None)
            }
            
            return status_info
        
        except Exception as e:
            logger.error(f"Error getting job status: {e}")
            return {}
    
    def monitor_job(self, job_id: str, check_interval: int = 30, max_checks: int = 1000):
        """Мониторит прогресс fine-tuning job."""
        logger.info(f"\n{'='*70}")
        logger.info("MONITORING KIMI FINE-TUNING JOB")
        logger.info(f"{'='*70}")
        logger.info(f"Job ID: {job_id}")
        logger.info(f"Check interval: {check_interval} seconds")
        logger.info(f"Max checks: {max_checks}")
        logger.info(f"{'='*70}\n")
        
        check_count = 0
        
        while check_count < max_checks:
            status_info = self.get_job_status(job_id)
            
            if not status_info:
                logger.error("Failed to get job status")
                return False
            
            status = status_info.get('status')
            
            logger.info(f"[Check {check_count + 1}] Status: {status}")
            
            if status == 'succeeded':
                logger.info(f"\n✅ Fine-tuning completed successfully!")
                logger.info(f"   Fine-tuned model: {status_info.get('fine_tuned_model')}")
                self.model_id = status_info.get('fine_tuned_model')
                return True
            
            elif status == 'failed':
                logger.error(f"\n❌ Fine-tuning failed!")
                error = status_info.get('error')
                if error:
                    logger.error(f"   Error: {error}")
                return False
            
            elif status == 'cancelled':
                logger.warning(f"\n⚠️  Fine-tuning was cancelled")
                return False
            
            check_count += 1
            
            if check_count < max_checks:
                logger.info(f"   Waiting {check_interval} seconds before next check...")
                import time
                time.sleep(check_interval)
        
        logger.warning(f"\n⚠️  Max checks reached. Job may still be running.")
        logger.info(f"   Check status manually with job ID: {job_id}")
        return False
    
    def test_model(self, model_id: str, test_prompts: list = None) -> dict:
        """Тестирует fine-tuned модель."""
        logger.info(f"\n{'='*70}")
        logger.info("TESTING KIMI FINE-TUNED MODEL")
        logger.info(f"{'='*70}")
        logger.info(f"Model: {model_id}\n")
        
        if not test_prompts:
            test_prompts = [
                "Я чувствую себя потерянным в жизни",
                "Как начать свой бизнес?",
                "Я вспомнил свою прошлую жизнь",
                "Как улучшить отношения с партнером?",
                "Что такое путь героя?"
            ]
        
        results = []
        
        for i, prompt in enumerate(test_prompts, 1):
            logger.info(f"Test {i}: {prompt}")
            
            try:
                response = self.client.chat.completions.create(
                    model=model_id,
                    messages=[
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=500,
                    temperature=0.7
                )
                
                answer = response.choices[0].message.content
                
                logger.info(f"Response: {answer[:200]}...")
                logger.info(f"Tokens used: {response.usage.total_tokens}\n")
                
                results.append({
                    'prompt': prompt,
                    'response': answer,
                    'tokens': response.usage.total_tokens
                })
            
            except Exception as e:
                logger.error(f"Error: {e}\n")
                results.append({
                    'prompt': prompt,
                    'response': f"Error: {e}",
                    'tokens': 0
                })
        
        return results
    
    def list_jobs(self, limit: int = 10) -> list:
        """Список всех fine-tuning jobs."""
        logger.info(f"\nListing last {limit} fine-tuning jobs in Kimi...")
        
        try:
            response = self.client.fine_tuning.jobs.list(limit=limit)
            
            jobs = []
            for job in response.data:
                jobs.append({
                    'id': job.id,
                    'status': job.status,
                    'model': job.model,
                    'fine_tuned_model': job.fine_tuned_model,
                    'created_at': job.created_at,
                    'updated_at': job.updated_at
                })
            
            logger.info(f"\nFound {len(jobs)} jobs:")
            for job in jobs:
                logger.info(f"  {job['id']}: {job['status']} ({job['model']})")
                if job['fine_tuned_model']:
                    logger.info(f"    → {job['fine_tuned_model']}")
            
            return jobs
        
        except Exception as e:
            logger.error(f"Error listing jobs: {e}")
            return []
    
    def save_config(self, output_path: str = "data/kimi_finetune_config.json"):
        """Сохраняет конфигурацию fine-tuning."""
        config = {
            'provider': 'kimi',
            'api_base': KIMI_API_BASE,
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
        description="Upload dataset and run fine-tuning for Natasha model on Kimi"
    )
    parser.add_argument(
        '--file',
        type=str,
        default='data/natasha_finetuning_20251125_153356.jsonl',
        help='Path to JSONL training file'
    )
    parser.add_argument(
        '--model',
        type=str,
        default='moonshot-v1-8k',
        help='Base model for fine-tuning (default: moonshot-v1-8k)'
    )
    parser.add_argument(
        '--epochs',
        type=int,
        default=3,
        help='Number of training epochs (default: 3)'
    )
    parser.add_argument(
        '--learning-rate',
        type=float,
        default=0.1,
        help='Learning rate multiplier (default: 0.1)'
    )
    parser.add_argument(
        '--suffix',
        type=str,
        default='natasha-v1',
        help='Model suffix (default: natasha-v1)'
    )
    parser.add_argument(
        '--validate-only',
        action='store_true',
        help='Only validate the file, do not upload or train'
    )
    parser.add_argument(
        '--upload-only',
        action='store_true',
        help='Only upload the file, do not start training'
    )
    parser.add_argument(
        '--monitor',
        type=str,
        help='Monitor existing job by ID'
    )
    parser.add_argument(
        '--test',
        type=str,
        help='Test fine-tuned model by ID'
    )
    parser.add_argument(
        '--list-jobs',
        action='store_true',
        help='List all fine-tuning jobs'
    )
    
    args = parser.parse_args()
    
    print("\n" + "="*70)
    print("NATASHA FINE-TUNING UPLOADER (KIMI)")
    print("="*70 + "\n")
    
    try:
        tuner = KimiFineTuner()
    except ValueError as e:
        logger.error(f"❌ {e}")
        logger.error("Please set KIMI_API_KEY in .env file")
        return
    
    try:
        # Список jobs
        if args.list_jobs:
            tuner.list_jobs()
            return
        
        # Мониторинг существующего job
        if args.monitor:
            logger.info(f"Monitoring job: {args.monitor}")
            tuner.monitor_job(args.monitor)
            return
        
        # Тестирование модели
        if args.test:
            logger.info(f"Testing model: {args.test}")
            results = tuner.test_model(args.test)
            
            # Сохраняем результаты
            test_results_file = f"data/kimi_test_results_{args.test}.json"
            with open(test_results_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            logger.info(f"✅ Test results saved to: {test_results_file}")
            return
        
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
        
        # Создание fine-tuning job
        job_id = tuner.create_fine_tuning_job(
            file_id=file_id,
            model=args.model,
            n_epochs=args.epochs,
            learning_rate_multiplier=args.learning_rate,
            suffix=args.suffix
        )
        
        if not job_id:
            logger.error("❌ Job creation failed!")
            return
        
        # Мониторинг job
        logger.info("\n⏳ Starting to monitor fine-tuning job...")
        logger.info("   (This may take several hours)")
        
        success = tuner.monitor_job(job_id, check_interval=60)
        
        if success:
            logger.info(f"\n✅ Fine-tuning completed!")
            logger.info(f"   Model ID: {tuner.model_id}")
            
            # Сохраняем конфигурацию
            tuner.save_config()
            
            # Тестируем модель
            logger.info("\n🧪 Testing fine-tuned model...")
            results = tuner.test_model(tuner.model_id)
            
            # Сохраняем результаты
            test_results_file = f"data/kimi_test_results_{tuner.model_id}.json"
            with open(test_results_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            logger.info(f"✅ Test results saved to: {test_results_file}")
        
        else:
            logger.warning(f"\n⚠️  Fine-tuning did not complete successfully")
            logger.info(f"   Job ID: {job_id}")
            logger.info(f"   Check status manually or use --monitor flag")
    
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())
