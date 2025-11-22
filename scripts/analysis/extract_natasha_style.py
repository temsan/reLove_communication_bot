"""
Скрипт для извлечения стиля Наташи Волкош из каналов и чатов.
1. Из постов в broadcast каналах - выжимка языка
2. Из чатов - провокативные диалоги
"""
import asyncio
import sys
from pathlib import Path
from typing import List, Dict
import json
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from telethon import TelegramClient
from telethon.tl.types import Message
from relove_bot.config import settings
from relove_bot.rag.llm import LLM
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/extract_natasha_style.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


# Каналы для анализа постов
BROADCAST_CHANNELS = [
    'reloverituals',  # reLove rituals
    # reLove🌀| Путь Героя - нет username
    # reLove. Большая Игра с Наташей - нет username
    # reLove people - нет username
    # Прошлые Жизни reLove - нет username
]

# Чаты для анализа диалогов
DISCUSSION_CHATS = [
    # ЧАТ RELOVE - нет username
    # reLove – Большая Игра - нет username
    # reLove people Chat - нет username
    # reLove🌀| Путь Героя Chat - нет username
    # ЧАТ Прошлые жизни reLove - нет username
]


class NatashaStyleExtractor:
    """Извлекает стиль Наташи Волкош из каналов"""
    
    def __init__(self):
        self.client = TelegramClient(
            settings.tg_session,
            settings.tg_api_id,
            settings.tg_api_hash.get_secret_value()
        )
        self.llm = LLM()
        self.natasha_posts = []
        self.natasha_dialogs = []
    
    async def find_channels_by_name(self, keywords: List[str]) -> List[Dict]:
        """Находит каналы по ключевым словам в названии"""
        logger.info(f"Searching for channels with keywords: {keywords}")
        found = []
        
        async for dialog in self.client.iter_dialogs():
            name_lower = dialog.name.lower()
            
            for keyword in keywords:
                if keyword.lower() in name_lower:
                    channel_info = {
                        'id': dialog.id,
                        'name': dialog.name,
                        'username': getattr(dialog.entity, 'username', None),
                        'entity': dialog.entity
                    }
                    found.append(channel_info)
                    logger.info(f"   Found: {channel_info['name']}")
                    break
        
        return found
    
    async def extract_posts_from_channel(
        self, 
        channel_entity, 
        channel_name: str,
        limit: int = 100
    ):
        """Извлекает посты из канала"""
        logger.info(f"\n{'='*70}")
        logger.info(f"Extracting posts from: {channel_name}")
        logger.info(f"{'='*70}")
        
        posts = []
        count = 0
        
        try:
            async for message in self.client.iter_messages(channel_entity, limit=limit):
                if message.text and len(message.text) > 50:  # Только содержательные посты
                    post_data = {
                        'channel': channel_name,
                        'date': message.date.isoformat(),
                        'text': message.text,
                        'views': message.views or 0,
                        'forwards': message.forwards or 0
                    }
                    posts.append(post_data)
                    count += 1
                    
                    if count <= 3:  # Показываем первые 3
                        logger.info(f"\nPost {count}:")
                        logger.info(f"Date: {message.date}")
                        logger.info(f"Text preview: {message.text[:200]}...")
            
            logger.info(f"\n✅ Extracted {len(posts)} posts from {channel_name}")
            self.natasha_posts.extend(posts)
            
        except Exception as e:
            logger.error(f"❌ Error extracting from {channel_name}: {e}")
    
    async def extract_dialogs_from_chat(
        self,
        chat_entity,
        chat_name: str,
        limit: int = 500
    ):
        """Извлекает диалоги из чата, фокусируясь на сообщениях Наташи"""
        logger.info(f"\n{'='*70}")
        logger.info(f"Extracting dialogs from: {chat_name}")
        logger.info(f"{'='*70}")
        
        # ID Наташи Волкош (если известен)
        NATASHA_ID = 496684653  # @NatashaVolkosh
        
        dialogs = []
        natasha_messages = []
        
        try:
            messages_list = []
            async for message in self.client.iter_messages(chat_entity, limit=limit):
                messages_list.append(message)
            
            # Сортируем по времени (старые -> новые)
            messages_list.sort(key=lambda m: m.date)
            
            # Ищем сообщения Наташи и контекст вокруг них
            for i, message in enumerate(messages_list):
                if message.sender_id == NATASHA_ID and message.text:
                    # Берем контекст: 2 сообщения до и 2 после
                    context_start = max(0, i - 2)
                    context_end = min(len(messages_list), i + 3)
                    
                    dialog_context = []
                    for j in range(context_start, context_end):
                        msg = messages_list[j]
                        if msg.text:
                            dialog_context.append({
                                'sender_id': msg.sender_id,
                                'sender_name': getattr(msg.sender, 'first_name', 'Unknown') if msg.sender else 'Unknown',
                                'is_natasha': msg.sender_id == NATASHA_ID,
                                'text': msg.text,
                                'date': msg.date.isoformat()
                            })
                    
                    if len(dialog_context) > 1:  # Есть контекст
                        dialog_data = {
                            'chat': chat_name,
                            'date': message.date.isoformat(),
                            'context': dialog_context
                        }
                        dialogs.append(dialog_data)
                        natasha_messages.append(message.text)
            
            logger.info(f"\n✅ Found {len(natasha_messages)} messages from Natasha")
            logger.info(f"✅ Extracted {len(dialogs)} dialog contexts")
            
            # Показываем примеры
            if natasha_messages:
                logger.info(f"\nExample Natasha messages:")
                for i, msg in enumerate(natasha_messages[:3], 1):
                    logger.info(f"\n{i}. {msg[:200]}...")
            
            self.natasha_dialogs.extend(dialogs)
            
        except Exception as e:
            logger.error(f"❌ Error extracting from {chat_name}: {e}")
    
    async def analyze_language_style(self) -> Dict:
        """Анализирует стиль языка Наташи через LLM"""
        logger.info(f"\n{'='*70}")
        logger.info("ANALYZING NATASHA'S LANGUAGE STYLE")
        logger.info(f"{'='*70}")
        
        if not self.natasha_posts:
            logger.warning("No posts to analyze!")
            return {}
        
        # Берем выборку постов
        sample_posts = self.natasha_posts[:50]
        posts_text = "\n\n---\n\n".join([p['text'] for p in sample_posts])
        
        analysis_prompt = f"""
Проанализируй стиль письма Наташи Волкош на основе её постов.

ПОСТЫ НАТАШИ:
{posts_text}

Выдели:
1. Ключевые фразы и выражения (10-15 примеров)
2. Стилистические особенности (тон, структура, обращение)
3. Провокативные приемы
4. Метафоры и образы
5. Типичные вопросы к аудитории
6. Призывы к действию

Формат ответа: JSON
{{
    "key_phrases": ["фраза 1", "фраза 2", ...],
    "style_features": ["особенность 1", ...],
    "provocative_techniques": ["прием 1", ...],
    "metaphors": ["метафора 1", ...],
    "typical_questions": ["вопрос 1", ...],
    "calls_to_action": ["призыв 1", ...]
}}
"""
        
        try:
            logger.info("Analyzing with LLM...")
            response = await self.llm.generate_rag_answer("", analysis_prompt)
            
            # Пытаемся распарсить JSON
            try:
                # Ищем JSON в ответе
                import re
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    analysis = json.loads(json_match.group())
                else:
                    analysis = {'raw_response': response}
            except:
                analysis = {'raw_response': response}
            
            logger.info("✅ Analysis complete")
            return analysis
            
        except Exception as e:
            logger.error(f"❌ Error analyzing: {e}")
            return {}
    
    async def analyze_dialog_patterns(self) -> Dict:
        """Анализирует паттерны провокативных диалогов"""
        logger.info(f"\n{'='*70}")
        logger.info("ANALYZING DIALOG PATTERNS")
        logger.info(f"{'='*70}")
        
        if not self.natasha_dialogs:
            logger.warning("No dialogs to analyze!")
            return {}
        
        # Берем выборку диалогов
        sample_dialogs = self.natasha_dialogs[:30]
        
        dialogs_text = ""
        for i, dialog in enumerate(sample_dialogs, 1):
            dialogs_text += f"\n\nДИАЛОГ {i}:\n"
            for msg in dialog['context']:
                role = "НАТАША" if msg['is_natasha'] else msg['sender_name']
                dialogs_text += f"{role}: {msg['text']}\n"
        
        analysis_prompt = f"""
Проанализируй провокативные диалоги Наташи Волкош.

ДИАЛОГИ:
{dialogs_text}

Выдели:
1. Провокативные вопросы (10-15 примеров)
2. Техники вскрытия паттернов
3. Способы работы с сопротивлением
4. Переформулировки и отзеркаливания
5. Прямые конфронтации
6. Поддерживающие фразы

Формат ответа: JSON
{{
    "provocative_questions": ["вопрос 1", ...],
    "pattern_breaking": ["техника 1", ...],
    "resistance_work": ["способ 1", ...],
    "reframing": ["пример 1", ...],
    "confrontations": ["пример 1", ...],
    "support_phrases": ["фраза 1", ...]
}}
"""
        
        try:
            logger.info("Analyzing with LLM...")
            response = await self.llm.generate_rag_answer("", analysis_prompt)
            
            # Пытаемся распарсить JSON
            try:
                import re
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    analysis = json.loads(json_match.group())
                else:
                    analysis = {'raw_response': response}
            except:
                analysis = {'raw_response': response}
            
            logger.info("✅ Analysis complete")
            return analysis
            
        except Exception as e:
            logger.error(f"❌ Error analyzing: {e}")
            return {}
    
    async def save_results(self, language_analysis: Dict, dialog_analysis: Dict):
        """Сохраняет результаты анализа"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Сохраняем сырые данные
        raw_data = {
            'timestamp': timestamp,
            'posts_count': len(self.natasha_posts),
            'dialogs_count': len(self.natasha_dialogs),
            'posts': self.natasha_posts,
            'dialogs': self.natasha_dialogs
        }
        
        raw_file = f"data/natasha_raw_data_{timestamp}.json"
        Path("data").mkdir(exist_ok=True)
        
        with open(raw_file, 'w', encoding='utf-8') as f:
            json.dump(raw_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"\n✅ Saved raw data to: {raw_file}")
        
        # Сохраняем анализ
        analysis_data = {
            'timestamp': timestamp,
            'language_style': language_analysis,
            'dialog_patterns': dialog_analysis
        }
        
        analysis_file = f"data/natasha_style_analysis_{timestamp}.json"
        
        with open(analysis_file, 'w', encoding='utf-8') as f:
            json.dump(analysis_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✅ Saved analysis to: {analysis_file}")
        
        return raw_file, analysis_file


async def main():
    """Главная функция"""
    print("\n" + "="*70)
    print("NATASHA VOLKOSH STYLE EXTRACTION")
    print("="*70 + "\n")
    
    extractor = NatashaStyleExtractor()
    
    try:
        await extractor.client.connect()
        
        if not await extractor.client.is_user_authorized():
            logger.error("❌ Not authorized!")
            return
        
        logger.info("✅ Connected to Telegram\n")
        
        # 1. Находим broadcast каналы
        logger.info("STEP 1: Finding broadcast channels...")
        broadcast_keywords = [
            'relove rituals',
            'путь героя',
            'большая игра',
            'relove people',
            'прошлые жизни'
        ]
        
        broadcast_channels = await extractor.find_channels_by_name(broadcast_keywords)
        
        # 2. Извлекаем посты
        logger.info("\nSTEP 2: Extracting posts from channels...")
        for channel in broadcast_channels:
            await extractor.extract_posts_from_channel(
                channel['entity'],
                channel['name'],
                limit=100
            )
        
        # 3. Находим чаты
        logger.info("\nSTEP 3: Finding discussion chats...")
        chat_keywords = [
            'чат relove',
            'большая игра',
            'people chat',
            'путь героя chat',
            'прошлые жизни'
        ]
        
        discussion_chats = await extractor.find_channels_by_name(chat_keywords)
        
        # 4. Извлекаем диалоги
        logger.info("\nSTEP 4: Extracting dialogs from chats...")
        for chat in discussion_chats:
            await extractor.extract_dialogs_from_chat(
                chat['entity'],
                chat['name'],
                limit=500
            )
        
        # 5. Анализируем стиль
        logger.info("\nSTEP 5: Analyzing language style...")
        language_analysis = await extractor.analyze_language_style()
        
        # 6. Анализируем диалоги
        logger.info("\nSTEP 6: Analyzing dialog patterns...")
        dialog_analysis = await extractor.analyze_dialog_patterns()
        
        # 7. Сохраняем результаты
        logger.info("\nSTEP 7: Saving results...")
        raw_file, analysis_file = await extractor.save_results(
            language_analysis,
            dialog_analysis
        )
        
        # Итоговая статистика
        logger.info(f"\n{'='*70}")
        logger.info("STATISTICS")
        logger.info(f"{'='*70}")
        logger.info(f"Broadcast channels processed: {len(broadcast_channels)}")
        logger.info(f"Discussion chats processed: {len(discussion_chats)}")
        logger.info(f"Posts extracted: {len(extractor.natasha_posts)}")
        logger.info(f"Dialog contexts extracted: {len(extractor.natasha_dialogs)}")
        logger.info(f"\nFiles created:")
        logger.info(f"  - {raw_file}")
        logger.info(f"  - {analysis_file}")
        logger.info(f"{'='*70}\n")
        
        logger.info("✅ Extraction complete!")
        logger.info("\n💡 Next step: Integrate into prompts")
        logger.info("   python scripts/analysis/integrate_natasha_style.py")
        
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
    
    finally:
        await extractor.client.disconnect()
        logger.info("\n👋 Disconnected from Telegram")


if __name__ == "__main__":
    asyncio.run(main())
