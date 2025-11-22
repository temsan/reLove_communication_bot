"""
Скрипт для заполнения профилей пользователей через Telethon user-клиент.
Получает участников из всех каналов и чатов reLove и заполняет их профили.

Использование:
    python scripts/fill_profiles_from_channels.py --all              # Все каналы reLove
    python scripts/fill_profiles_from_channels.py --channel @relove  # Конкретный канал
    python scripts/fill_profiles_from_channels.py --limit 100        # Ограничить количество
"""
import asyncio
import logging
import sys
from pathlib import Path
from typing import List, Optional
import argparse

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from telethon import TelegramClient
from telethon.tl.functions.channels import GetParticipantsRequest
from telethon.tl.types import ChannelParticipantsSearch, User as TelethonUser
from sqlalchemy import select
from tqdm import tqdm

from relove_bot.config import settings
from relove_bot.db.models import User, GenderEnum
from relove_bot.db.session import async_session
from relove_bot.services.profile_service import ProfileService

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/fill_profiles_from_channels.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class ChannelProfileFiller:
    """Класс для заполнения профилей из каналов через Telethon"""
    
    def __init__(self):
        self.client = TelegramClient(
            settings.tg_session,
            settings.tg_api_id,
            settings.tg_api_hash.get_secret_value()
        )
        self.stats = {
            'channels_processed': 0,
            'users_found': 0,
            'users_added': 0,
            'users_updated': 0,
            'profiles_filled': 0,
            'errors': 0,
            'duplicates_skipped': 0  # Пользователи, найденные в нескольких каналах
        }
        # Множество для отслеживания уже обработанных пользователей
        self.processed_user_ids = set()
    
    async def find_relove_channels(self) -> List[str]:
        """Находит все каналы и чаты с 'relove' в названии"""
        logger.info("Searching for reLove channels and chats...")
        relove_entities = []
        
        async for dialog in self.client.iter_dialogs():
            entity_name = dialog.name.lower()
            
            # Ищем каналы/чаты с relove в названии
            if 'relove' in entity_name or 'релов' in entity_name:
                entity_info = {
                    'id': dialog.id,
                    'name': dialog.name,
                    'username': getattr(dialog.entity, 'username', None),
                    'type': 'channel' if dialog.is_channel else 'group'
                }
                relove_entities.append(entity_info)
                logger.info(
                    f"Found: {entity_info['name']} "
                    f"(@{entity_info['username']}) "
                    f"[{entity_info['type']}]"
                )
        
        return relove_entities
    
    async def get_channel_participants(
        self, 
        channel_username: str, 
        limit: Optional[int] = None
    ) -> List[TelethonUser]:
        """Получает участников канала"""
        logger.info(f"Getting participants from {channel_username}...")
        
        try:
            channel = await self.client.get_entity(channel_username)
            participants = []
            
            # Для каналов используем GetParticipantsRequest
            if hasattr(channel, 'broadcast'):
                logger.info(f"Channel {channel_username} is a broadcast channel")
                # Для broadcast каналов нельзя получить список участников
                # Но можно получить админов
                async for user in self.client.iter_participants(
                    channel, 
                    filter=None,
                    limit=limit or 10000
                ):
                    if isinstance(user, TelethonUser) and not user.bot:
                        participants.append(user)
            else:
                # Для групп и супергрупп
                async for user in self.client.iter_participants(
                    channel,
                    limit=limit or 10000
                ):
                    if isinstance(user, TelethonUser) and not user.bot:
                        participants.append(user)
            
            logger.info(f"Found {len(participants)} participants in {channel_username}")
            return participants
            
        except Exception as e:
            logger.error(f"Error getting participants from {channel_username}: {e}")
            self.stats['errors'] += 1
            return []
    
    async def save_user_to_db(
        self, 
        tg_user: TelethonUser,
        session,
        is_duplicate: bool = False
    ) -> Optional[User]:
        """
        Сохраняет пользователя в БД.
        
        Args:
            tg_user: Пользователь из Telegram
            session: Сессия БД
            is_duplicate: True если пользователь уже был обработан в другом канале
        """
        try:
            # Проверяем, есть ли уже такой пользователь
            result = await session.execute(
                select(User).where(User.id == tg_user.id)
            )
            db_user = result.scalar_one_or_none()
            
            if db_user:
                # Обновляем данные если изменились
                update_needed = False
                
                if db_user.username != tg_user.username:
                    db_user.username = tg_user.username
                    update_needed = True
                
                if db_user.first_name != tg_user.first_name:
                    db_user.first_name = tg_user.first_name
                    update_needed = True
                
                if db_user.last_name != tg_user.last_name:
                    db_user.last_name = tg_user.last_name
                    update_needed = True
                
                if not db_user.is_active:
                    db_user.is_active = True
                    update_needed = True
                
                # ВАЖНО: НЕ трогаем markers (summary, relove_context и т.д.)
                # Они сохраняются как есть
                
                if update_needed:
                    await session.commit()
                    if not is_duplicate:
                        self.stats['users_updated'] += 1
                    logger.debug(f"Updated user {tg_user.id} (@{tg_user.username})")
                
                return db_user
            else:
                # Создаем нового пользователя
                new_user = User(
                    id=tg_user.id,
                    username=tg_user.username,
                    first_name=tg_user.first_name or "",
                    last_name=tg_user.last_name,
                    gender=GenderEnum.female,  # По умолчанию
                    is_active=True
                )
                session.add(new_user)
                await session.commit()
                await session.refresh(new_user)
                
                if not is_duplicate:
                    self.stats['users_added'] += 1
                logger.info(f"Added new user {tg_user.id} (@{tg_user.username})")
                
                return new_user
                
        except Exception as e:
            logger.error(f"Error saving user {tg_user.id}: {e}")
            await session.rollback()
            self.stats['errors'] += 1
            return None
    
    async def fill_user_profile(
        self,
        user: User,
        session
    ):
        """Заполняет профиль пользователя через ProfileService"""
        try:
            profile_service = ProfileService(session)
            
            # Создаем минимальный tg_user объект для ProfileService
            class TgUser:
                def __init__(self, db_user: User):
                    self.id = db_user.id
                    self.username = db_user.username
                    self.first_name = db_user.first_name
                    self.last_name = db_user.last_name
            
            tg_user = TgUser(user)
            
            # Анализируем профиль
            await profile_service.analyze_profile(
                user_id=user.id,
                tg_user=tg_user
            )
            
            self.stats['profiles_filled'] += 1
            logger.info(f"Filled profile for user {user.id} (@{user.username})")
            
        except Exception as e:
            logger.error(f"Error filling profile for user {user.id}: {e}")
            self.stats['errors'] += 1
    
    async def process_channel(
        self,
        channel_info: dict,
        limit: Optional[int] = None,
        fill_profiles: bool = True
    ):
        """Обрабатывает один канал"""
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing: {channel_info['name']}")
        logger.info(f"{'='*60}")
        
        # Получаем участников
        channel_identifier = (
            f"@{channel_info['username']}" 
            if channel_info['username'] 
            else channel_info['id']
        )
        
        participants = await self.get_channel_participants(
            channel_identifier,
            limit=limit
        )
        
        if not participants:
            logger.warning(f"No participants found in {channel_info['name']}")
            return
        
        self.stats['users_found'] += len(participants)
        
        # Сохраняем пользователей в БД
        async with async_session() as session:
            with tqdm(
                total=len(participants),
                desc=f"Processing {channel_info['name']}"
            ) as pbar:
                for tg_user in participants:
                    # Проверяем, не обрабатывали ли мы уже этого пользователя
                    is_duplicate = tg_user.id in self.processed_user_ids
                    
                    if is_duplicate:
                        self.stats['duplicates_skipped'] += 1
                        logger.debug(
                            f"User {tg_user.id} (@{tg_user.username}) already processed "
                            f"(found in multiple channels)"
                        )
                        pbar.update(1)
                        continue
                    
                    # Сохраняем пользователя
                    db_user = await self.save_user_to_db(tg_user, session, is_duplicate=False)
                    
                    # Добавляем в множество обработанных
                    if db_user:
                        self.processed_user_ids.add(tg_user.id)
                    
                    # Заполняем профиль если нужно
                    if db_user and fill_profiles:
                        # Проверяем, нет ли уже профиля (используем правильную колонку)
                        has_profile = db_user.profile_summary is not None
                        
                        if not has_profile:
                            await self.fill_user_profile(db_user, session)
                        else:
                            logger.debug(
                                f"User {db_user.id} already has profile, skipping"
                            )
                    
                    pbar.update(1)
                    
                    # Небольшая пауза чтобы не перегружать
                    await asyncio.sleep(0.1)
        
        self.stats['channels_processed'] += 1
    
    async def process_all_relove_channels(
        self,
        limit: Optional[int] = None,
        fill_profiles: bool = True
    ):
        """Обрабатывает все найденные каналы reLove"""
        # Находим каналы
        channels = await self.find_relove_channels()
        
        if not channels:
            logger.warning("No reLove channels found!")
            return
        
        logger.info(f"\nFound {len(channels)} reLove channels/groups:")
        for ch in channels:
            logger.info(f"  - {ch['name']} (@{ch['username']}) [{ch['type']}]")
        
        # Обрабатываем каждый канал
        for channel_info in channels:
            await self.process_channel(
                channel_info,
                limit=limit,
                fill_profiles=fill_profiles
            )
            
            # Пауза между каналами
            await asyncio.sleep(2)
    
    async def process_specific_channel(
        self,
        channel_username: str,
        limit: Optional[int] = None,
        fill_profiles: bool = True
    ):
        """Обрабатывает конкретный канал"""
        try:
            channel = await self.client.get_entity(channel_username)
            channel_info = {
                'id': channel.id,
                'name': getattr(channel, 'title', channel_username),
                'username': getattr(channel, 'username', None),
                'type': 'channel' if getattr(channel, 'broadcast', False) else 'group'
            }
            
            await self.process_channel(
                channel_info,
                limit=limit,
                fill_profiles=fill_profiles
            )
            
        except Exception as e:
            logger.error(f"Error processing channel {channel_username}: {e}")
            self.stats['errors'] += 1
    
    def print_stats(self):
        """Выводит статистику"""
        logger.info("\n" + "="*60)
        logger.info("STATISTICS")
        logger.info("="*60)
        logger.info(f"Channels processed: {self.stats['channels_processed']}")
        logger.info(f"Users found (total): {self.stats['users_found']}")
        logger.info(f"Users found (unique): {len(self.processed_user_ids)}")
        logger.info(f"Duplicates skipped: {self.stats['duplicates_skipped']}")
        logger.info(f"Users added: {self.stats['users_added']}")
        logger.info(f"Users updated: {self.stats['users_updated']}")
        logger.info(f"Profiles filled: {self.stats['profiles_filled']}")
        logger.info(f"Errors: {self.stats['errors']}")
        logger.info("="*60)
        
        # Дополнительная информация
        if self.stats['duplicates_skipped'] > 0:
            overlap_percent = (
                self.stats['duplicates_skipped'] / self.stats['users_found'] * 100
                if self.stats['users_found'] > 0 else 0
            )
            logger.info(f"\n💡 Channel overlap: {overlap_percent:.1f}%")
            logger.info(
                f"   {self.stats['duplicates_skipped']} users found in multiple channels"
            )


