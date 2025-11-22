"""
Полное извлечение стиля Наташи Волкош:
1. Все её посты из всех каналов
2. Полные диалоги с контекстом (вопрос -> ответ Наташи)
3. Конкатенация всех постов пользователя из разных каналов
"""
import asyncio
import sys
from pathlib import Path
from typing import List, Dict
import json
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from telethon import TelegramClient
from relove_bot.config import settings
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/extract_natasha_full.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ID Наташи Волкош
NATASHA_ID = 496684653


class FullStyleExtractor:
    """Полное извлечение стиля и контента"""
    
    def __init__(self):
        self.client = TelegramClient(
            settings.tg_session,
            settings.tg_api_id,
            settings.tg_api_hash.get_secret_value()
        )
        
        # Данные Наташи
        self.natasha_posts = []  # Все посты Наташи
        self.natasha_dialogs = []  # Диалоги с полным контекстом
        
        # Данные всех пользователей
        self.user_posts = {}  # {user_id: [posts]}
    
    async def extract_all_natasha_content(self, limit_per_channel: int = 1000):
        """Извлекает ВСЕ посты и диалоги Наташи из всех каналов"""
        logger.info("Extracting ALL Natasha's content from all reLove channels...")
        
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
                messages_list = []
                
                # Получаем все сообщения
                async for message in self.client.iter_messages(
                    dialog.entity,
                    limit=limit_per_channel
                ):
                    if message.text:
                        messages_list.append(message)
                
                logger.info(f"Got {len(messages_list)} messages")
                
                # Сортируем по времени
                messages_list.sort(key=lambda m: m.date)
                
                # Извлекаем посты и диалоги Наташи
                natasha_count = 0
                dialog_count = 0
                
                for i, message in enumerate(messages_list):
                    # Посты/сообщения Наташи
                    if message.sender_id == NATASHA_ID:
                        natasha_count += 1
                        
                        post_data = {
                            'channel': channel_name,
                            'date': message.date.isoformat(),
                            'text': message.text,
                            'views': message.views or 0,
                            'forwards': message.forwards or 0,
                            'message_id': message.id
                        }
                        self.natasha_posts.append(post_data)
                        
                        # Извлекаем контекст диалога
                        dialog_context = []
                        reply_chain = []
                        has_reply = False
                        
                        # 1. Проверяем, есть ли reply_to
                        if message.reply_to and message.reply_to.reply_to_msg_id:
                            has_reply = True
                            
                            # Ищем сообщение, на которое отвечает Наташа
                            replied_msg = None
                            for msg in messages_list:
                                if msg.id == message.reply_to.reply_to_msg_id:
                                    replied_msg = msg
                                    break
                            
                            if replied_msg:
                                # Строим цепочку реплаев (если есть)
                                current_msg = replied_msg
                                chain_depth = 0
                                max_chain_depth = 5  # Ограничение глубины цепочки
                                
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
                                        'message_id': current_msg.id,
                                        'is_reply_target': current_msg.id == message.reply_to.reply_to_msg_id
                                    })
                                    
                                    # Проверяем, есть ли у этого сообщения reply
                                    if current_msg.reply_to and current_msg.reply_to.reply_to_msg_id:
                                        # Ищем следующее в цепочке
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
                                    'text': message.text,
                                    'date': message.date.isoformat(),
                                    'message_id': message.id,
                                    'is_reply_target': False
                                })
                                
                                dialog_context = reply_chain
                        
                        # 2. Если reply нет - берем контекст по порядку (как раньше)
                        if not has_reply or len(dialog_context) == 0:
                            context_start = max(0, i - 2)
                            context_end = min(len(messages_list), i + 3)
                            
                            for j in range(context_start, context_end):
                                msg = messages_list[j]
                                
                                sender_name = "Unknown"
                                if msg.sender:
                                    sender_name = getattr(msg.sender, 'first_name', 'Unknown')
                                
                                dialog_context.append({
                                    'sender_id': msg.sender_id,
                                    'sender_name': sender_name,
                                    'is_natasha': msg.sender_id == NATASHA_ID,
                                    'text': msg.text,
                                    'date': msg.date.isoformat(),
                                    'message_id': msg.id,
                                    'is_reply_target': False
                                })
                        
                        # Сохраняем диалог если есть контекст
                        if len(dialog_context) > 1:
                            dialog_data = {
                                'chat': channel_name,
                                'date': message.date.isoformat(),
                                'natasha_message': message.text,
                                'has_reply_chain': has_reply,
                                'context': dialog_context
                            }
                            self.natasha_dialogs.append(dialog_data)
                            dialog_count += 1
                
                logger.info(f"✅ Natasha's messages: {natasha_count}")
                logger.info(f"✅ Dialog contexts: {dialog_count}")
                
            except Exception as e:
                logger.error(f"❌ Error processing {channel_name}: {e}")
    
    async def extract_user_posts_from_all_channels(
        self,
        user_id: int,
        limit_per_channel: int = 1000
    ) -> Dict:
        """
        Извлекает ВСЕ посты конкретного пользователя из всех каналов reLove.
        Конкатенирует в единый текст.
        """
        logger.info(f"\nExtracting all posts for user {user_id}...")
        
        user_posts = []
        channels_found = []
        
        async for dialog in self.client.iter_dialogs():
            name_lower = dialog.name.lower()
            
            # Только каналы reLove
            if 'relove' not in name_lower and 'релов' not in name_lower:
                continue
            
            try:
                channel_posts = []
                
                async for message in self.client.iter_messages(
                    dialog.entity,
                    limit=limit_per_channel
                ):
                    if message.sender_id == user_id and message.text:
                        post_data = {
                            'channel': dialog.name,
                            'date': message.date.isoformat(),
                            'text': message.text
                        }
                        channel_posts.append(post_data)
                        user_posts.append(post_data)
                
                if channel_posts:
                    channels_found.append({
                        'channel': dialog.name,
                        'posts_count': len(channel_posts)
                    })
                    logger.info(
                        f"  {dialog.name}: {len(channel_posts)} posts"
                    )
                
            except Exception as e:
                logger.debug(f"Error in {dialog.name}: {e}")
        
        # Сортируем по дате
        user_posts.sort(key=lambda p: p['date'])
        
        # Конкатенируем все тексты
        all_text = "\n\n---\n\n".join([p['text'] for p in user_posts])
        
        result = {
            'user_id': user_id,
            'total_posts': len(user_posts),
            'channels': channels_found,
            'posts': user_posts,
            'concatenated_text': all_text
        }
        
        logger.info(f"\n✅ User {user_id}:")
        logger.info(f"   Total posts: {len(user_posts)}")
        logger.info(f"   Channels: {len(channels_found)}")
        logger.info(f"   Total text length: {len(all_text)} chars")
        
        return result
    
    async def save_results(self):
        """Сохраняет результаты"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Сохраняем данные Наташи
        natasha_data = {
            'timestamp': timestamp,
            'natasha_id': NATASHA_ID,
            'posts_count': len(self.natasha_posts),
            'dialogs_count': len(self.natasha_dialogs),
            'posts': self.natasha_posts,
            'dialogs': self.natasha_dialogs
        }
        
        natasha_file = f"data/natasha_full_content_{timestamp}.json"
        Path("data").mkdir(exist_ok=True)
        
        with open(natasha_file, 'w', encoding='utf-8') as f:
            json.dump(natasha_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"\n✅ Saved Natasha's content to: {natasha_file}")
        
        # Сохраняем конкатенированный текст отдельно
        concat_file = f"data/natasha_all_text_{timestamp}.txt"
        
        with open(concat_file, 'w', encoding='utf-8') as f:
            # Все посты
            f.write("="*70 + "\n")
            f.write("NATASHA'S POSTS\n")
            f.write("="*70 + "\n\n")
            
            for post in self.natasha_posts:
                f.write(f"[{post['channel']}] {post['date']}\n")
                f.write(post['text'])
                f.write("\n\n" + "-"*70 + "\n\n")
            
            # Все диалоги
            f.write("\n\n" + "="*70 + "\n")
            f.write("NATASHA'S DIALOGS WITH CONTEXT\n")
            f.write("="*70 + "\n\n")
            
            for dialog in self.natasha_dialogs:
                f.write(f"[{dialog['chat']}] {dialog['date']}\n\n")
                
                for msg in dialog['context']:
                    role = "🔥 НАТАША" if msg['is_natasha'] else f"👤 {msg['sender_name']}"
                    f.write(f"{role}: {msg['text']}\n\n")
                
                f.write("-"*70 + "\n\n")
        
        logger.info(f"✅ Saved concatenated text to: {concat_file}")
        
        return natasha_file, concat_file


async def main():
    """Главная функция"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Full extraction of Natasha's style and user posts"
    )
    parser.add_argument(
        '--natasha',
        action='store_true',
        help='Extract all Natasha content'
    )
    parser.add_argument(
        '--user',
        type=int,
        help='Extract all posts for specific user ID'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=1000,
        help='Limit messages per channel (default: 1000)'
    )
    
    args = parser.parse_args()
    
    print("\n" + "="*70)
    print("FULL CONTENT EXTRACTION")
    print("="*70 + "\n")
    
    extractor = FullStyleExtractor()
    
    try:
        await extractor.client.connect()
        
        if not await extractor.client.is_user_authorized():
            logger.error("❌ Not authorized!")
            return
        
        logger.info("✅ Connected to Telegram\n")
        
        # Извлечение контента Наташи
        if args.natasha:
            await extractor.extract_all_natasha_content(
                limit_per_channel=args.limit
            )
            
            natasha_file, concat_file = await extractor.save_results()
            
            # Статистика
            logger.info(f"\n{'='*70}")
            logger.info("STATISTICS")
            logger.info(f"{'='*70}")
            logger.info(f"Natasha's posts: {len(extractor.natasha_posts)}")
            logger.info(f"Dialog contexts: {len(extractor.natasha_dialogs)}")
            logger.info(f"\nFiles created:")
            logger.info(f"  - {natasha_file} (JSON)")
            logger.info(f"  - {concat_file} (TXT)")
            logger.info(f"{'='*70}\n")
        
        # Извлечение постов конкретного пользователя
        elif args.user:
            user_data = await extractor.extract_user_posts_from_all_channels(
                args.user,
                limit_per_channel=args.limit
            )
            
            # Сохраняем
            user_file = f"data/user_{args.user}_all_posts.json"
            with open(user_file, 'w', encoding='utf-8') as f:
                json.dump(user_data, f, ensure_ascii=False, indent=2)
            
            # Сохраняем конкатенированный текст
            user_text_file = f"data/user_{args.user}_all_text.txt"
            with open(user_text_file, 'w', encoding='utf-8') as f:
                f.write(user_data['concatenated_text'])
            
            logger.info(f"\n✅ Saved to:")
            logger.info(f"  - {user_file}")
            logger.info(f"  - {user_text_file}")
        
        else:
            parser.print_help()
        
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
    
    finally:
        await extractor.client.disconnect()
        logger.info("\n👋 Disconnected")


if __name__ == "__main__":
    asyncio.run(main())
