"""
Анализ стиля Наташи Волкош через LLM для кристаллизации паттернов.

Задачи:
1. Анализ диалогов с reply-цепочками
2. Выявление ключевых паттернов общения
3. Извлечение метафор и концептов
4. Кристаллизация стиля для промптов
"""
import asyncio
import json
import sys
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from relove_bot.config import settings
from relove_bot.services.llm_service import LLMService
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/natasha_style_analysis.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


STYLE_ANALYSIS_PROMPT = """
Ты — эксперт по анализу стиля общения и коммуникационных паттернов.

Проанализируй диалоги Наташи Волкош и выяви:

1. **ЯЗЫКОВЫЕ ПАТТЕРНЫ**:
   - Типичные фразы и обороты
   - Длина предложений (короткие/длинные)
   - Использование вопросов vs утверждений
   - Эмоциональная окраска (директивная, поддерживающая, провокативная)

2. **МЕТАФОРЫ И КОНЦЕПТЫ**:
   - Повторяющиеся метафоры (свет/тьма, смерть/жизнь, война/мир)
   - Духовные/эзотерические концепты
   - Психологические термины
   - Уникальные выражения

3. **СТРУКТУРА ДИАЛОГА**:
   - Как начинает диалог
   - Как задаёт вопросы (прямые/косвенные)
   - Как даёт обратную связь
   - Как завершает диалог

4. **ПРОВОКАТИВНЫЕ ТЕХНИКИ**:
   - Прямая конфронтация
   - Переворот перспективы
   - Абсурдные метафоры
   - Создание дискомфорта

5. **ЭМОЦИОНАЛЬНАЯ ДИНАМИКА**:
   - Удар → Поддержка
   - Жёсткость → Тепло
   - Вызов → Принятие

Проанализируй следующие диалоги и выдай структурированный анализ.

ДИАЛОГИ:
{dialogs}

ФОРМАТ ОТВЕТА (JSON):
{{
  "language_patterns": {{
    "typical_phrases": ["список типичных фраз"],
    "sentence_structure": "описание структуры предложений",
    "question_style": "стиль вопросов",
    "emotional_tone": "эмоциональный тон"
  }},
  "metaphors_concepts": {{
    "recurring_metaphors": ["повторяющиеся метафоры"],
    "spiritual_concepts": ["духовные концепты"],
    "psychological_terms": ["психологические термины"],
    "unique_expressions": ["уникальные выражения"]
  }},
  "dialog_structure": {{
    "opening": "как начинает",
    "questioning": "как задаёт вопросы",
    "feedback": "как даёт обратную связь",
    "closing": "как завершает"
  }},
  "provocative_techniques": {{
    "confrontation": ["примеры конфронтации"],
    "perspective_flip": ["примеры переворота перспективы"],
    "absurd_metaphors": ["абсурдные метафоры"],
    "discomfort_creation": ["создание дискомфорта"]
  }},
  "emotional_dynamics": {{
    "hit_support": ["примеры удар→поддержка"],
    "harshness_warmth": ["примеры жёсткость→тепло"],
    "challenge_acceptance": ["примеры вызов→принятие"]
  }},
  "key_insights": ["ключевые инсайты о стиле"]
}}
"""


PATTERN_EXTRACTION_PROMPT = """
На основе анализа стиля Наташи, извлеки конкретные паттерны для интеграции в промпты бота.

АНАЛИЗ СТИЛЯ:
{style_analysis}

ЗАДАЧА:
Создай структурированный набор паттернов, которые можно использовать в промптах:

1. **ФРАЗЫ-ТРИГГЕРЫ** — короткие фразы для провокации
2. **ВОПРОСЫ-ЛОВУШКИ** — вопросы, ведущие к осознанию
3. **МЕТАФОРЫ-ИНСТРУМЕНТЫ** — метафоры для трансформации
4. **ТЕХНИКИ ПЕРЕВОРОТА** — способы перевернуть перспективу
5. **ПОДДЕРЖИВАЮЩИЕ ФРАЗЫ** — фразы после жёсткого вскрытия

ФОРМАТ ОТВЕТА (JSON):
{{
  "trigger_phrases": [
    {{"phrase": "фраза", "context": "когда использовать", "example": "пример из диалога"}}
  ],
  "trap_questions": [
    {{"question": "вопрос", "purpose": "цель вопроса", "example": "пример"}}
  ],
  "metaphor_tools": [
    {{"metaphor": "метафора", "meaning": "значение", "usage": "как использовать"}}
  ],
  "flip_techniques": [
    {{"technique": "техника", "description": "описание", "example": "пример"}}
  ],
  "support_phrases": [
    {{"phrase": "фраза", "timing": "когда использовать", "example": "пример"}}
  ]
}}
"""


