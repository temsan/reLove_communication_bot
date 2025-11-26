#!/usr/bin/env python3
"""
Загрузка датасета и запуск fine-tuning модели Наташи через Google Vertex AI.

Документация: https://cloud.google.com/vertex-ai/docs/generative-ai/models/gemini-supervised-tuning

Vertex AI поддерживает supervised fine-tuning для Gemini моделей.

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

from google.cloud import aiplatform
from google.cloud import storage
from dotenv import load_dotenv
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/finetune_vertex.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Загружаем переменные окружения
load_dotenv()


class VertexAIFineTuner:
    """Класс для fine-tuning модели Наташи на Google Vertex AI."""
    
    def __init__(self, project_id: str, location: str = "us-central1"):
        """
        Инициализирует Vertex AI fine-tuner.
        
        Args:
            project_id: Google Cloud Project ID
            location: Регион для Vertex AI (default: us-central1)
        """
        self.project_id = project_id
        self.location = location
        self.bucket_name = None
        self.training_file_uri = None
        self.job_id = None
        self.model_id = None
        
        # Инициализируем Vertex AI
        aiplatform.init(project=project_id, location=location)
        
        logger.info(f"✅ Vertex AI initialized")
        logger.info(f"   Project: {project_id}")
        logger.info(f"   Location: {location}")
    
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
    
    def upload_to_gcs(self, file_path: str, bucket_name: str) -> Optional[str]:
        """Загружает файл в Google Cloud Storage."""
        logger.info(f"Uploading file to GCS: gs://{bucket_name}/")
        
        try:
            # Инициализируем GCS клиент
            storage_client = storage.Client(project=self.project_id)
            bucket = storage_client.bucket(bucket_name)
            
            # Загружаем файл
            blob_name = Path(file_path).name
            blob = bucket.blob(blob_name)
            
            file_size = Path(file_path).stat().st_size
            
            blob.upload_from_filename(file_path)
            
            self.bucket_name = bucket_name
            self.training_file_uri = f"gs://{bucket_name}/{blob_name}"
            
            logger.info(f"✅ File uploaded to GCS")
            logger.info(f"   URI: {self.training_file_uri}")
            logger.info(f"   Size: {file_size} bytes ({file_size/1024:.2f} KB)")
            
            return self.training_file_uri
        
        except Exception as e:
            logger.error(f"Upload error: {e}")
            return None
    
    def create_fine_tuning_job(
        self,
        training_file_uri: str,
        model: str = "gemini-1.5-pro-002",
        epochs: int = 3,
        batch_size: int = 4,
        learning_rate: float = 0.001,
        job_display_name: str = "natasha-finetuning-v1"
    ) -> Optional[str]:
        """Создает fine-tuning job в Vertex AI."""
        logger.info(f"\nCreating fine-tuning job in Vertex AI...")
        logger.info(f"  Model: {model}")
        logger.info(f"  Epochs: {epochs}")
        logger.info(f"  Batch size: {batch_size}")
        logger.info(f"  Learning rate: {learning_rate}")
        logger.info(f"  Job name: {job_display_name}")
        
        try:
            # Создаем fine-tuning job
            response = aiplatform.PipelineJob.create_and_run(
                display_name=job_display_name,
                template_path="gs://vertex-ai/template/supervised_tuning_pipeline.yaml",
                pipeline_root=f"gs://{self.bucket_name}/pipeline-root",
                parameter_values={
                    "model_display_name": model,
                    "dataset_uri": training_file_uri,
                    "train_steps": epochs * 100,  # Примерный расчет
                    "learning_rate_multiplier": learning_rate,
                    "batch_size": batch_size,
                }
            )
            
            self.job_id = response.name
            
            logger.info(f"✅ Fine-tuning job created successfully")
            logger.info(f"   Job ID: {self.job_id}")
            logger.info(f"   Status: {response.state}")
            
            return self.job_id
        
        except Exception as e:
            logger.error(f"Job creation error: {e}")
            logger.info(f"   Note: Убедитесь, что у вас есть доступ к Vertex AI API")
            logger.info(f"   Перейдите на: https://console.cloud.google.com/vertex-ai")
            return None
    
    def get_job_status(self, job_id: str) -> dict:
        """Получает статус fine-tuning job."""
        try:
            job = aiplatform.PipelineJob.get(job_id)
            
            status_info = {
                'id': job.name,
                'status': job.state,
                'display_name': job.display_name,
                'created_time': job.create_time,
                'update_time': job.update_time,
                'error': job.error if hasattr(job, 'error') else None
            }
            
            return status_info
        
        except Exception as e:
            logger.error(f"Error getting job status: {e}")
            return {}
    
    def monitor_job(self, job_id: str, check_interval: int = 60, max_checks: int = 1000):
        """Мониторит прогресс fine-tuning job."""
        logger.info(f"\n{'='*70}")
        logger.info("MONITORING VERTEX AI FINE-TUNING JOB")
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
            
            if status == 'PIPELINE_STATE_SUCCEEDED':
                logger.info(f"\n✅ Fine-tuning completed successfully!")
                return True
            
            elif status == 'PIPELINE_STATE_FAILED':
                logger.error(f"\n❌ Fine-tuning failed!")
                error = status_info.get('error')
                if error:
                    logger.error(f"   Error: {error}")
                return False
            
            elif status == 'PIPELINE_STATE_CANCELLED':
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
    
    def save_config(self, output_path: str = "data/vertex_finetune_config.json"):
        """Сохраняет конфигурацию fine-tuning."""
        config = {
            'provider': 'vertex-ai',
            'project_id': self.project_id,
            'location': self.location,
            'bucket_name': self.bucket_name,
            'training_file_uri': self.training_file_uri,
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
        description="Upload dataset and run fine-tuning for Natasha model on Vertex AI"
    )
    parser.add_argument(
        '--file',
        type=str,
        default='data/natasha_finetuning_20251125_153356.jsonl',
        help='Path to JSONL training file'
    )
    parser.add_argument(
        '--project-id',
        type=str,
        required=True,
        help='Google Cloud Project ID'
    )
    parser.add_argument(
        '--bucket',
        type=str,
        required=True,
        help='Google Cloud Storage bucket name'
    )
    parser.add_argument(
        '--model',
        type=str,
        default='gemini-1.5-pro-002',
        help='Base model for fine-tuning'
    )
    parser.add_argument(
        '--epochs',
        type=int,
        default=3,
        help='Number of training epochs'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=4,
        help='Batch size for training'
    )
    parser.add_argument(
        '--learning-rate',
        type=float,
        default=0.001,
        help='Learning rate'
    )
    parser.add_argument(
        '--validate-only',
        action='store_true',
        help='Only validate the file'
    )
    parser.add_argument(
        '--upload-only',
        action='store_true',
        help='Only upload the file'
    )
    parser.add_argument(
        '--monitor',
        type=str,
        help='Monitor existing job by ID'
    )
    
    args = parser.parse_args()
    
    print("\n" + "="*70)
    print("NATASHA FINE-TUNING UPLOADER (VERTEX AI)")
    print("="*70 + "\n")
    
    try:
        tuner = VertexAIFineTuner(
            project_id=args.project_id,
            location="us-central1"
        )
    except Exception as e:
        logger.error(f"❌ {e}")
        logger.error("Please ensure you have Google Cloud credentials configured")
        logger.error("Run: gcloud auth application-default login")
        return
    
    try:
        # Мониторинг существующего job
        if args.monitor:
            logger.info(f"Monitoring job: {args.monitor}")
            tuner.monitor_job(args.monitor)
            return
        
        # Валидация файла
        if not tuner.validate_jsonl(args.file):
            logger.error("❌ Validation failed!")
            return
        
        if args.validate_only:
            logger.info("✅ Validation passed. Exiting.")
            return
        
        # Загрузка файла в GCS
        file_uri = tuner.upload_to_gcs(args.file, args.bucket)
        if not file_uri:
            logger.error("❌ Upload failed!")
            return
        
        if args.upload_only:
            logger.info(f"✅ File uploaded. URI: {file_uri}")
            return
        
        # Создание fine-tuning job
        job_id = tuner.create_fine_tuning_job(
            training_file_uri=file_uri,
            model=args.model,
            epochs=args.epochs,
            batch_size=args.batch_size,
            learning_rate=args.learning_rate
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
            
            # Сохраняем конфигурацию
            tuner.save_config()
        
        else:
            logger.warning(f"\n⚠️  Fine-tuning did not complete successfully")
            logger.info(f"   Job ID: {job_id}")
            logger.info(f"   Check status manually or use --monitor flag")
    
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())
