#!/usr/bin/env python3
"""
Локальный fine-tuning для RTX 2050 (мобильная карта).

Оптимизирован для ограниченной памяти:
- Используем LoRA для уменьшения памяти
- Quantization для экономии VRAM
- Меньший batch size
- Gradient accumulation
- Кэширование модели для восстановления после разрыва сети

Требования:
- torch
- transformers
- peft (для LoRA)
- bitsandbytes (для quantization)
"""
import json
import sys
import os
import time
from pathlib import Path
from typing import List, Dict, Optional
import torch
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
    Trainer,
    DataCollatorForLanguageModeling,
)
from datasets import load_dataset
from peft import LoraConfig, get_peft_model
import logging
import matplotlib.pyplot as plt
import numpy as np
from tqdm import tqdm
import traceback

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Кэш для моделей в текущей директории проекта
CACHE_DIR = Path(__file__).parent.parent.parent / ".model_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


class LocalFineTuner:
    """Локальный fine-tuner для RTX 2050."""
    
    def __init__(self, model_name: str = "dphn/dolphin-2.8-mistral-7b-v02", quantize: str = "none"):
        """
        Инициализирует fine-tuner.
        
        Args:
            model_name: Название модели из Hugging Face
            quantize: Тип квантизации ('none', '8bit', '4bit')
        """
        self.model_name = model_name
        self.quantize = quantize
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.cache_dir = CACHE_DIR / model_name.replace("/", "_")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Device: {self.device}")
        if self.device == "cuda":
            logger.info(f"GPU: {torch.cuda.get_device_name(0)}")
            logger.info(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB")
        logger.info(f"Quantization: {quantize}")
        logger.info(f"Cache dir: {self.cache_dir}")
    
    def _load_with_retry(self, load_func, max_retries: int = 10, initial_wait: int = 3):
        """Загружает с retry логикой для обработки сетевых ошибок."""
        for attempt in range(max_retries):
            try:
                return load_func()
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = initial_wait * (2 ** min(attempt, 4))  # Макс 48 сек между попытками
                    logger.warning(f"Attempt {attempt + 1}/{max_retries} failed: {str(e)[:100]}")
                    logger.info(f"Retrying in {wait_time} seconds... (VPN check?)")
                    time.sleep(wait_time)
                else:
                    raise
    
    def load_model_and_tokenizer(self):
        """Загружает модель и токенайзер с оптимизацией для RTX 2050."""
        try:
            logger.info(f"📥 Loading model: {self.model_name}")
            
            # Загружаем токенайзер с retry
            logger.info("Loading tokenizer...")
            def load_tokenizer():
                return AutoTokenizer.from_pretrained(
                    self.model_name,
                    cache_dir=str(self.cache_dir)
                )
            
            self.tokenizer = self._load_with_retry(load_tokenizer)
            self.tokenizer.pad_token = self.tokenizer.eos_token
            logger.info("✅ Tokenizer loaded")
            
            # Устанавливаем timeout для скачки файлов
            os.environ['HF_HUB_DOWNLOAD_TIMEOUT'] = '3600'  # 1 час
            
            # Загружаем модель с retry
            if self.device == "cuda":
                if self.quantize == "8bit":
                    try:
                        logger.info("Attempting 8-bit quantization...")
                        def load_8bit():
                            return AutoModelForCausalLM.from_pretrained(
                                self.model_name,
                                load_in_8bit=True,
                                device_map="auto",
                                torch_dtype=torch.float16,
                                cache_dir=str(self.cache_dir),
                            )
                        self.model = self._load_with_retry(load_8bit)
                        logger.info("✅ Loaded with 8-bit quantization")
                    except Exception as e:
                        logger.warning(f"8-bit quantization failed: {e}")
                        logger.info("Falling back to no quantization...")
                        def load_no_quant():
                            return AutoModelForCausalLM.from_pretrained(
                                self.model_name,
                                device_map="auto",
                                torch_dtype=torch.float16,
                                cache_dir=str(self.cache_dir),
                            )
                        self.model = self._load_with_retry(load_no_quant)
                        logger.info("✅ Loaded without quantization")
                elif self.quantize == "4bit":
                    try:
                        from transformers import BitsAndBytesConfig
                        logger.info("Attempting 4-bit quantization...")
                        bnb_config = BitsAndBytesConfig(
                            load_in_4bit=True,
                            bnb_4bit_use_double_quant=True,
                            bnb_4bit_quant_type="nf4",
                            bnb_4bit_compute_dtype=torch.float16
                        )
                        def load_4bit():
                            return AutoModelForCausalLM.from_pretrained(
                                self.model_name,
                                quantization_config=bnb_config,
                                device_map="auto",
                                cache_dir=str(self.cache_dir),
                            )
                        self.model = self._load_with_retry(load_4bit)
                        logger.info("✅ Loaded with 4-bit quantization")
                    except Exception as e:
                        logger.warning(f"4-bit quantization failed: {e}")
                        logger.info("Falling back to 8-bit...")
                        def load_8bit_fallback():
                            return AutoModelForCausalLM.from_pretrained(
                                self.model_name,
                                load_in_8bit=True,
                                device_map="auto",
                                torch_dtype=torch.float16,
                                cache_dir=str(self.cache_dir),
                            )
                        self.model = self._load_with_retry(load_8bit_fallback)
                        logger.info("✅ Loaded with 8-bit quantization")
                else:
                    logger.info("Loading without quantization...")
                    def load_no_quant_default():
                        return AutoModelForCausalLM.from_pretrained(
                            self.model_name,
                            device_map="auto",
                            torch_dtype=torch.float16,
                            cache_dir=str(self.cache_dir),
                        )
                    self.model = self._load_with_retry(load_no_quant_default)
                    logger.info("✅ Loaded without quantization")
            else:
                # На CPU загружаем без quantization
                logger.info("Loading on CPU (no quantization)...")
                def load_cpu():
                    return AutoModelForCausalLM.from_pretrained(
                        self.model_name,
                        torch_dtype=torch.float32,
                        cache_dir=str(self.cache_dir),
                    )
                self.model = self._load_with_retry(load_cpu)
                logger.info("✅ Model loaded on CPU")
        except Exception as e:
            logger.error(f"❌ Failed to load model: {e}")
            logger.error(traceback.format_exc())
            raise
        
        # Применяем LoRA для уменьшения параметров
        try:
            logger.info("🔧 Applying LoRA...")
            
            # Определяем target modules в зависимости от модели
            if "mistral" in self.model_name.lower() or "zephyr" in self.model_name.lower() or "dolphin" in self.model_name.lower():
                target_modules = ["q_proj", "v_proj"]
            elif "gpt2" in self.model_name.lower():
                target_modules = ["c_attn"]
            else:
                # Для других моделей пытаемся найти attention модули
                target_modules = ["q_proj", "v_proj", "c_attn"]
            
            lora_config = LoraConfig(
                r=8,  # Rank
                lora_alpha=16,
                target_modules=target_modules,
                lora_dropout=0.05,
                bias="none",
                task_type="CAUSAL_LM"
            )
            
            self.model = get_peft_model(self.model, lora_config)
            self.model.print_trainable_parameters()
            logger.info("✅ LoRA applied successfully")
        except Exception as e:
            logger.error(f"❌ Failed to apply LoRA: {e}")
            logger.error(traceback.format_exc())
            raise
        
        return self.model, self.tokenizer
    
    def load_dataset(self, jsonl_path: str):
        """Загружает датасет из JSONL файла с retry логикой."""
        try:
            logger.info(f"📂 Loading dataset from: {jsonl_path}")
            
            # Загружаем датасет с retry
            def load_data():
                return load_dataset('json', data_files=jsonl_path)
            
            dataset = self._load_with_retry(load_data)
            
            # Преобразуем в нужный формат
            def format_data(example):
                text = ""
                for msg in example['messages']:
                    if msg['role'] == 'user':
                        text += f"User: {msg['content']}\n"
                    else:
                        text += f"Assistant: {msg['content']}\n"
                return {'text': text}
            
            logger.info("Formatting dataset...")
            dataset = dataset.map(format_data, desc="Formatting")
            
            logger.info(f"✅ Dataset loaded: {len(dataset['train'])} examples")
            return dataset
        except Exception as e:
            logger.error(f"❌ Failed to load dataset: {e}")
            logger.error(traceback.format_exc())
            raise
    
    def tokenize_function(self, examples):
        """Токенизирует примеры."""
        return self.tokenizer(
            examples['text'],
            truncation=True,
            max_length=512,
            padding="max_length",
        )
    
    def train(
        self,
        jsonl_path: str,
        output_dir: str = "./natasha-model-local",
        num_epochs: int = 6,
        batch_size: int = 2,  # Маленький batch для RTX 2050
        learning_rate: float = 1e-4,
    ):
        """Обучает модель."""
        try:
            logger.info("🚀 Starting training...")
            
            # Загружаем модель и датасет
            logger.info("\n[1/4] Loading model and tokenizer...")
            self.load_model_and_tokenizer()
            
            logger.info("\n[2/4] Loading dataset...")
            dataset = self.load_dataset(jsonl_path)
            
            # Токенизируем
            logger.info("\n[3/4] Tokenizing dataset...")
            tokenized_dataset = dataset.map(
                self.tokenize_function,
                batched=True,
                remove_columns=['messages', 'text'],
                desc="Tokenizing"
            )
            
            # Параметры обучения (оптимизированы для RTX 2050)
            # Выбираем оптимайзер в зависимости от устройства
            optim_type = "paged_adamw_8bit" if self.device == "cuda" else "adamw_torch"
            use_fp16 = self.device == "cuda"
            
            training_args = TrainingArguments(
                output_dir=output_dir,
                num_train_epochs=num_epochs,
                per_device_train_batch_size=batch_size,
                gradient_accumulation_steps=4,  # Компенсируем маленький batch
                learning_rate=learning_rate,
                warmup_steps=100,
                weight_decay=0.01,
                logging_steps=10,
                save_steps=50,
                save_total_limit=2,
                fp16=use_fp16,  # Mixed precision только на GPU
                optim=optim_type,  # Оптимайзер в зависимости от устройства
                max_grad_norm=0.3,
                seed=42,
                report_to=["tensorboard"],
            )
            
            # Создаем trainer
            trainer = Trainer(
                model=self.model,
                args=training_args,
                train_dataset=tokenized_dataset['train'],
                data_collator=DataCollatorForLanguageModeling(
                    self.tokenizer,
                    mlm=False
                ),
            )
            
            # Обучаем
            logger.info("\n[4/4] Training model...")
            logger.info(f"⏱️  Epochs: {num_epochs}, Batch size: {batch_size}, LR: {learning_rate}")
            train_result = trainer.train()
            
            # Сохраняем модель
            logger.info(f"\n💾 Saving model to: {output_dir}")
            self.model.save_pretrained(output_dir)
            self.tokenizer.save_pretrained(output_dir)
            
            # Сохраняем логи обучения
            logger.info("📊 Generating training metrics...")
            self._plot_training_metrics(trainer, output_dir)
            
            logger.info("\n" + "="*70)
            logger.info("✅ Training completed successfully!")
            logger.info("="*70)
            return output_dir
            
        except KeyboardInterrupt:
            logger.warning("\n⚠️  Training interrupted by user")
            logger.info("Attempting to save checkpoint...")
            try:
                checkpoint_dir = Path(output_dir) / "interrupted_checkpoint"
                self.model.save_pretrained(checkpoint_dir)
                self.tokenizer.save_pretrained(checkpoint_dir)
                logger.info(f"✅ Checkpoint saved to: {checkpoint_dir}")
            except Exception as e:
                logger.error(f"Failed to save checkpoint: {e}")
            raise
            
        except Exception as e:
            logger.error(f"\n❌ Training failed: {e}")
            logger.error(traceback.format_exc())
            logger.info("Attempting to save emergency checkpoint...")
            try:
                emergency_dir = Path(output_dir) / "emergency_checkpoint"
                self.model.save_pretrained(emergency_dir)
                self.tokenizer.save_pretrained(emergency_dir)
                logger.info(f"✅ Emergency checkpoint saved to: {emergency_dir}")
            except Exception as save_e:
                logger.error(f"Failed to save emergency checkpoint: {save_e}")
            raise
    
    def _plot_training_metrics(self, trainer, output_dir: str):
        """Создает графики метрик обучения."""
        try:
            import json
            
            # Получаем логи из trainer
            logs = trainer.state.log_history
            
            if not logs:
                logger.warning("No training logs found")
                return
            
            # Извлекаем данные
            steps = []
            losses = []
            learning_rates = []
            
            for log in logs:
                if 'loss' in log:
                    steps.append(log.get('step', len(steps)))
                    losses.append(log['loss'])
                    learning_rates.append(log.get('learning_rate', learning_rate))
            
            if not losses:
                logger.warning("No loss data found")
                return
            
            # Создаем фигуру с несколькими подграфиками
            fig, axes = plt.subplots(2, 2, figsize=(14, 10))
            fig.suptitle('Training Metrics', fontsize=16, fontweight='bold')
            
            # График 1: Loss
            axes[0, 0].plot(steps, losses, 'b-', linewidth=2)
            axes[0, 0].set_xlabel('Step')
            axes[0, 0].set_ylabel('Loss')
            axes[0, 0].set_title('Training Loss')
            axes[0, 0].grid(True, alpha=0.3)
            
            # График 2: Loss (сглаженный)
            if len(losses) > 5:
                window = max(1, len(losses) // 10)
                smoothed_losses = np.convolve(losses, np.ones(window)/window, mode='valid')
                smoothed_steps = steps[window-1:]
                axes[0, 1].plot(smoothed_steps, smoothed_losses, 'g-', linewidth=2, label='Smoothed')
                axes[0, 1].plot(steps, losses, 'b-', alpha=0.3, label='Raw')
                axes[0, 1].set_xlabel('Step')
                axes[0, 1].set_ylabel('Loss')
                axes[0, 1].set_title('Smoothed Training Loss')
                axes[0, 1].legend()
                axes[0, 1].grid(True, alpha=0.3)
            
            # График 3: Learning Rate
            if learning_rates and any(lr > 0 for lr in learning_rates):
                axes[1, 0].plot(steps, learning_rates, 'r-', linewidth=2)
                axes[1, 0].set_xlabel('Step')
                axes[1, 0].set_ylabel('Learning Rate')
                axes[1, 0].set_title('Learning Rate Schedule')
                axes[1, 0].grid(True, alpha=0.3)
            
            # График 4: Loss Distribution
            axes[1, 1].hist(losses, bins=30, color='purple', alpha=0.7, edgecolor='black')
            axes[1, 1].set_xlabel('Loss Value')
            axes[1, 1].set_ylabel('Frequency')
            axes[1, 1].set_title('Loss Distribution')
            axes[1, 1].grid(True, alpha=0.3, axis='y')
            
            plt.tight_layout()
            
            # Сохраняем график
            plot_path = Path(output_dir) / "training_metrics.png"
            plt.savefig(plot_path, dpi=150, bbox_inches='tight')
            logger.info(f"✅ Training metrics saved to: {plot_path}")
            
            # Сохраняем статистику
            stats = {
                'final_loss': losses[-1] if losses else None,
                'min_loss': min(losses) if losses else None,
                'max_loss': max(losses) if losses else None,
                'avg_loss': np.mean(losses) if losses else None,
                'total_steps': len(steps),
            }
            
            stats_path = Path(output_dir) / "training_stats.json"
            with open(stats_path, 'w') as f:
                json.dump(stats, f, indent=2)
            logger.info(f"✅ Training stats saved to: {stats_path}")
            logger.info(f"Final Loss: {stats['final_loss']:.4f}")
            logger.info(f"Min Loss: {stats['min_loss']:.4f}")
            logger.info(f"Avg Loss: {stats['avg_loss']:.4f}")
            
        except Exception as e:
            logger.error(f"Error plotting metrics: {e}", exc_info=True)


def main():
    """Главная функция."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Local fine-tuning for RTX 2050"
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
        default='DavidAU/Llama-3.1-DeepSeek-8B-DarkIdol-Instruct-1.2-Uncensored',
        help='Model name from Hugging Face'
    )
    parser.add_argument(
        '--epochs',
        type=int,
        default=6,
        help='Number of training epochs (default: 6 for 321 examples)'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=2,
        help='Batch size (default: 2 for RTX 2050)'
    )
    parser.add_argument(
        '--lr',
        type=float,
        default=1e-4,
        help='Learning rate (default: 1e-4 for small datasets)'
    )
    parser.add_argument(
        '--quantize',
        type=str,
        choices=['none', '8bit', '4bit'],
        default='none',
        help='Quantization type (default: none, use 8bit for memory optimization)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='./natasha-model-local',
        help='Output directory'
    )
    
    args = parser.parse_args()
    
    print("\n" + "="*70)
    print("LOCAL FINE-TUNING FOR RTX 2050")
    print("="*70)
    print(f"Model: {args.model}")
    print(f"Dataset: {args.file}")
    print(f"Epochs: {args.epochs} | Batch size: {args.batch_size} | LR: {args.lr}")
    print(f"Quantization: {args.quantize}")
    print("="*70 + "\n")
    
    try:
        tuner = LocalFineTuner(model_name=args.model, quantize=args.quantize)
        tuner.train(
            jsonl_path=args.file,
            output_dir=args.output,
            num_epochs=args.epochs,
            batch_size=args.batch_size,
            learning_rate=args.lr,
        )
    except KeyboardInterrupt:
        logger.warning("\n⚠️  Training interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n❌ Fatal error: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
