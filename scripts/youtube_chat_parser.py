import asyncio
import logging
import re
import sys
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any

import pytchat
from sqlalchemy import select, update, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker

from relove_bot.config import settings
from relove_bot.db.models import Base, YouTubeChatUser, User

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('youtube_chat_parser.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Компилируем регулярные выражения для поиска Telegram username
TG_USERNAME_PATTERN = re.compile(r'(?:@|(?:https?://)?(?:t\.me|telegram\.me)/)([a-zA-Z0-9_]{5,32})')


class YouTubeChatParser:
    def __init__(self, video_id: str):
        self.video_id = video_id
        self.chat = None
        self.engine = None
        self.Session = None
        self.processed_messages = set()  # Для избежания дубликатов
        self.logger = logging.getLogger(self.__class__.__name__)

    async def init_db(self):
        """Инициализация подключения к базе данных"""
        try:
            # Получаем URL для подключения к базе данных
            db_url = settings.db_url
            
            # Если используется SQLite, заменяем на асинхронный драйвер
            if db_url.startswith('sqlite'):
                db_url = db_url.replace('sqlite://', 'sqlite+aiosqlite:///')
            # Для PostgreSQL заменяем на асинхронный драйвер
            elif db_url.startswith('postgresql'):
                db_url = db_url.replace('postgresql://', 'postgresql+asyncpg://')
            
            self.engine = create_async_engine(db_url, echo=True)
            self.Session = async_sessionmaker(
                bind=self.engine,
                expire_on_commit=False,
                class_=AsyncSession
            )
            
            # Проверяем соединение
            async with self.engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
                self.logger.info("Успешное подключение к базе данных")
                
        except Exception as e:
            self.logger.error(f"Ошибка при инициализации базы данных: {e}", exc_info=True)
            raise
    
    async def find_telegram_user(self, username: str) -> Optional[int]:
        """Поиск пользователя в базе по username Telegram"""
        if not username:
            return None
            
        try:
            async with self.Session() as session:
                result = await session.execute(
                    select(User).where(User.username.ilike(f'%{username}%'))
                )
                user = result.scalars().first()
                return user.id if user else None
        except Exception as e:
            self.logger.error(f"Ошибка при поиске пользователя {username}: {e}")
            return None

    def extract_telegram_username(self, message: str) -> Optional[str]:
        """Извлекает username Telegram из текста сообщения"""
        if not message:
            return None
            
        # Удаляем эмодзи и специальные символы, которые могут мешать
        import emoji
        message = emoji.replace_emoji(message, replace='')
        
        # Ищем упоминания Telegram в тексте сообщения
        matches = TG_USERNAME_PATTERN.findall(message)
        if matches:
            # Берем первое совпадение и убираем @ если есть
            username = matches[0].lstrip('@').lower()
            # Проверяем, что username соответствует требованиям Telegram
            if 5 <= len(username) <= 32 and username.replace('_', '').isalnum():
                return username
        return None
    
    async def process_message(self, chat_data: Dict):
        """Обработка сообщения из чата"""
        try:
            message_id = chat_data.get('id')
            if not message_id:
                self.logger.warning("Получено сообщение без ID, пропускаем")
                return
                
            # Проверяем, обрабатывали ли мы это сообщение
            if message_id in self.processed_messages:
                return

            self.processed_messages.add(message_id)
            
            # Извлекаем информацию об авторе
            author = chat_data.get('author', {})
            author_name = author.get('name', 'Unknown')
            channel_id = author.get('channelId')
            
            # Ищем Telegram username в сообщении
            message_text = chat_data.get('message', '')
            telegram_username = self.extract_telegram_username(message_text)
            telegram_id = await self.find_telegram_user(telegram_username) if telegram_username else None

            # Подготавливаем данные для сохранения
            user_data = {
                'youtube_display_name': author_name,
                'youtube_channel_id': channel_id,
                'message_count': 1,
                'last_seen': datetime.now(timezone.utc),
                'telegram_username': telegram_username,
                'telegram_id': telegram_id,
                'metadata': {
                    'last_message': message_text[:500],
                    'timestamp': chat_data.get('timestamp', str(datetime.now(timezone.utc))),
                    'message_id': message_id,
                    'author_channel_url': author.get('channelUrl')
                }
            }

            await self.save_chat_user(user_data)
            
        except Exception as e:
            self.logger.error(f"Ошибка при обработке сообщения: {e}", exc_info=True)

    async def save_chat_user(self, user_data: Dict):
        """Сохранение или обновление данных пользователя чата"""
        if not self.Session:
            self.logger.error("Сессия базы данных не инициализирована")
            return
            
        async with self.Session() as session:
            try:
                # Проверяем, есть ли уже такой пользователь
                conditions = []
                if user_data.get('youtube_channel_id'):
                    conditions.append(YouTubeChatUser.youtube_channel_id == user_data['youtube_channel_id'])
                if user_data.get('youtube_display_name'):
                    conditions.append(YouTubeChatUser.youtube_display_name.ilike(user_data['youtube_display_name']))
                
                if not conditions:
                    self.logger.warning("Недостаточно данных для поиска пользователя")
                    return
                
                # Строим запрос с условиями OR
                query = select(YouTubeChatUser).where(*[c for c in conditions])
                result = await session.execute(query)
                existing_user = result.scalars().first()

                if existing_user:
                    # Обновляем существующего пользователя
                    existing_user.message_count += 1
                    existing_user.last_seen = user_data['last_seen']
                    
                    # Обновляем telegram_username, если нашли новый
                    if user_data.get('telegram_username') and not existing_user.telegram_username:
                        existing_user.telegram_username = user_data['telegram_username']
                        if user_data.get('telegram_id'):
                            existing_user.telegram_id = user_data['telegram_id']
                    
                    # Обновляем метаданные
                    user_metadata = existing_user.user_metadata or {}
                    user_metadata.update(user_data.get('user_metadata', {}))
                    existing_user.user_metadata = user_metadata
                    
                    self.logger.info(f"Обновлен пользователь: {existing_user.youtube_display_name}")
                else:
                    # Создаем нового пользователя
                    new_user = YouTubeChatUser(
                        youtube_display_name=user_data['youtube_display_name'],
                        youtube_channel_id=user_data.get('youtube_channel_id'),
                        message_count=1,
                        first_seen=datetime.now(timezone.utc),
                        last_seen=datetime.now(timezone.utc),
                        telegram_username=user_data.get('telegram_username'),
                        telegram_id=user_data.get('telegram_id'),
                        user_metadata=user_data.get('user_metadata', {})
                    )
                    session.add(new_user)
                    self.logger.info(f"Добавлен новый пользователь: {new_user.youtube_display_name}")
                
                await session.commit()
                
            except Exception as e:
                await session.rollback()
                self.logger.error(f"Ошибка при сохранении пользователя: {e}", exc_info=True)
                raise

    async def run(self):
        """Запуск парсера чата"""
        try:
            # Инициализируем подключение к базе данных
            await self.init_db()
            
            self.logger.info(f"Запуск парсера чата для видео: {self.video_id}")
            
            # Инициализация чата
            self.chat = pytchat.create(video_id=self.video_id)
            
            if not self.chat.is_alive():
                self.logger.error("Не удалось подключиться к чату. Проверьте ID видео и подключение к интернету.")
                return
                
            self.logger.info("Чат успешно инициализирован, начинаем сбор сообщений...")
            
            # Основной цикл обработки сообщений
            while self.chat.is_alive():
                try:
                    # Получаем новые сообщения
                    chat_data = self.chat.get()
                    
                    if not chat_data.sync_items():
                        self.logger.debug("Нет новых сообщений, ожидаем...")
                        await asyncio.sleep(1)
                        continue
                    
                    # Обрабатываем каждое сообщение
                    processed_count = 0
                    for message in chat_data.sync_items():
                        try:
                            message_dict = {
                                'id': message.id,
                                'message': message.message,
                                'timestamp': message.timestamp,
                                'author': {
                                    'name': message.author.name,
                                    'channelId': message.author.channelId,
                                    'channelUrl': message.author.channelUrl,
                                    'imageUrl': message.author.imageUrl,
                                    'isChatOwner': message.author.isChatOwner,
                                    'isChatSponsor': message.author.isChatSponsor,
                                    'isVerified': message.author.isVerified
                                }
                            }
                            await self.process_message(message_dict)
                            processed_count += 1
                            
                            # Логируем прогресс каждые 10 сообщений
                            if processed_count % 10 == 0:
                                self.logger.info(f"Обработано сообщений: {processed_count}")
                                
                        except Exception as e:
                            self.logger.error(f"Ошибка при обработке сообщения: {e}", exc_info=True)
                            continue
                    
                    # Небольшая задержка, чтобы не нагружать процессор
                    await asyncio.sleep(0.5)
                    
                except KeyboardInterrupt:
                    self.logger.info("Получен сигнал на завершение работы...")
                    break
                    
                except Exception as e:
                    self.logger.error(f"Ошибка в основном цикле: {e}", exc_info=True)
                    await asyncio.sleep(5)  # Пауза перед повторной попыткой
        
        except Exception as e:
            self.logger.error(f"Критическая ошибка: {e}", exc_info=True)
            raise
            
        finally:
            # Корректно завершаем работу
            try:
                if self.chat:
                    self.chat.terminate()
                    self.logger.info("Чат остановлен")
                
                if self.engine:
                    await self.engine.dispose()
                    self.logger.info("Соединение с базой данных закрыто")
                    
            except Exception as e:
                self.logger.error(f"Ошибка при завершении работы: {e}", exc_info=True)
                
            self.logger.info("Парсер завершил работу")


def parse_arguments():
    """Разбор аргументов командной строки"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Парсер чата YouTube')
    parser.add_argument('video_id', type=str, help='ID видео на YouTube')
    parser.add_argument('--log-level', type=str, default='INFO', 
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                       help='Уровень логирования')
    
    return parser.parse_args()

async def main():
    try:
        # Парсим аргументы командной строки
        args = parse_arguments()
        
        # Настраиваем уровень логирования
        logging.basicConfig(
            level=getattr(logging, args.log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler('youtube_chat_parser.log', encoding='utf-8')
            ]
        )
        
        logger = logging.getLogger(__name__)
        logger.info(f"Начало работы парсера для видео: {args.video_id}")
        
        # Создаем и запускаем парсер
        parser = YouTubeChatParser(args.video_id)
        await parser.run()
        
    except KeyboardInterrupt:
        logger.info("Работа парсера прервана пользователем")
    except Exception as e:
        logger.critical(f"Критическая ошибка: {e}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("Работа парсера завершена")

if __name__ == "__main__":
    asyncio.run(main())
