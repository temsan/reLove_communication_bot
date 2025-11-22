"""
Скрипт для интеграции стиля Наташи в промпты бота.
Читает анализ и обновляет prompts.py
"""
import json
import sys
from pathlib import Path
from typing import Dict

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_latest_analysis() -> Dict:
    """Загружает последний анализ стиля"""
    data_dir = Path("data")
    
    # Находим последний файл анализа
    analysis_files = list(data_dir.glob("natasha_style_analysis_*.json"))
    
    if not analysis_files:
        logger.error("No analysis files found!")
        return {}
    
    latest_file = max(analysis_files, key=lambda p: p.stat().st_mtime)
    logger.info(f"Loading analysis from: {latest_file}")
    
    with open(latest_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def generate_enhanced_prompts(analysis: Dict) -> Dict[str, str]:
    """Генерирует улучшенные промпты на основе анализа"""
    
    language_style = analysis.get('language_style', {})
    dialog_patterns = analysis.get('dialog_patterns', {})
    
    # Извлекаем ключевые элементы
    key_phrases = language_style.get('key_phrases', [])
    provocative_questions = dialog_patterns.get('provocative_questions', [])
    pattern_breaking = dialog_patterns.get('pattern_breaking', [])
    
    # Формируем примеры для промптов
    phrases_text = "\n".join([f"- {p}" for p in key_phrases[:10]])
    questions_text = "\n".join([f"- {q}" for q in provocative_questions[:10]])
    techniques_text = "\n".join([f"- {t}" for t in pattern_breaking[:5]])
    
    # Генерируем промпты
    prompts = {}
    
    # 1. Провокативная сессия
    prompts['PROVOCATIVE_SESSION'] = f"""Ты - Наташа Волкош, провокативный терапевт.

ТВОЙ СТИЛЬ (из реальных постов и диалогов):
{phrases_text}

ПРОВОКАТИВНЫЕ ВОПРОСЫ:
{questions_text}

ТЕХНИКИ ВСКРЫТИЯ ПАТТЕРНОВ:
{techniques_text}

ПРАВИЛА:
1. Говори прямо, без обиняков
2. Вскрывай паттерны и самообман
3. Используй провокацию для пробуждения
4. Работай с сопротивлением напрямую
5. Не жалей, но поддерживай
6. Веди к корню проблемы

Задавай короткие, точные вопросы. Не давай готовых ответов.
"""
    
    # 2. Анализ сообщений
    prompts['MESSAGE_ANALYSIS'] = f"""Проанализируй сообщение пользователя в стиле Наташи Волкош.

СТИЛЬ АНАЛИЗА:
{phrases_text}

Выдели:
1. Паттерны самообмана
2. Сопротивление
3. Корневую проблему
4. Точку роста

Будь прямой и провокативной.
"""
    
    # 3. Обратная связь
    prompts['FEEDBACK'] = f"""Дай обратную связь в стиле Наташи Волкош.

ТВОИ ФРАЗЫ:
{phrases_text}

ПРОВОКАТИВНЫЕ ВОПРОСЫ:
{questions_text}

Будь честной, прямой, провокативной. Веди к осознанию.
"""
    
    return prompts


def update_prompts_file(enhanced_prompts: Dict[str, str]):
    """Обновляет файл prompts.py"""
    prompts_file = Path("relove_bot/services/prompts.py")
    
    if not prompts_file.exists():
        logger.error(f"Prompts file not found: {prompts_file}")
        return
    
    # Читаем текущий файл
    with open(prompts_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Создаем бэкап
    backup_file = prompts_file.with_suffix('.py.backup')
    with open(backup_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    logger.info(f"✅ Created backup: {backup_file}")
    
    # Добавляем новые промпты в конец файла
    additions = "\n\n# ============================================\n"
    additions += "# ENHANCED PROMPTS (from real Natasha's style)\n"
    additions += "# ============================================\n\n"
    
    for name, prompt in enhanced_prompts.items():
        additions += f'{name}_ENHANCED = """{prompt}"""\n\n'
    
    # Записываем обновленный файл
    with open(prompts_file, 'w', encoding='utf-8') as f:
        f.write(content + additions)
    
    logger.info(f"✅ Updated prompts file: {prompts_file}")
    logger.info(f"   Added {len(enhanced_prompts)} enhanced prompts")


def main():
    """Главная функция"""
    print("\n" + "="*70)
    print("INTEGRATE NATASHA'S STYLE INTO PROMPTS")
    print("="*70 + "\n")
    
    # 1. Загружаем анализ
    logger.info("Step 1: Loading analysis...")
    analysis = load_latest_analysis()
    
    if not analysis:
        logger.error("No analysis data found!")
        return
    
    logger.info("✅ Analysis loaded")
    
    # 2. Генерируем промпты
    logger.info("\nStep 2: Generating enhanced prompts...")
    enhanced_prompts = generate_enhanced_prompts(analysis)
    
    logger.info(f"✅ Generated {len(enhanced_prompts)} prompts")
    
    # 3. Показываем превью
    logger.info("\nStep 3: Preview of enhanced prompts:")
    for name, prompt in enhanced_prompts.items():
        logger.info(f"\n{name}:")
        logger.info(prompt[:200] + "...")
    
    # 4. Обновляем файл
    logger.info("\nStep 4: Updating prompts.py...")
    update_prompts_file(enhanced_prompts)
    
    logger.info("\n" + "="*70)
    logger.info("✅ INTEGRATION COMPLETE")
    logger.info("="*70)
    logger.info("\nEnhanced prompts added to relove_bot/services/prompts.py")
    logger.info("Backup created: relove_bot/services/prompts.py.backup")
    logger.info("\n💡 Test the bot to see the new style in action!")


if __name__ == "__main__":
    main()
