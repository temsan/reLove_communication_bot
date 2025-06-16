import json
import os
from pathlib import Path
from datetime import datetime
import asyncio
from relove_bot.services.llm_service import llm_service

def find_latest_report(reports_dir: str = "reports") -> Path:
    files = list(Path(reports_dir).glob("relove_full_analysis_*.json"))
    if not files:
        raise FileNotFoundError("Нет файлов анализа в reports/")
    return max(files, key=os.path.getmtime)

def extract_all_analyses(report_path: Path) -> str:
    with open(report_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    analyses = []
    for batch in data.get("analyses", []):
        analysis = batch.get("analysis", "")
        if isinstance(analysis, dict):
            analysis = json.dumps(analysis, ensure_ascii=False, indent=2)
        analyses.append(str(analysis))
    return "\n\n".join(analyses)

async def main():
    print("Ищем последний файл анализа...")
    report_path = find_latest_report()
    print(f"Используем файл: {report_path}")
    all_analyses = extract_all_analyses(report_path)
    print(f"Собрано {len(all_analyses)} символов смыслов из всех батчей.")
    
    prompt = f"""
    На основе анализа батчей постов канала reLove:
    ---
    {all_analyses}
    ---
    Суммируй и структурируй основные смыслы, концепции, вайб, стиль, ключевые термины, ценности, целевую аудиторию и рекомендации для проектирования чат-бота и его промптов. Оформи результат в виде markdown-отчёта для команды разработки.
    """
    print("Отправляем запрос в LLM...")
    summary = await llm_service.analyze_text(prompt)
    
    md_path = Path("reports") / f"relove_channel_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(summary)
    print(f"Сводка сохранена в {md_path}")
    print("\n---\n")
    print(summary)

if __name__ == "__main__":
    asyncio.run(main()) 