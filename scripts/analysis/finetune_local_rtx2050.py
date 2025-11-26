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

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class LocalFineTuner:
    """Локальный fine-tuner для RTX 2050."""
    
    def __init__(self, model_name: str = "mistralai/Mistral-7B-Instruct-v0.1"):
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
        
        # Загружаем модель с quantization для экономии памяти
        try:
            # Пытаемся использовать 8-bit quantization
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
        
        # Применяем LoRA для уменьшения параметров
        logger.info("Applying LoRA...")
        lora_config = LoraConfig(
            r=8,  # Rank
            lora_alpha=16,
            target_modules=["q_proj", "v_proj"],
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
        num_epochs: int = 3,
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
            fp16=True,  # Mixed precision для экономии памяти
            optim="paged_adamw_8bit",  # Оптимизированный оптимайзер
            max_grad_norm=0.3,
            seed=42,
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
        trainer.train()
        
        # Сохраняем модель
        logger.info(f"Saving model to: {output_dir}")
        self.model.save_pretrained(output_dir)
        self.tokenizer.save_pretrained(output_dir)
        
        logger.info("✅ Training completed!")
        return output_dir


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
        default='mistralai/Mistral-7B-Instruct-v0.1',
        help='Model name from Hugging Face'
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