async def main():
    """Главная функция"""
    parser = argparse.ArgumentParser(
        description="Заполнение профилей из каналов Telegram через Telethon"
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Обработать все каналы reLove'
    )
    parser.add_argument(
        '--channel',
        type=str,
        help='Обработать конкретный канал (username или ID)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Ограничить количество участников'
    )
    parser.add_argument(
        '--no-fill',
        action='store_true',
        help='Только импортировать пользователей, не заполнять профили'
    )
    parser.add_argument(
        '--list-channels',
        action='store_true',
        help='Только показать список каналов reLove'
    )
    
    args = parser.parse_args()
    
    filler = ChannelProfileFiller()
    
    try:
        # Подключаемся к Telegram
        await filler.client.start()
        logger.info("✅ Connected to Telegram as user client")
        
        # Показываем список каналов
        if args.list_channels:
            channels = await filler.find_relove_channels()
            logger.info(f"\nFound {len(channels)} reLove channels:")
            for ch in channels:
                logger.info(
                    f"  - {ch['name']} "
                    f"(@{ch['username'] or 'no username'}) "
                    f"[{ch['type']}]"
                )
            return
        
        fill_profiles = not args.no_fill
        
        # Обрабатываем все каналы
        if args.all:
            await filler.process_all_relove_channels(
                limit=args.limit,
                fill_profiles=fill_profiles
            )
        
        # Обрабатываем конкретный канал
        elif args.channel:
            await filler.process_specific_channel(
                args.channel,
                limit=args.limit,
                fill_profiles=fill_profiles
            )
        
        else:
            parser.print_help()
            return
        
        # Выводим статистику
        filler.print_stats()
        
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    
    finally:
        await filler.client.disconnect()
        logger.info("Disconnected from Telegram")


if __name__ == "__main__":
    asyncio.run(main())
