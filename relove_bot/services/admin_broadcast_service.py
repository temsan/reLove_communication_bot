"""
Сервис для админ-рассылки с фильтрацией пользователей.
"""
import asyncio
import logging
from typing import List, Dict, Any

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from relove_bot.db.models import User, JourneyStageEnum, GenderEnum
from relove_bot.utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class AdminBroadcastService:
    """Сервис для админ-рассылки"""
    
    def __init__(self, session: AsyncSession, bot: Bot):
        self.session = session
        self.bot = bot
    
    async def broadcast_message(
        self,
        message: str,
        criteria: Dict[str, Any]
    ) -> Dict[str, int]:
        """
        Отправляет рассылку по критериям.
        
        Args:
            message: Текст сообщения
            criteria: Критерии фильтрации
        
        Returns:
            Статистика: {sent, errors, blocked}
        """
        try:
            # Получаем пользователей по критериям
            users = await self.get_users_by_criteria(criteria)
            
            if not users:
                logger.info("No users found for broadcast")
                return {'sent': 0, 'errors': 0, 'blocked': 0}
            
            logger.info(f"Broadcasting to {len(users)} users")
            
            stats = {
                'sent': 0,
                'errors': 0,
                'blocked': 0
            }
            
            # Rate limiter: 30 сообщений в секунду
            rate_limiter = RateLimiter(30, 1)
            
            for user in users:
                async with rate_limiter:
                    try:
                        await self.bot.send_message(user.id, message)
                        stats['sent'] += 1
                    except TelegramForbiddenError:
                        # Пользователь заблокировал бота
                        await self.mark_user_inactive(user.id)
                        stats['blocked'] += 1
                    except Exception as e:
                        logger.error(f"Error sending to user {user.id}: {e}")
                        stats['errors'] += 1
            
            logger.info(
                f"Broadcast completed: sent={stats['sent']}, "
                f"errors={stats['errors']}, blocked={stats['blocked']}"
            )
            
            return stats
            
        except Exception as e:
            logger.error(f"Error in broadcast: {e}")
            return {'sent': 0, 'errors': 0, 'blocked': 0}
    
    async def get_users_by_criteria(
        self,
        criteria: Dict[str, Any]
    ) -> List[User]:
        """
        Получает пользователей по критериям.
        
        Поддерживаемые критерии:
        - gender: male/female
        - journey_stage: название этапа
        - streams: список потоков
        - markers: словарь маркеров
        """
        try:
            # Базовый запрос: только активные пользователи
            query = select(User).where(User.is_active == True)
            
            # Фильтр по полу
            if 'gender' in criteria:
                gender_str = criteria['gender']
                if gender_str == 'male':
                    query = query.where(User.gender == GenderEnum.male)
                elif gender_str == 'female':
                    query = query.where(User.gender == GenderEnum.female)
            
            # Фильтр по этапу пути героя
            if 'journey_stage' in criteria:
                stage_str = criteria['journey_stage']
                # Пробуем найти этап по значению
                for stage in JourneyStageEnum:
                    if stage.value == stage_str or stage.name == stage_str:
                        query = query.where(User.last_journey_stage == stage)
                        break
            
            # Фильтр по потокам
            if 'streams' in criteria:
                streams = criteria['streams']
                if isinstance(streams, str):
                    streams = [streams]
                
                for stream in streams:
                    query = query.where(User.streams.contains([stream]))
            
            # Фильтр по маркерам
            if 'markers' in criteria:
                markers = criteria['markers']
                for key, value in markers.items():
                    query = query.where(
                        User.markers[key].astext == str(value)
                    )
            
            result = await self.session.execute(query)
            users = list(result.scalars().all())
            
            logger.info(f"Found {len(users)} users matching criteria")
            
            return users
            
        except Exception as e:
            logger.error(f"Error getting users by criteria: {e}")
            return []
    
    def parse_criteria(self, criteria_str: str) -> Dict[str, Any]:
        """
        Парсит строку критериев в словарь.
        
        Формат: "gender=female,journey_stage=CALL_TO_ADVENTURE,streams=Путь Героя"
        
        Args:
            criteria_str: Строка с критериями
        
        Returns:
            Словарь критериев
        """
        criteria = {}
        
        if not criteria_str:
            return criteria
        
        parts = criteria_str.split(',')
        
        for part in parts:
            part = part.strip()
            if '=' not in part:
                continue
            
            key, value = part.split('=', 1)
            key = key.strip()
            value = value.strip()
            
            if key == 'streams':
                # Потоки могут быть списком
                if key not in criteria:
                    criteria[key] = []
                criteria[key].append(value)
            elif key == 'markers':
                # Маркеры - это вложенный словарь
                if key not in criteria:
                    criteria[key] = {}
                # Формат: markers.key=value
                if '.' in key:
                    _, marker_key = key.split('.', 1)
                    criteria['markers'][marker_key] = value
            else:
                criteria[key] = value
        
        return criteria
    
    async def mark_user_inactive(self, user_id: int):
        """Помечает пользователя как неактивного"""
        try:
            result = await self.session.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if user:
                user.is_active = False
                await self.session.commit()
                logger.info(f"Marked user {user_id} as inactive")
                
        except Exception as e:
            logger.error(f"Error marking user {user_id} as inactive: {e}")
            await self.session.rollback()