class NatashaStyleAnalyzer:
    """Анализатор стиля Наташи через LLM."""
    
    def __init__(self):
        self.llm = LLMService()
    
    def load_dialogs(self, json_path: str) -> List[Dict[str, Any]]:
        """Загружает диалоги из JSON."""
        logger.info(f"Loading dialogs from {json_path}")
        
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Фильтруем только диалоги с reply-цепочками
        dialogs_with_replies = [
            d for d in data.get('dialogs', [])
            if d.get('has_reply_chain', False)
        ]
        
        logger.info(f"Loaded {len(dialogs_with_replies)} dialogs with reply chains")
        return dialogs_with_replies
    
    def format_dialog_for_analysis(self, dialog: Dict[str, Any]) -> str:
        """Форматирует диалог для анализа."""
        lines = [
            f"=== ДИАЛОГ: {dialog['chat']} ({dialog['date']}) ==="
        ]
        
        for msg in dialog['context']:
            role = "🔥 НАТАША" if msg['is_natasha'] else f"👤 {msg['sender_name']}"
            lines.append(f"{role}: {msg['text']}")
        
        lines.append("")
        return "\n".join(lines)
    
    async def analyze_style(
        self,
        dialogs: List[Dict[str, Any]],
        sample_size: int = 50
    ) -> Dict[str, Any]:
        """Анализирует стиль через LLM."""
        logger.info(f"Analyzing style from {sample_size} dialogs...")
        
        # Берём sample диалогов
        sample_dialogs = dialogs[:sample_size]
        
        # Форматируем для анализа
        formatted_dialogs = "\n\n".join([
            self.format_dialog_for_analysis(d)
            for d in sample_dialogs
        ])
        
        # Анализируем через LLM
        prompt = STYLE_ANALYSIS_PROMPT.format(dialogs=formatted_dialogs)
        
        logger.info("Sending to LLM for style analysis...")
        response = await self.llm.generate_text(
            prompt=prompt,
            max_tokens=4000,
            temperature=0.7
        )
        
        # Парсим JSON
        try:
            style_analysis = json.loads(response)
            logger.info("✅ Style analysis completed")
            return style_analysis
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            logger.error(f"Response: {response}")
            return {}
    
    async def extract_patterns(
        self,
        style_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Извлекает конкретные паттерны для промптов."""
        logger.info("Extracting patterns for prompts...")
        
        prompt = PATTERN_EXTRACTION_PROMPT.format(
            style_analysis=json.dumps(style_analysis, ensure_ascii=False, indent=2)
        )
        
        logger.info("Sending to LLM for pattern extraction...")
        response = await self.llm.generate_text(
            prompt=prompt,
            max_tokens=4000,
            temperature=0.7
        )
        
        # Парсим JSON
        try:
            patterns = json.loads(response)
            logger.info("✅ Pattern extraction completed")
            return patterns
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            logger.error(f"Response: {response}")
            return {}
    
    def save_results(
        self,
        style_analysis: Dict[str, Any],
        patterns: Dict[str, Any]
    ) -> tuple[str, str]:
        """Сохраняет результаты анализа."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Сохраняем анализ стиля
        style_file = f"data/natasha_style_analysis_{timestamp}.json"
        with open(style_file, 'w', encoding='utf-8') as f:
            json.dump(style_analysis, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✅ Saved style analysis to: {style_file}")
        
        # Сохраняем паттерны
        patterns_file = f"data/natasha_patterns_{timestamp}.json"
        with open(patterns_file, 'w', encoding='utf-8') as f:
            json.dump(patterns, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✅ Saved patterns to: {patterns_file}")
        
        # Создаём markdown-отчёт
        report_file = f"data/natasha_style_report_{timestamp}.md"
        self._create_markdown_report(
            style_analysis,
            patterns,
            report_file
        )
        
        logger.info(f"✅ Saved report to: {report_file}")
        
        return style_file, patterns_file, report_file
    
    def _create_markdown_report(
        self,
        style_analysis: Dict[str, Any],
        patterns: Dict[str, Any],
        output_file: str
    ):
        """Создаёт markdown-отчёт."""
        lines = [
            "# Анализ стиля Наташи Волкош",
            "",
            "## 1. Языковые паттерны",
            ""
        ]
        
        # Языковые паттерны
        lang_patterns = style_analysis.get('language_patterns', {})
        if lang_patterns:
            lines.append("### Типичные фразы:")
            for phrase in lang_patterns.get('typical_phrases', []):
                lines.append(f"- {phrase}")
            lines.append("")
            
            lines.append(f"**Структура предложений**: {lang_patterns.get('sentence_structure', 'N/A')}")
            lines.append(f"**Стиль вопросов**: {lang_patterns.get('question_style', 'N/A')}")
            lines.append(f"**Эмоциональный тон**: {lang_patterns.get('emotional_tone', 'N/A')}")
            lines.append("")
        
        # Метафоры и концепты
        lines.append("## 2. Метафоры и концепты")
        lines.append("")
        
        metaphors = style_analysis.get('metaphors_concepts', {})
        if metaphors:
            lines.append("### Повторяющиеся метафоры:")
            for m in metaphors.get('recurring_metaphors', []):
                lines.append(f"- {m}")
            lines.append("")
            
            lines.append("### Духовные концепты:")
            for c in metaphors.get('spiritual_concepts', []):
                lines.append(f"- {c}")
            lines.append("")
        
        # Провокативные техники
        lines.append("## 3. Провокативные техники")
        lines.append("")
        
        techniques = style_analysis.get('provocative_techniques', {})
        if techniques:
            lines.append("### Конфронтация:")
            for t in techniques.get('confrontation', []):
                lines.append(f"- {t}")
            lines.append("")
            
            lines.append("### Переворот перспективы:")
            for t in techniques.get('perspective_flip', []):
                lines.append(f"- {t}")
            lines.append("")
        
        # Паттерны для промптов
        lines.append("## 4. Паттерны для интеграции в промпты")
        lines.append("")
        
        # Фразы-триггеры
        lines.append("### Фразы-триггеры:")
        for trigger in patterns.get('trigger_phrases', []):
            lines.append(f"- **{trigger.get('phrase')}**")
            lines.append(f"  - Контекст: {trigger.get('context')}")
            lines.append(f"  - Пример: {trigger.get('example')}")
            lines.append("")
        
        # Вопросы-ловушки
        lines.append("### Вопросы-ловушки:")
        for question in patterns.get('trap_questions', []):
            lines.append(f"- **{question.get('question')}**")
            lines.append(f"  - Цель: {question.get('purpose')}")
            lines.append(f"  - Пример: {question.get('example')}")
            lines.append("")
        
        # Ключевые инсайты
        lines.append("## 5. Ключевые инсайты")
        lines.append("")
        for insight in style_analysis.get('key_insights', []):
            lines.append(f"- {insight}")
        
        # Сохраняем
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines))


async def main():
    """Главная функция."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Analyze Natasha's communication style"
    )
    parser.add_argument(
        '--input',
        type=str,
        default='data/natasha_full_content_20251122_090907.json',
        help='Input JSON file with dialogs'
    )
    parser.add_argument(
        '--sample-size',
        type=int,
        default=50,
        help='Number of dialogs to analyze (default: 50)'
    )
    
    args = parser.parse_args()
    
    print("\n" + "="*70)
    print("NATASHA STYLE ANALYSIS")
    print("="*70 + "\n")
    
    analyzer = NatashaStyleAnalyzer()
    
    try:
        # Загружаем диалоги
        dialogs = analyzer.load_dialogs(args.input)
        
        if not dialogs:
            logger.error("No dialogs with reply chains found!")
            return
        
        # Анализируем стиль
        style_analysis = await analyzer.analyze_style(
            dialogs,
            sample_size=args.sample_size
        )
        
        if not style_analysis:
            logger.error("Style analysis failed!")
            return
        
        # Извлекаем паттерны
        patterns = await analyzer.extract_patterns(style_analysis)
        
        if not patterns:
            logger.error("Pattern extraction failed!")
            return
        
        # Сохраняем результаты
        style_file, patterns_file, report_file = analyzer.save_results(
            style_analysis,
            patterns
        )
        
        # Статистика
        logger.info(f"\n{'='*70}")
        logger.info("RESULTS")
        logger.info(f"{'='*70}")
        logger.info(f"Analyzed dialogs: {args.sample_size}")
        logger.info(f"Style analysis: {style_file}")
        logger.info(f"Patterns: {patterns_file}")
        logger.info(f"Report: {report_file}")
        logger.info(f"{'='*70}\n")
        
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())
