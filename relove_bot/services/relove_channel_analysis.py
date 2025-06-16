import logging
from typing import List, Dict, Any, Optional
from telethon import TelegramClient
from telethon.errors import ChannelPrivateError
from datetime import datetime
import json
from pathlib import Path

from relove_bot.services.llm_service import llm_service

logger = logging.getLogger(__name__)

async def get_channel_messages(client: TelegramClient, channel_username: str, limit: Optional[int] = None, max_messages: int = 10000) -> List[Dict[str, Any]]:
    """Получает сообщения из канала (limit=N или все до max_messages)"""
    try:
        channel = await client.get_entity(channel_username)
        messages = []
        async for message in client.iter_messages(channel, limit=limit or max_messages):
            if message.text:
                message_data = {
                    'id': message.id,
                    'date': message.date.isoformat(),
                    'text': message.text,
                    'views': message.views,
                    'forwards': message.forwards
                }
                if message.reactions:
                    message_data['reactions'] = [
                        {
                            'emoji': reaction.emoji,
                            'count': reaction.count
                        } for reaction in message.reactions.reactions
                    ] if hasattr(message.reactions, 'reactions') else []
                messages.append(message_data)
        logger.info(f"Получено сообщений: {len(messages)}")
        return messages
    except ChannelPrivateError:
        logger.error(f"Канал {channel_username} является приватным")
        return []
    except Exception as e:
        logger.error(f"Ошибка при получении сообщений из канала {channel_username}: {e}")
        return []

def split_batches(messages: List[Dict[str, Any]], batch_size: int) -> List[List[Dict[str, Any]]]:
    """Разбивает список сообщений на батчи"""
    return [messages[i:i+batch_size] for i in range(0, len(messages), batch_size)]

async def analyze_batch(messages: List[Dict[str, Any]], batch_num: int) -> Dict[str, Any]:
    """Анализирует батч сообщений через LLM"""
    combined_text = "\n\n".join([
        f"Сообщение от {msg['date']} (id={msg['id']}):\n{msg['text']}"
        for msg in messages
    ])
    prompt = f"""
    Проанализируй этот батч контента канала reLove и определи:
    1. Основные темы и концепции
    2. Стиль и тон общения
    3. Ключевые термины и их значения
    4. Эмоциональный окрас контента
    5. Целевую аудиторию
    6. Основные ценности и принципы
    \nКонтент батча #{batch_num}:\n{combined_text}\n\nПредставь результат в структурированном виде.
    """
    try:
        analysis = await llm_service.analyze_text(prompt)
        return {
            'batch_num': batch_num,
            'messages_count': len(messages),
            'analysis': analysis
        }
    except Exception as e:
        logger.error(f"Ошибка при анализе батча {batch_num}: {e}")
        return {
            'batch_num': batch_num,
            'messages_count': len(messages),
            'analysis': f'Ошибка: {e}'
        }

def save_report(analyses: List[Dict[str, Any]], total_messages: int, batches: int, report_prefix: str = "relove_analysis") -> Path:
    """Сохраняет результаты анализа в файл и возвращает путь"""
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = reports_dir / f"{report_prefix}_{timestamp}.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump({
            'total_messages': total_messages,
            'batches': batches,
            'analyses': analyses,
            'timestamp': datetime.utcnow().isoformat()
        }, f, ensure_ascii=False, indent=2)
    logger.info(f"Анализ завершен. Результаты сохранены в {report_file}")
    return report_file 