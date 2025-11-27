#!/usr/bin/env python3
"""
Fine-tuning script for Google Colab.
Использует Google Drive для хранения датасета и результатов.
"""

import os
import json
import sys
from pathlib import Path
from typing import Optional
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
import traceback

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def setup_colab():
    """Настраивает окружение Colab."""
    try:
        import google.colab
        # Проверяем, смонтирован ли уже drive
        if not Path('/content/drive/MyDrive').exists():
            from google.colab import drive
            drive.mount('/content/drive')
            logger.info("✅ Google Drive mounted")
        else:
            logger.info("✅ Google Drive already mounted")
        return True
    except (ImportError, AttributeError):
        logger.warning("Not running in Colab or Drive already mounted")
        return False


class ColabFineTuner:
    """Fine-tuner для Google Colab."""
    
    def __init__(
        self,
        model_name: str = "DavidAU/Llama-3.1-DeepSeek-8B-DarkIdol-Instruct-1.2-Uncensored",
        drive_path: str = "/content/drive/MyDrive/relove_finetuning"
    ):
        self.model_name = model_name
        self.drive_path = Path(drive_path)
        self.drive_path.mkdir(parents=True, exist_ok=True)
        
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Device: {self.device}")
        if self.device == "cuda":
            logger.info(f"GPU: {torch.cuda.get_device_name(0)}")
            logger.info(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB")
    
    def load_model_and_tokenizer(self):
        """Загружает модель и токенайзер."""
        try:
            logger.info(f"📥 Loading model: {self.model_name}")
            
            # Загружаем токенайзер
            logger.info("Loading tokenizer...")
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self.tokenizer.pad_token = self.tokenizer.eos_token
            logger.info("✅ Tokenizer loaded")
            
            # Загружаем модель с 4-bit квантизацией для экономии памяти
            logger.info("Loading model with 4-bit quantization...")
            from transformers import BitsAndBytesConfig
            
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.float16
            )
            
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                quantization_config=bnb_config,
                device_map="auto",
                torch_dtype=torch.float16,
            )
            logger.info("✅ Model loaded with 4-bit quantization")
            
            # Включаем gradient checkpointing для экономии памяти
            self.model.gradient_checkpointing_enable()
            
            # Применяем LoRA
            logger.info("🔧 Applying LoRA...")
            lora_config = LoraConfig(
                r=8,
                lora_alpha=16,
                target_modules=["q_proj", "v_proj"],
                lora_dropout=0.05,
                bias="none",
                task_type="CAUSAL_LM"
            )
            self.model = get_peft_model(self.model, lora_config)
            self.model.print_trainable_parameters()
            logger.info("✅ LoRA applied")
            
        except Exception as e:
            logger.error(f"❌ Failed to load model: {e}")
            logger.error(traceback.format_exc())
            raise
    
    def load_dataset(self, jsonl_path: str):
        """Загружает датасет из JSONL файла."""
        try:
            logger.info(f"📂 Loading dataset from: {jsonl_path}")
            
            dataset = load_dataset('json', data_files=jsonl_path)
            
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
        num_epochs: int = 6,
        batch_size: int = 2,
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
            
            # Параметры обучения
            output_dir = str(self.drive_path / "model_output")
            
            training_args = TrainingArguments(
                output_dir=output_dir,
                num_train_epochs=num_epochs,
                per_device_train_batch_size=1,  # Уменьшаем до 1 для экономии памяти
                gradient_accumulation_steps=8,  # Увеличиваем для компенсации
                learning_rate=learning_rate,
                warmup_steps=100,
                weight_decay=0.01,
                logging_steps=10,
                save_steps=50,
                save_total_limit=2,
                fp16=True,
                optim="paged_adamw_8bit",
                max_grad_norm=0.3,
                seed=42,
                report_to=["tensorboard"],
                gradient_checkpointing=True,
                max_grad_norm=0.3,
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
            
            # Сохраняем метрики
            logger.info("📊 Generating training metrics...")
            self._plot_training_metrics(trainer, output_dir)
            
            logger.info("\n" + "="*70)
            logger.info("✅ Training completed successfully!")
            logger.info(f"Model saved to: {output_dir}")
            logger.info("="*70)
            
            return output_dir
            
        except Exception as e:
            logger.error(f"\n❌ Training failed: {e}")
            logger.error(traceback.format_exc())
            raise
    
    def _plot_training_metrics(self, trainer, output_dir: str):
        """Создает графики метрик обучения."""
        try:
            logs = trainer.state.log_history
            
            if not logs:
                logger.warning("No training logs found")
                return
            
            steps = []
            losses = []
            
            for log in logs:
                if 'loss' in log:
                    steps.append(log.get('step', len(steps)))
                    losses.append(log['loss'])
            
            if not losses:
                logger.warning("No loss data found")
                return
            
            fig, axes = plt.subplots(1, 2, figsize=(14, 5))
            fig.suptitle('Training Metrics', fontsize=16, fontweight='bold')
            
            # График 1: Loss
            axes[0].plot(steps, losses, 'b-', linewidth=2)
            axes[0].set_xlabel('Step')
            axes[0].set_ylabel('Loss')
            axes[0].set_title('Training Loss')
            axes[0].grid(True, alpha=0.3)
            
            # График 2: Loss Distribution
            axes[1].hist(losses, bins=30, color='purple', alpha=0.7, edgecolor='black')
            axes[1].set_xlabel('Loss Value')
            axes[1].set_ylabel('Frequency')
            axes[1].set_title('Loss Distribution')
            axes[1].grid(True, alpha=0.3, axis='y')
            
            plt.tight_layout()
            
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
    
    parser = argparse.ArgumentParser(description="Fine-tuning for Google Colab")
    parser.add_argument(
        '--file',
        type=str,
        default='/content/drive/MyDrive/relove_finetuning/natasha_finetuning.jsonl',
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
        help='Number of training epochs'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=1,
        help='Batch size (default: 1 for memory efficiency)'
    )
    parser.add_argument(
        '--lr',
        type=float,
        default=1e-4,
        help='Learning rate'
    )
    
    args = parser.parse_args()
    
    print("\n" + "="*70)
    print("FINE-TUNING FOR GOOGLE COLAB")
    print("="*70)
    print(f"Model: {args.model}")
    print(f"Dataset: {args.file}")
    print(f"Epochs: {args.epochs} | Batch size: {args.batch_size} | LR: {args.lr}")
    print("="*70 + "\n")
    
    try:
        # Настраиваем Colab
        is_colab = setup_colab()
        
        tuner = ColabFineTuner(model_name=args.model)
        tuner.train(
            jsonl_path=args.file,
            num_epochs=args.epochs,
            batch_size=args.batch_size,
            learning_rate=args.lr,
        )
    except Exception as e:
        logger.error(f"\n❌ Fatal error: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
