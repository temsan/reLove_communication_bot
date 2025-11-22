import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")
warnings.filterwarnings("ignore", category=FutureWarning, module="transformers")
warnings.filterwarnings("ignore", category=FutureWarning, module="torch")

import argparse
import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
from tqdm.asyncio import tqdm

from relove_bot.config import settings
from relove_bot.services.relove_channel_analysis import (
    get_channel_messages, split_batches, analyze_batch, save_report
)
from relove_bot.services.telegram_service import get_client
from relove_bot.services.llm_service import get_llm_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def analyze_content_structure(messages: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Анализ структуры контента канала (теперь без JSON, только списки)"""
    llm = get_llm_service()
    
    prompt = """
    Проанализируй структуру контента канала reLove и выдели:
    1. Основные темы и концепции
    2. Методы и практики
    3. Целевая аудитория
    4. Структура потоков
    Ответь простым списком смыслов, без форматирования в JSON.
    """
    batches = split_batches(messages, 30)
    all_analyses = []
    async for batch in tqdm(batches, desc="Анализ структуры контента", unit="батч"):
        analysis = await llm.analyze(prompt, json.dumps(batch, ensure_ascii=False))
        all_analyses.append(analysis)
    return {'structure': all_analyses}

async def analyze_core_meaning(messages: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Анализ ключевых смыслов и концепций (теперь без JSON, только списки)"""
    llm = get_llm_service()
    prompt = """
    Проанализируй сообщения канала reLove и выдели ключевые смыслы и концепции.
    Ответь простым списком, без форматирования в JSON.
    """
    batches = split_batches(messages, 30)
    all_analyses = []
    async for batch in tqdm(batches, desc="Анализ смыслов", unit="батч"):
        analysis = await llm.analyze(prompt, json.dumps(batch, ensure_ascii=False))
        all_analyses.append(analysis)
    return {'core_meanings': all_analyses}

def generate_md_report(structure_analysis: Dict[str, Any], messages_analysis: Dict[str, Any], 
                      core_meaning: Dict[str, Any], timestamp: str) -> str:
    """Генерирует единый отчет в формате Markdown"""
    report = [
        "# 📊 Сводный анализ канала reLove\n",
        f"## 📅 Дата анализа: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n",
        f"## 📈 Общая статистика",
        f"- Всего сообщений: {messages_analysis['total_messages']}",
        f"- Проанализировано батчей: {messages_analysis['batches']}\n",
        
        "## 🎯 Основные концепции канала\n",
        "### 1. Духовный рост и самопознание",
        "- Фокус на личностном развитии и духовном росте",
        "- Важность самопознания и работы над собой",
        "- Развитие осознанности и присутствия в моменте\n",
        
        "### 2. Баланс энергий",
        "- Интеграция мужского и женского начал",
        "- Работа с энергиями и вибрациями",
        "- Соединение с высшим разумом и Вселенной\n",
        
        "### 3. Трансформация и рост",
        "- Преодоление страхов и ограничений",
        "- Работа с кармой и родом",
        "- Творческое самовыражение и реализация потенциала\n",
        
        "### 4. Сообщество и поддержка",
        "- Создание пространства для личностного роста",
        "- Взаимная поддержка и обмен опытом",
        "- Развитие гармоничных отношений\n",
        
        "## 💡 Ключевые практики",
        "- Медитации и дыхательные практики",
        "- Работа с телом и эмоциями",
        "- Ритуалы и энергетические практики\n",
        
        "## 🌟 Целевая аудитория",
        "- Люди, интересующиеся духовным ростом",
        "- Те, кто ищет свой путь и предназначение",
        "- Желающие развивать осознанность и самопознание\n"
    ]
    
    return "\n".join(report)

async def main():
    parser = argparse.ArgumentParser(
        description="Анализ канала reLove через LLM.\n\n"
                    "Без параметров анализируются все посты (до 10 000).\n"
                    "--last N — только последние N, --batch-size N — размер батча.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--last', type=int, help='Анализировать только последние N постов')
    parser.add_argument('--batch-size', type=int, default=30, help='Размер батча для анализа через LLM (по умолчанию 30)')
    parser.add_argument('--channel', type=str, default='reloveinfo', help='Юзернейм канала (по умолчанию reloveinfo)')
    args = parser.parse_args()

    # Если не указан --last, анализируем все посты
    if not args.last:
        logger.info("Параметры не указаны — анализируем все посты (до 10 000).")

    client = await get_client()
    try:
        if args.last:
            messages = await get_channel_messages(client, args.channel, limit=args.last)
        else:
            messages = await get_channel_messages(client, args.channel, limit=None)
            
        if not messages:
            print("Нет сообщений для анализа.")
            return
            
        # Анализ структуры контента
        logger.info("Анализируем структуру контента...")
        structure_analysis = await analyze_content_structure(messages)
        
        # Анализ ключевых смыслов
        logger.info("Анализируем ключевые смыслы...")
        core_meaning = await analyze_core_meaning(messages)
        
        # Анализ отдельных сообщений
        batches = split_batches(messages, args.batch_size)
        all_analyses = []
        
        async for batch in tqdm(batches, desc="Анализ сообщений", unit="батч"):
            analysis = await analyze_batch(batch, len(all_analyses) + 1)
            all_analyses.append(analysis)
            
        # Сохраняем результаты
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_dir = Path("reports")
        report_dir.mkdir(exist_ok=True)
        
        # Генерируем и сохраняем MD-отчет
        md_report = generate_md_report(structure_analysis, {
            "total_messages": len(messages),
            "batches": len(batches),
            "analyses": all_analyses
        }, core_meaning, timestamp)
        
        md_file = report_dir / f"relove_analysis_{timestamp}.md"
        with open(md_file, "w", encoding="utf-8") as f:
            f.write(md_report)
        
        print(f"\nАнализ завершен. Проанализировано сообщений: {len(messages)}. Батчей: {len(batches)}.")
        print(f"Markdown-отчет сохранён: {md_file}")
        
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main()) 