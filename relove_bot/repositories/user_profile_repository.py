"""
Репозиторий для работы с профилями пользователей.
Оптимизированные SQL-запросы для фильтрации и обновления.
"""
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from sqlalchemy import select, and_, or_, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from relove_bot.db.models import User

logger = logging.getLogger(__name__)


class UserProfileRepository:
    """Репозиторий для работы с профилями пользователей"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_users_without_profiles(
        self,
        limit: Optional[int] = None
    ) -> List[User]:
        """
        Получает пользователей без психологических профилей.
        
        Args:
            limit: Максимальное количество пользователей
            
        Returns:
            Список пользователей без профилей
        """
        query = select(User).where(
            and_(
                User.is_active == True,
                or_(
                    User.psychological_summary == None,
                    User.psychological_summary == ''
                )
            )
        ).order_by(User.id)
        
        if limit:
            query = query.limit(limit)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def get_users_with_outdated_profiles(
        self,
        days_threshold: int = 7,
        limit: Optional[int] = None
    ) -> List[User]:
        """
        Получает пользователей с устаревшими профилями.
        
        Критерии:
        - Профиль обновлялся более N дней назад
        - Или markers['profile_updated_at'] отсутствует
        
        Args:
            days_threshold: Количество дней для определения устаревшего профиля
            limit: Максимальное количество пользователей
            
        Returns:
            Список пользователей с устаревшими профилями
        """
        threshold_date = datetime.now() - timedelta(days=days_threshold)
        threshold_iso = threshold_date.isoformat()
        
        # Используем JSONB оператор для фильтрации
        query = select(User).where(
            and_(
                User.is_active == True,
                User.psychological_summary != None,
                or_(
                    # markers['profile_updated_at'] отсутствует
                    ~User.markers.has_key('profile_updated_at'),  # type: ignore
                    # или старше threshold
                    text(f"(markers->>'profile_updated_at')::timestamp < '{threshold_iso}'")
                )
            )
        ).order_by(User.last_seen_date.desc())
        
        if limit:
            query = query.limit(limit)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def get_users_with_activity(
        self,
        days_threshold: int = 30,
        limit: Optional[int] = None
    ) -> List[User]:
        """
        Получает активных пользователей за последние N дней.
        
        Args:
            days_threshold: Количество дней для определения активности
            limit: Максимальное количество пользователей
            
        Returns:
            Список активных пользователей
        """
        threshold_date = datetime.now() - timedelta(days=days_threshold)
        
        query = select(User).where(
            and_(
                User.is_active == True,
                User.last_seen_date >= threshold_date
            )
        ).order_by(User.last_seen_date.desc())
        
        if limit:
            query = query.limit(limit)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def update_profile_batch(
        self,
        updates: List[Dict[str, Any]]
    ) -> int:
        """
        Пакетное обновление профилей пользователей.
        
        Args:
            updates: Список словарей с обновлениями
                     Формат: {'user_id': int, 'summary': str, 'streams': list, 'markers': dict}
        
        Returns:
            Количество обновлённых пользователей
        """
        updated_count = 0
        
        for update_data in updates:
            user_id = update_data.get('user_id')
            if not user_id:
                continue
            
            result = await self.session.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                continue
            
            # Обновляем поля
            if 'summary' in update_data:
                user.psychological_summary = update_data['summary']
            
            if 'streams' in update_data:
                user.streams = update_data['streams']
            
            if 'markers' in update_data:
                if not user.markers:
                    user.markers = {}
                user.markers.update(update_data['markers'])
            
            # Обновляем timestamp
            if not user.markers:
                user.markers = {}
            user.markers['profile_updated_at'] = datetime.now().isoformat()
            
            updated_count += 1
        
        await self.session.commit()
        return updated_count
    
    async def get_profile_statistics(self) -> Dict[str, int]:
        """
        Получает статистику по профилям.
        
        Returns:
            Словарь со статистикой
        """
        # Всего пользователей
        total_result = await self.session.execute(
            select(func.count(User.id))
        )
        total = total_result.scalar() or 0
        
        # С профилями
        with_profiles_result = await self.session.execute(
            select(func.count(User.id)).where(
                and_(
                    User.psychological_summary != None,
                    User.psychological_summary != ''
                )
            )
        )
        with_profiles = with_profiles_result.scalar() or 0
        
        # Активные
        active_result = await self.session.execute(
            select(func.count(User.id)).where(User.is_active == True)
        )
        active = active_result.scalar() or 0
        
        # С потоками
        with_streams_result = await self.session.execute(
            select(func.count(User.id)).where(
                User.streams != None
            )
        )
        with_streams = with_streams_result.scalar() or 0
        
        return {
            'total_users': total,
            'with_profiles': with_profiles,
            'without_profiles': total - with_profiles,
            'active_users': active,
            'with_streams': with_streams,
            'completion_rate': round((with_profiles / total * 100) if total > 0 else 0, 2)
        }
    
    async def mark_profile_as_updated(
        self,
        user_id: int,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Отмечает профиль как обновлённый.
        
        Args:
            user_id: ID пользователя
            metadata: Дополнительные метаданные для сохранения
            
        Returns:
            True если успешно, False если пользователь не найден
        """
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            return False
        
        if not user.markers:
            user.markers = {}
        
        user.markers['profile_updated_at'] = datetime.now().isoformat()
        
        if metadata:
            user.markers.update(metadata)
        
        await self.session.commit()
        return True
