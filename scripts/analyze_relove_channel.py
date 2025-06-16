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
    """Анализ структуры контента канала"""
    llm = get_llm_service()
    
    prompt = """
    Проанализируй структуру контента канала reLove и выдели:
    
    1. ОСНОВНЫЕ ТЕМЫ И КОНЦЕПЦИИ:
    - Ключевые темы и идеи
    - Основные концепции и метафоры
    - Ценности и принципы
    
    2. МЕТОДЫ И ПРАКТИКИ:
    - Техники и упражнения
    - Процессы трансформации
    - Групповые практики
    
    3. ЦЕЛЕВАЯ АУДИТОРИЯ:
    - Уровни развития
    - Потребности и запросы
    - Точки роста
    
    4. СТРУКТУРА ПОТОКОВ:
    - Этапы развития
    - Ключевые практики
    - Ожидаемые результаты
    
    Ответь в формате JSON:
    {
        "themes": {
            "key_themes": ["список ключевых тем"],
            "concepts": ["основные концепции"],
            "values": ["ценности сообщества"]
        },
        "practices": {
            "techniques": ["список техник"],
            "processes": ["процессы трансформации"],
            "group_practices": ["групповые практики"]
        },
        "audience": {
            "development_levels": ["уровни развития"],
            "needs": ["потребности"],
            "growth_points": ["точки роста"]
        },
        "streams": {
            "stages": ["этапы развития"],
            "key_practices": ["ключевые практики"],
            "expected_results": ["ожидаемые результаты"]
        }
    }
    """
    
    # Анализируем сообщения батчами
    batches = split_batches(messages, 30)
    all_analyses = []
    
    async for batch in tqdm(batches, desc="Анализ структуры контента", unit="батч"):
        analysis = await llm.analyze(prompt, json.dumps(batch, ensure_ascii=False))
        all_analyses.append(analysis)
    
    # Объединяем результаты
    combined_analysis = {
        "themes": {
            "key_themes": [],
            "concepts": [],
            "values": []
        },
        "practices": {
            "techniques": [],
            "processes": [],
            "group_practices": []
        },
        "audience": {
            "development_levels": [],
            "needs": [],
            "growth_points": []
        },
        "streams": {
            "stages": [],
            "key_practices": [],
            "expected_results": []
        }
    }
    
    # Агрегируем результаты
    for analysis in all_analyses:
        if isinstance(analysis, dict):
            for category in combined_analysis:
                for key in combined_analysis[category]:
                    if key in analysis.get(category, {}):
                        combined_analysis[category][key].extend(analysis[category][key])
    
    # Удаляем дубликаты
    for category in combined_analysis:
        for key in combined_analysis[category]:
            combined_analysis[category][key] = list(set(combined_analysis[category][key]))
    
    return combined_analysis

