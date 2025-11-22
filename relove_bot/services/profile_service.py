"""
Сервис для массового обновления профилей пользователей.
"""
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from relove_bot.db.repository import UserRepository
from relove_bot.utils.gender import detect_gender
from relove_bot.db.models import GenderEnum
from relove_bot.services.prompts import PROFILE_STREAMS_PROMPT
from typing import List, Dict, Union, Optional
from relove_bot.services.llm_service import llm_service
from relove_bot.utils.telegram_client import get_client
from telethon.tl.functions.users import GetFullUserRequest
from relove_bot.services.telegram_service import telegram_service


logger = logging.getLogger(__name__)

class ProfileService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repository = UserRepository(session)
        self.llm_service = llm_service

    @staticmethod
    def validate_user_fields(user_dict):
        missing = []
        for field in ("first_name", "last_name", "username"):
            if not user_dict.get(field):
                missing.append(field)
        return missing

    async def analyze_profile(self, user_id: int, main_channel_id: Optional[str] = None, tg_user=None) -> bool:
        """
        Анализирует профиль пользователя и обновляет его в базе данных.
        
        Args:
            user_id: ID пользователя
            main_channel_id: ID основного канала
            tg_user: Объект пользователя Telegram (опционально)
            
        Returns:
            bool: True если профиль успешно обновлен, False в противном случае
        """
        try:
            # Получаем пользователя из базы данных
            user = await self.user_repository.get_user(user_id)
            if not user:
                logger.warning(f"Пользователь {user_id} не найден в базе данных")
                return False

            # Получаем информацию о пользователе из Telegram
            if not tg_user:
                try:
                    tg_user = await telegram_service.get_full_user(user_id)
                except Exception as e:
                    logger.warning(f"Не удалось получить информацию о пользователе {user_id} по ID: {e}")
                    return False

            if not tg_user:
                logger.warning(f"Не удалось получить информацию о пользователе {user_id}")
                return False

            # Получаем био и посты пользователя
            bio = getattr(tg_user, 'about', '') or ''
            posts_text = ''

            try:
                # Получаем посты из канала обсуждений
                if main_channel_id:
                    posts = await telegram_service.get_user_posts_in_channel(main_channel_id, user_id)
                    posts_text = '\n'.join(posts) if posts else ''
            except Exception as e:
                logger.warning(f"Не удалось получить посты пользователя {user_id}: {e}")

            # Получаем психологический анализ
            try:
                summary, photo_bytes, streams = await telegram_service.get_user_psychological_summary(
                    user_id=user_id,
                    tg_user=tg_user,
                    bio=bio,
                    posts_text=posts_text
                )
            except Exception as e:
                logger.error(f"Ошибка при получении психологического анализа для пользователя {user_id}: {e}")
                return False

            if not summary:
                logger.warning(f"Не удалось получить психологический анализ для пользователя {user_id}")
                return False

            # Обновляем профиль пользователя
            try:
                await self.user_repository.update(
                    user_id,
                    {
                        'profile': summary,
                        'streams': streams or [],
                        'photo_jpeg': photo_bytes if photo_bytes else None
                    }
                )
                logger.info(f"Профиль пользователя {user_id} успешно обновлен")
                return True
            except Exception as e:
                logger.error(f"Ошибка при обновлении профиля пользователя {user_id}: {e}")
                return False

        except Exception as e:
            logger.error(f"Ошибка при анализе профиля пользователя {user_id}: {e}")
            return False

    async def get_user_streams(self, user_id: int) -> List[str]:
        """
        Получает потоки пользователя.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            List[str]: Список потоков пользователя
        """
        try:
            # Получаем профиль пользователя
            profile = await self.user_repository.get_user(user_id)
            if not profile:
                return []
            
            # Анализируем текстовые поля
            text_parts = []
            if profile.first_name:
                text_parts.append(f"Имя: {profile.first_name}")
            if profile.last_name:
                text_parts.append(f"Фамилия: {profile.last_name}")
            if profile.username:
                text_parts.append(f"Логин: @{profile.username}")
            if profile.bio:
                text_parts.append(f"О себе: {profile.bio}")
            
            if not text_parts:
                return []
            
            prompt = "\n".join(text_parts)
            streams_str = await llm_service.analyze_text(prompt, system_prompt=PROFILE_STREAMS_PROMPT, max_tokens=16)
            
            if not streams_str:
                return []
            
            # Разбиваем строку на потоки
            streams = [s.strip() for s in streams_str.split(',')]
            return [s for s in streams if s]
            
        except Exception as e:
            logger.error(f"Ошибка при получении потоков пользователя: {e}", exc_info=True)
            return []

    async def get_user_posts(self, user_id: int, main_channel_id: Union[int, str]) -> List[str]:
        """Получить посты пользователя из канала"""
        try:
            client = await get_client()
            if not client.is_connected():
                await client.connect()
                
            # Получаем канал по ID или username
            try:
                channel = await client.get_entity(main_channel_id)
            except ValueError as e:
                logger.warning(f"Не удалось получить канал {main_channel_id}: {str(e)}")
                return []
            except Exception as e:
                logger.warning(f"Ошибка при получении канала {main_channel_id}: {str(e)}")
                return []
                
            posts = []
            try:
                async for message in client.iter_messages(channel, from_user=user_id):
                    if message and hasattr(message, 'text') and message.text:
                        posts.append(message.text)
            except Exception as e:
                if "Chat admin privileges are required" in str(e):
                    logger.warning(f"Недостаточно прав для получения постов пользователя {user_id} из канала {main_channel_id}")
                else:
                    logger.warning(f"Ошибка при получении постов пользователя {user_id}: {str(e)}")
                return posts  # Возвращаем уже полученные посты
                    
            return posts
        except Exception as e:
            logger.warning(f"Не удалось получить посты пользователя {user_id}: {str(e)}")
            return []
