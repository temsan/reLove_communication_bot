#!/usr/bin/env python3
"""
Локальный fine-tuning для RTX 2050 (мобильная карта).

Оптимизирован для ограниченной памяти:
- Используем LoRA для уменьшения памяти
- Quantization для экономии VRAM
- Меньший batch size
- Gradient accumulation

Требования:
- torch
- transformers
- peft (для LoRA)
- bitsandbytes (для quantization)
"""
import json
import sys
from pathlib import Path
from typing import List, Dict
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

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class LocalFineTuner:
    """Локальный fine-tuner для RTX 2050."""
    
    def __init__(self, model_name: str = "dphn/dolphin-2.8-mistral-7b-v02"):
        """
        Инициализирует fine-tuner.
        
        Args:
            model_name: Название модели из Hugging Face
        """
        self.model_name = model_name
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        
        logger.info(f"Device: {self.device}")
        if self.device == "cuda":
            logger.info(f"GPU: {torch.cuda.get_device_name(0)}")
            logger.info(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB")
    
    def load_model_and_tokenizer(self):
        """Загружает модель и токенайзер с оптимизацией для RTX 2050."""
        logger.info(f"Loading model: {self.model_name}")
        
        # Загружаем токенайзер
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self.tokenizer.pad_token = self.tokenizer.eos_token
        
        # Загружаем модель
        if self.device == "cuda":
            try:
                # На GPU пытаемся использовать 8-bit quantization
                self.model = AutoModelForCausalLM.from_pretrained(
                    self.model_name,
                    load_in_8bit=True,
                    device_map="auto",
                    torch_dtype=torch.float16,
                )
                logger.info("✅ Loaded with 8-bit quantization")
            except Exception as e:
                logger.warning(f"8-bit quantization failed: {e}")
                logger.info("Loading without quantization...")
                self.model = AutoModelForCausalLM.from_pretrained(
                    self.model_name,
                    device_map="auto",
                    torch_dtype=torch.float16,
                )
        else:
            # На CPU загружаем без quantization
            logger.info("Loading on CPU (no quantization)...")
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                torch_dtype=torch.float32,
            )
        
        # Применяем LoRA для уменьшения параметров
        logger.info("Applying LoRA...")
        
        # Определяем target modules в зависимости от модели
        if "mistral" in self.model_name.lower() or "zephyr" in self.model_name.lower():
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
        
        return self.model, self.tokenizer
    
    def load_dataset(self, jsonl_path: str):
        """Загружает датасет из JSONL файла."""
        logger.info(f"Loading dataset from: {jsonl_path}")
        
        # Загружаем датасет
        dataset = load_dataset('json', data_files=jsonl_path)
        
        # Преобразуем в нужный формат
        def format_data(example):
            text = ""
            for msg in example['messages']:
                if msg['role'] == 'user':
                    text += f"User: {msg['content']}\n"
                else:
                    text += f"Assistant: {msg['content']}\n"
            return {'text': text}
        
        dataset = dataset.map(format_data)
        
        logger.info(f"Dataset size: {len(dataset['train'])} examples")
        return dataset
    
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
        num_epochs: int = 10,
        batch_size: int = 2,  # Маленький batch для RTX 2050
        learning_rate: float = 2e-4,
    ):
        """Обучает модель."""
        logger.info("Starting training...")
        
        # Загружаем модель и датасет
        self.load_model_and_tokenizer()
        dataset = self.load_dataset(jsonl_path)
        
        # Токенизируем
        logger.info("Tokenizing dataset...")
        tokenized_dataset = dataset.map(
            self.tokenize_function,
            batched=True,
            remove_columns=['messages', 'text']
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
        logger.info("Training started...")
        train_result = trainer.train()
        
        # Сохраняем модель
        logger.info(f"Saving model to: {output_dir}")
        self.model.save_pretrained(output_dir)
        self.tokenizer.save_pretrained(output_dir)
        
        # Сохраняем логи обучения
        self._plot_training_metrics(trainer, output_dir)
        
        logger.info("✅ Training completed!")
        return output_dir
    
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
        default='dphn/dolphin-2.8-mistral-7b-v02',
        help='Model name from Hugging Face'
    )
    parser.add_argument(
        '--epochs',
        type=int,
        default=10,
        help='Number of training epochs'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=2,
        help='Batch size (default: 2 for RTX 2050)'
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
    print("="*70 + "\n")
    
    try:
        tuner = LocalFineTuner(model_name=args.model)
        tuner.train(
            jsonl_path=args.file,
            output_dir=args.output,
            num_epochs=args.epochs,
            batch_size=args.batch_size,
        )
    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)


if __name__ == "__main__":
    main()