async def analyze_core_meaning(messages: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Анализ ключевых смыслов и концепций"""
    llm = get_llm_service()
    
    prompt = """
    Проанализируй сообщения канала reLove и выдели ключевые смыслы и концепции:
    
    1. КЛЮЧЕВЫЕ СМЫСЛЫ:
    - Основные идеи и посылы
    - Глубинные ценности
    - Метафоры и образы
    
    2. КОНЦЕПЦИИ РАЗВИТИЯ:
    - Этапы трансформации
    - Ключевые практики
    - Ожидаемые результаты
    
    3. МЕТОДОЛОГИЯ:
    - Подходы к работе
    - Техники и инструменты
    - Процессы и последовательности
    
    4. ЦЕННОСТИ И ПРИНЦИПЫ:
    - Базовые ценности
    - Этические принципы
    - Правила взаимодействия
    
    Ответь в формате JSON:
    {
        "core_meanings": {
            "key_ideas": ["основные идеи"],
            "deep_values": ["глубинные ценности"],
            "metaphors": ["метафоры и образы"]
        },
        "development": {
            "transformation_stages": ["этапы трансформации"],
            "key_practices": ["ключевые практики"],
            "expected_outcomes": ["ожидаемые результаты"]
        },
        "methodology": {
            "approaches": ["подходы к работе"],
            "techniques": ["техники и инструменты"],
            "processes": ["процессы и последовательности"]
        },
        "values": {
            "core_values": ["базовые ценности"],
            "principles": ["этические принципы"],
            "interaction_rules": ["правила взаимодействия"]
        }
    }
    """
    
    # Анализируем сообщения батчами
    batches = split_batches(messages, 30)
    all_analyses = []
    
    async for batch in tqdm(batches, desc="Анализ смыслов", unit="батч"):
        analysis = await llm.analyze(prompt, json.dumps(batch, ensure_ascii=False))
        all_analyses.append(analysis)
    
    # Объединяем результаты
    combined_analysis = {
        "core_meanings": {
            "key_ideas": [],
            "deep_values": [],
            "metaphors": []
        },
        "development": {
            "transformation_stages": [],
            "key_practices": [],
            "expected_outcomes": []
        },
        "methodology": {
            "approaches": [],
            "techniques": [],
            "processes": []
        },
        "values": {
            "core_values": [],
            "principles": [],
            "interaction_rules": []
        }
    }
    
    # Агрегируем результаты
    for analysis in all_analyses:
        if isinstance(analysis, dict):
            for category in combined_analysis:
                for key in combined_analysis[category]:
                    if key in analysis.get(category, {}):
                        combined_analysis[category][key].extend(analysis[category][key])
    
    # Удаляем дубликаты
    for category in combined_analysis:
        for key in combined_analysis[category]:
            combined_analysis[category][key] = list(set(combined_analysis[category][key]))
    
    return combined_analysis

def generate_md_report(structure_analysis: Dict[str, Any], messages_analysis: Dict[str, Any], 
                      core_meaning: Dict[str, Any], timestamp: str) -> str:
    """Генерирует отчет в формате Markdown"""
    report = [
        "# 📊 Анализ канала reLove\n",
        f"## 📅 Дата анализа: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n",
        f"## 📈 Общая статистика",
        f"- Всего сообщений: {messages_analysis['total_messages']}",
        f"- Проанализировано батчей: {messages_analysis['batches']}\n",
        
        "## 🎯 Ключевые смыслы и концепции\n"
    ]
    
    # Добавляем анализ ключевых смыслов
    for category, items in core_meaning.items():
        report.append(f"### {category.replace('_', ' ').title()}")
        for key, values in items.items():
            if values:  # Добавляем только непустые списки
                report.append(f"\n#### {key.replace('_', ' ').title()}")
                for value in values:
                    report.append(f"- {value}")
        report.append("")
    
    report.append("## 🎯 Структура контента\n")
    
    # Добавляем анализ структуры
    for category, items in structure_analysis.items():
        report.append(f"### {category.title()}")
        for key, values in items.items():
            if values:  # Добавляем только непустые списки
                report.append(f"\n#### {key.replace('_', ' ').title()}")
                for value in values:
                    report.append(f"- {value}")
        report.append("")
    
    # Добавляем анализ сообщений
    report.append("## 📝 Анализ сообщений\n")
    for i, batch in enumerate(messages_analysis['analyses'], 1):
        report.append(f"### Батч {i}")
        if isinstance(batch.get('analysis'), dict):
            for key, value in batch['analysis'].items():
                report.append(f"\n#### {key.replace('_', ' ').title()}")
                if isinstance(value, list):
                    for item in value:
                        report.append(f"- {item}")
                else:
                    report.append(f"- {value}")
        else:
            report.append(batch.get('analysis', 'Нет данных'))
        report.append("")
    
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
        
        # Сохраняем анализ структуры
        structure_file = report_dir / f"relove_structure_analysis_{timestamp}.json"
        with open(structure_file, "w", encoding="utf-8") as f:
            json.dump(structure_analysis, f, ensure_ascii=False, indent=2)
            
        # Сохраняем анализ ключевых смыслов
        meaning_file = report_dir / f"relove_core_meaning_{timestamp}.json"
        with open(meaning_file, "w", encoding="utf-8") as f:
            json.dump(core_meaning, f, ensure_ascii=False, indent=2)
            
        # Сохраняем анализ сообщений
        messages_file = report_dir / f"relove_messages_analysis_{timestamp}.json"
        with open(messages_file, "w", encoding="utf-8") as f:
            json.dump({
                "total_messages": len(messages),
                "batches": len(batches),
                "analyses": all_analyses
            }, f, ensure_ascii=False, indent=2)
            
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
        print(f"Результаты сохранены в:")
        print(f"- Анализ структуры: {structure_file}")
        print(f"- Анализ ключевых смыслов: {meaning_file}")
        print(f"- Анализ сообщений: {messages_file}")
        print(f"- Markdown отчет: {md_file}")
        
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main()) 