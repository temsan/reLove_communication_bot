#!/usr/bin/env python3
"""
Сбор датасета диалогов Наташи с юзерами для дообучения модели.

Задачи:
1. Извлечение всех диалогов Наташи с юзерами из всех каналов reLove
2. Форматирование в формат для fine-tuning (question-answer pairs)
3. Создание JSONL датасета для OpenAI API
4. Статистика и анализ качества данных
"""
import asyncio
import json
import sys
from pathlib import Path
from typing import List, Dict, Any, Tuple
from datetime import datetime
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from telethon import TelegramClient
from relove_bot.config import settings
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/collect_natasha_dialogs.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ID Наташи Волкош
NATASHA_ID = 496684653

# Минимальная длина сообщения для включения в датасет
MIN_MESSAGE_LENGTH = 20

# Минимальное количество сообщений в диалоге
MIN_DIALOG_LENGTH = 2


class NatashaDialogsCollector:
    """Сборщик диалогов Наташи для датасета."""
    
    def __init__(self):
        self.client = TelegramClient(
            settings.tg_session,
            settings.tg_api_id,
            settings.tg_api_hash.get_secret_value()
        )
        
        # Данные для датасета
        self.dialogs = []  # Все диалоги
        self.qa_pairs = []  # Question-answer пары
        self.statistics = {
            'total_channels': 0,
            'total_messages': 0,
            'natasha_messages': 0,
            'user_messages': 0,
            'valid_dialogs': 0,
            'channels_processed': []
        }
    
    async def collect_from_all_channels(self, limit_per_channel: int = 2000):
        """Собирает диалоги из всех каналов reLove."""
        logger.info("Starting collection from all reLove channels...")
        
        async for dialog in self.client.iter_dialogs():
            name_lower = dialog.name.lower()
            
            # Только каналы reLove
            if 'relove' not in name_lower and 'релов' not in name_lower:
                continue
            
            channel_name = dialog.name
            logger.info(f"\n{'='*70}")
            logger.info(f"Processing: {channel_name}")
            logger.info(f"{'='*70}")
            
            try:
                await self._process_channel(
                    dialog.entity,
                    channel_name,
                    limit_per_channel
                )
                
                self.statistics['channels_processed'].append(channel_name)
                self.statistics['total_channels'] += 1
                
            except Exception as e:
                logger.error(f"❌ Error processing {channel_name}: {e}")
    
    async def _process_channel(
        self,
        channel_entity,
        channel_name: str,
        limit: int
    ):
        """Обрабатывает один канал."""
        messages_list = []
        
        # Получаем все сообщения
        async for message in self.client.iter_messages(channel_entity, limit=limit):
            if message.text:
                messages_list.append(message)
        
        logger.info(f"Got {len(messages_list)} messages")
        
        # Сортируем по времени
        messages_list.sort(key=lambda m: m.date)
        
        # Ищем диалоги Наташи
        channel_dialogs = 0
        channel_qa_pairs = 0
        
        for i, message in enumerate(messages_list):
            # Ищем сообщения Наташи
            if message.sender_id == NATASHA_ID and len(message.text) >= MIN_MESSAGE_LENGTH:
                
                # Вариант 1: Диалог через reply_to
                if message.reply_to and message.reply_to.reply_to_msg_id:
                    dialog_data = self._extract_reply_chain_dialog(
                        message,
                        messages_list,
                        channel_name
                    )
                    
                    if dialog_data:
                        self.dialogs.append(dialog_data)
                        
                        # Создаём QA пары
                        qa_pair = self._create_qa_pair_from_dialog(dialog_data)
                        if qa_pair:
                            self.qa_pairs.append(qa_pair)
                            channel_qa_pairs += 1
                        
                        channel_dialogs += 1
                
                # Вариант 2: Диалог по контексту (если нет reply)
                else:
                    dialog_data = self._extract_context_dialog(
                        message,
                        messages_list,
                        i,
                        channel_name
                    )
                    
                    if dialog_data:
                        self.dialogs.append(dialog_data)
                        
                        # Создаём QA пары
                        qa_pair = self._create_qa_pair_from_dialog(dialog_data)
                        if qa_pair:
                            self.qa_pairs.append(qa_pair)
                            channel_qa_pairs += 1
                        
                        channel_dialogs += 1
        
        logger.info(f"✅ Found {channel_dialogs} dialogs, {channel_qa_pairs} QA pairs")
        
        self.statistics['total_messages'] += len(messages_list)
        self.statistics['natasha_messages'] += sum(
            1 for m in messages_list if m.sender_id == NATASHA_ID
        )
        self.statistics['user_messages'] += sum(
            1 for m in messages_list if m.sender_id != NATASHA_ID
        )
        self.statistics['valid_dialogs'] += channel_dialogs
    
    def _extract_reply_chain_dialog(
        self,
        natasha_message,
        messages_list: List,
        channel_name: str
    ) -> Dict[str, Any]:
        """Извлекает диалог через цепочку reply."""
        try:
            # Ищем сообщение, на которое отвечает Наташа
            replied_msg = None
            for msg in messages_list:
                if msg.id == natasha_message.reply_to.reply_to_msg_id:
                    replied_msg = msg
                    break
            
            if not replied_msg or len(replied_msg.text) < MIN_MESSAGE_LENGTH:
                return None
            
            # Строим цепочку реплаев
            reply_chain = []
            current_msg = replied_msg
            chain_depth = 0
            max_chain_depth = 5
            
            while current_msg and chain_depth < max_chain_depth:
                sender_name = "Unknown"
                if current_msg.sender:
                    sender_name = getattr(current_msg.sender, 'first_name', 'Unknown')
                
                reply_chain.insert(0, {
                    'sender_id': current_msg.sender_id,
                    'sender_name': sender_name,
                    'is_natasha': current_msg.sender_id == NATASHA_ID,
                    'text': current_msg.text,
                    'date': current_msg.date.isoformat(),
                    'message_id': current_msg.id
                })
                
                # Проверяем, есть ли у этого сообщения reply
                if current_msg.reply_to and current_msg.reply_to.reply_to_msg_id:
                    next_msg = None
                    for msg in messages_list:
                        if msg.id == current_msg.reply_to.reply_to_msg_id:
                            next_msg = msg
                            break
                    current_msg = next_msg
                    chain_depth += 1
                else:
                    break
            
            # Добавляем сообщение Наташи в конец
            reply_chain.append({
                'sender_id': NATASHA_ID,
                'sender_name': 'Наташа Волкош',
                'is_natasha': True,
                'text': natasha_message.text,
                'date': natasha_message.date.isoformat(),
                'message_id': natasha_message.id
            })
            
            if len(reply_chain) < MIN_DIALOG_LENGTH:
                return None
            
            return {
                'channel': channel_name,
                'date': natasha_message.date.isoformat(),
                'type': 'reply_chain',
                'context': reply_chain,
                'user_message': replied_msg.text,
                'natasha_response': natasha_message.text,
                'user_name': getattr(replied_msg.sender, 'first_name', 'Unknown') if replied_msg.sender else 'Unknown'
            }
        
        except Exception as e:
            logger.debug(f"Error extracting reply chain: {e}")
            return None
    
    def _extract_context_dialog(
        self,
        natasha_message,
        messages_list: List,
        message_index: int,
        channel_name: str
    ) -> Dict[str, Any]:
        """Извлекает диалог по контексту."""
        try:
            # Берём контекст: 2 сообщения до, само сообщение Наташи, 1 после
            context_start = max(0, message_index - 2)
            context_end = min(len(messages_list), message_index + 2)
            
            context = []
            user_message = None
            
            for j in range(context_start, context_end):
                msg = messages_list[j]
                
                if len(msg.text) < MIN_MESSAGE_LENGTH:
                    continue
                
                sender_name = "Unknown"
                if msg.sender:
                    sender_name = getattr(msg.sender, 'first_name', 'Unknown')
                
                context.append({
                    'sender_id': msg.sender_id,
                    'sender_name': sender_name,
                    'is_natasha': msg.sender_id == NATASHA_ID,
                    'text': msg.text,
                    'date': msg.date.isoformat(),
                    'message_id': msg.id
                })
                
                # Запоминаем последнее сообщение пользователя перед Наташей
                if msg.sender_id != NATASHA_ID and j < message_index:
                    user_message = msg.text
            
            if len(context) < MIN_DIALOG_LENGTH or not user_message:
                return None
            
            return {
                'channel': channel_name,
                'date': natasha_message.date.isoformat(),
                'type': 'context',
                'context': context,
                'user_message': user_message,
                'natasha_response': natasha_message.text,
                'user_name': 'Unknown'
            }
        
        except Exception as e:
            logger.debug(f"Error extracting context dialog: {e}")
            return None
    
    def _create_qa_pair_from_dialog(self, dialog: Dict[str, Any]) -> Dict[str, str]:
        """Создаёт QA пару из диалога."""
        try:
            # Собираем контекст (все сообщения кроме последнего ответа Наташи)
            context_messages = []
            
            for msg in dialog['context'][:-1]:  # Все кроме последнего
                if not msg['is_natasha']:
                    context_messages.append(msg['text'])
            
            if not context_messages:
                return None
            
            # Вопрос - последнее сообщение пользователя
            question = context_messages[-1] if context_messages else dialog['user_message']
            
            # Ответ - сообщение Наташи
            answer = dialog['natasha_response']
            
            if not question or not answer or len(question) < 10 or len(answer) < 10:
                return None
            
            return {
                'prompt': question,
                'completion': answer,
                'channel': dialog['channel'],
                'date': dialog['date'],
                'user_name': dialog.get('user_name', 'Unknown')
            }
        
        except Exception as e:
            logger.debug(f"Error creating QA pair: {e}")
            return None
    
    async def save_datasets(self) -> Tuple[str, str, str]:
        """Сохраняет датасеты в разных форматах."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 1. JSON датасет (полные диалоги)
        json_file = f"data/natasha_dialogs_dataset_{timestamp}.json"
        Path("data").mkdir(exist_ok=True)
        
        dataset_json = {
            'timestamp': timestamp,
            'natasha_id': NATASHA_ID,
            'total_dialogs': len(self.dialogs),
            'total_qa_pairs': len(self.qa_pairs),
            'statistics': self.statistics,
            'dialogs': self.dialogs
        }
        
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(dataset_json, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✅ Saved JSON dataset to: {json_file}")
        
        # 2. JSONL датасет для fine-tuning (OpenAI format)
        jsonl_file = f"data/natasha_finetuning_{timestamp}.jsonl"
        
        with open(jsonl_file, 'w', encoding='utf-8') as f:
            for qa_pair in self.qa_pairs:
                # Формат для OpenAI fine-tuning
                training_example = {
                    "messages": [
                        {
                            "role": "user",
                            "content": qa_pair['prompt']
                        },
                        {
                            "role": "assistant",
                            "content": qa_pair['completion']
                        }
                    ]
                }
                f.write(json.dumps(training_example, ensure_ascii=False) + '\n')
        
        logger.info(f"✅ Saved JSONL dataset to: {jsonl_file}")
        
        # 3. CSV датасет для анализа
        csv_file = f"data/natasha_dialogs_{timestamp}.csv"
        
        import csv
        with open(csv_file, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(
                f,
                fieldnames=['date', 'channel', 'user_name', 'user_message', 'natasha_response', 'message_length']
            )
            writer.writeheader()
            
            for dialog in self.dialogs:
                writer.writerow({
                    'date': dialog['date'],
                    'channel': dialog['channel'],
                    'user_name': dialog.get('user_name', 'Unknown'),
                    'user_message': dialog['user_message'][:100] + '...' if len(dialog['user_message']) > 100 else dialog['user_message'],
                    'natasha_response': dialog['natasha_response'][:100] + '...' if len(dialog['natasha_response']) > 100 else dialog['natasha_response'],
                    'message_length': len(dialog['natasha_response'])
                })
        
        logger.info(f"✅ Saved CSV dataset to: {csv_file}")
        
        return json_file, jsonl_file, csv_file
    
    def print_statistics(self):
        """Выводит статистику."""
        logger.info(f"\n{'='*70}")
        logger.info("DATASET STATISTICS")
        logger.info(f"{'='*70}")
        logger.info(f"Total channels processed: {self.statistics['total_channels']}")
        logger.info(f"Total messages: {self.statistics['total_messages']}")
        logger.info(f"Natasha's messages: {self.statistics['natasha_messages']}")
        logger.info(f"User messages: {self.statistics['user_messages']}")
        logger.info(f"Valid dialogs: {self.statistics['valid_dialogs']}")
        logger.info(f"QA pairs for fine-tuning: {len(self.qa_pairs)}")
        logger.info(f"\nChannels processed:")
        for channel in self.statistics['channels_processed']:
            logger.info(f"  - {channel}")
        logger.info(f"{'='*70}\n")
    
    def print_sample_dialogs(self, count: int = 3):
        """Выводит примеры диалогов."""
        logger.info(f"\n{'='*70}")
        logger.info("SAMPLE DIALOGS")
        logger.info(f"{'='*70}\n")
        
        for i, dialog in enumerate(self.dialogs[:count]):
            logger.info(f"Dialog #{i+1} - {dialog['channel']} ({dialog['date']})")
            logger.info("-" * 70)
            
            for msg in dialog['context']:
                role = "🔥 НАТАША" if msg['is_natasha'] else f"👤 {msg['sender_name']}"
                text = msg['text'][:200] + "..." if len(msg['text']) > 200 else msg['text']
                logger.info(f"{role}: {text}")
            
            logger.info("")


async def main():
    """Главная функция."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Collect Natasha's dialogs for model fine-tuning"
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=2000,
        help='Limit messages per channel (default: 2000)'
    )
    parser.add_argument(
        '--sample',
        type=int,
        default=3,
        help='Show N sample dialogs (default: 3)'
    )
    
    args = parser.parse_args()
    
    print("\n" + "="*70)
    print("NATASHA DIALOGS DATASET COLLECTION")
    print("="*70 + "\n")
    
    collector = NatashaDialogsCollector()
    
    try:
        await collector.client.connect()
        
        if not await collector.client.is_user_authorized():
            logger.error("❌ Not authorized!")
            return
        
        logger.info("✅ Connected to Telegram\n")
        
        # Собираем диалоги
        await collector.collect_from_all_channels(limit_per_channel=args.limit)
        
        # Сохраняем датасеты
        json_file, jsonl_file, csv_file = await collector.save_datasets()
        
        # Выводим статистику
        collector.print_statistics()
        
        # Выводим примеры
        collector.print_sample_dialogs(count=args.sample)
        
        logger.info(f"\n{'='*70}")
        logger.info("FILES CREATED")
        logger.info(f"{'='*70}")
        logger.info(f"1. JSON (full dialogs): {json_file}")
        logger.info(f"2. JSONL (fine-tuning): {jsonl_file}")
        logger.info(f"3. CSV (analysis): {csv_file}")
        logger.info(f"{'='*70}\n")
        
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
    
    finally:
        await collector.client.disconnect()
        logger.info("👋 Disconnected")


if __name__ == "__main__":
    asyncio.run(main())
