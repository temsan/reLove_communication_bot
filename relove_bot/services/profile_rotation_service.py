"""
Сервис для автоматической ротации и актуализации профилей пользователей.
Обновляет psychological_summary, streams и markers на основе истории активности.
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from relove_bot.db.models import User, UserActivityLog
from relove_bot.services.llm_service import llm_service
from relove_bot.services.telegram_service import telegram_service

logger = logging.getLogger(__name__)


class ProfileRotationService:
    """Сервис для ротации профилей пользователей"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.stats = {
            'processed': 0,
            'updated': 0,
            'errors': 0,
            'skipped': 0
        }
    
    async def rotate_profiles(self):
        """Ротация профилей активных пользователей"""
        logger.info("Starting profile rotation...")
        
        try:
            # Получаем пользователей для обновления
            users = await self.get_users_for_rotation()
            
            if not users:
                logger.info("No users found for rotation")
                return
            
            logger.info(f"Found {len(users)} users for rotation")
            
            # Обрабатываем пачками по 10 пользователей
            batch_size = 10
            for i in range(0, len(users), batch_size):
                batch = users[i:i + batch_size]
                await self.process_batch(batch)
                
                # Пауза между пачками
                if i + batch_size < len(users):
                    await asyncio.sleep(5)
            
            # Логируем статистику
            await self.log_rotation_stats()
            
        except Exception as e:
            logger.error(f"Error in profile rotation: {e}", exc_info=True)
    
    async def get_users_for_rotation(self) -> List[User]:
        """
        Получает пользователей для ротации.
        Критерии:
        - last_seen_date в последние 30 дней
        - markers['profile_updated_at'] старше 7 дней или отсутствует
        """
        try:
            # Дата 30 дней назад
            thirty_days_ago = datetime.now() - timedelta(days=30)
            
            # Дата 7 дней назад для проверки обновления профиля
            seven_days_ago = datetime.now() - timedelta(days=7)
            
            # Базовый запрос: активные пользователи, виденные за последние 30 дней
            query = select(User).where(
                and_(
                    User.is_active == True,
                    User.last_seen_date >= thirty_days_ago
                )
            ).order_by(User.last_seen_date.desc())
            
            result = await self.session.execute(query)
            all_users = result.scalars().all()
            
            # Фильтруем по возрасту профиля
            users_to_update = []
            for user in all_users:
                markers = user.markers or {}
                profile_updated_at_str = markers.get('profile_updated_at')
                
                if profile_updated_at_str:
                    try:
                        profile_updated_at = datetime.fromisoformat(profile_updated_at_str)
                        if profile_updated_at < seven_days_ago:
                            users_to_update.append(user)
                    except (ValueError, TypeError):
                        # Если формат неверный - обновляем
                        users_to_update.append(user)
                else:
                    # Если profile_updated_at отсутствует - обновляем
                    users_to_update.append(user)
            
            logger.info(
                f"Found {len(users_to_update)} users with outdated profiles "
                f"out of {len(all_users)} active users"
            )
            
            return users_to_update
            
        except Exception as e:
            logger.error(f"Error getting users for rotation: {e}", exc_info=True)
            return []
    
    async def process_batch(self, users: List[User]):
        """Обрабатывает пачку пользователей"""
        for user in users:
            try:
                await self.update_user_profile(user)
                self.stats['processed'] += 1
            except Exception as e:
                logger.error(f"Error updating user {user.id}: {e}", exc_info=True)
                self.stats['errors'] += 1
    
    async def update_user_profile(self, user: User):
        """
        Обновляет профиль пользователя.
        Получает последние логи, посты из Telegram, анализирует через LLM.
        """
        try:
            logger.info(f"Updating profile for user {user.id}")
            
            # Получаем последние 50 записей из UserActivityLog
            logs = await self.get_recent_logs(user.id, limit=50)
            
            if not logs:
                logger.info(f"No activity logs for user {user.id}, skipping")
                self.stats['skipped'] += 1
                return
            
            # Получаем посты пользователя из Telegram (если доступно)
            posts = await self.get_user_posts(user.id)
            
            # Формируем промпт для LLM
            prompt = self.build_update_prompt(user, logs, posts)
            
            # Получаем обновлённый анализ от LLM
            analysis = await llm_service.analyze_text(
                prompt,
                max_tokens=800
            )
            
            if not analysis:
                logger.warning(f"Empty analysis for user {user.id}")
                self.stats['skipped'] += 1
                return
            
            # Парсим и сохраняем обновлённый профиль
            await self.save_updated_profile(user, analysis)
            
            self.stats['updated'] += 1
            logger.info(f"Successfully updated profile for user {user.id}")
            
        except Exception as e:
            logger.error(f"Error updating profile for user {user.id}: {e}", exc_info=True)
            raise
    
    async def get_recent_logs(self, user_id: int, limit: int = 50) -> List[UserActivityLog]:
        """Получает последние логи активности пользователя"""
        try:
            query = select(UserActivityLog).where(
                UserActivityLog.user_id == user_id
            ).order_by(
                UserActivityLog.timestamp.desc()
            ).limit(limit)
            
            result = await self.session.execute(query)
            return list(result.scalars().all())
            
        except Exception as e:
            logger.error(f"Error getting logs for user {user_id}: {e}")
            return []
    
    async def get_user_posts(self, user_id: int) -> Optional[str]:
        """Получает посты пользователя из Telegram через telegram_service"""
        try:
            # Используем telegram_service для получения постов
            posts = await telegram_service.get_user_posts(user_id, limit=10)
            
            if posts:
                return "\n\n".join(posts)
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting posts for user {user_id}: {e}")
            return None
    
    def build_update_prompt(
        self, 
        user: User, 
        logs: List[UserActivityLog], 
        posts: Optional[str]
    ) -> str:
        """Формирует промпт для обновления профиля"""
        
        # Старый профиль
        old_summary = user.psychological_summary or "Профиль отсутствует"
        
        # История активности
        activity_text = self._format_activity_logs(logs)
        
        # Посты
        posts_text = f"\n\nПОСТЫ ПОЛЬЗОВАТЕЛЯ:\n{posts}" if posts else ""
        
        prompt = f"""Обнови психологический профиль пользователя на основе новых данных.

СТАРЫЙ ПРОФИЛЬ:
{old_summary}

ПОСЛЕДНЯЯ АКТИВНОСТЬ (последние 50 действий):
{activity_text}
{posts_text}

ЗАДАЧА:
1. Проанализируй изменения в поведении и интересах
2. Обнови psychological_summary (краткое описание психологического состояния)
3. Определи подходящие потоки reLove (список через запятую)

ПОТОКИ reLove:
- Путь Героя (трансформация через 12 этапов)
- Прошлые Жизни (работа с кармой)
- Открытие Сердца (работа с любовью)
- Трансформация Тени (интеграция тьмы)
- Пробуждение (выход из матрицы)

Ответь в формате:
SUMMARY: [обновлённое краткое описание психологического состояния, 2-3 предложения]
STREAMS: [список потоков через запятую]
CHANGES: [что изменилось с последнего обновления]
"""
        
        return prompt
    
    def _format_activity_logs(self, logs: List[UserActivityLog]) -> str:
        """Форматирует логи активности для промпта"""
        lines = []
        
        for log in logs:
            timestamp = log.timestamp.strftime("%d.%m %H:%M")
            activity_type = log.activity_type
            
            details = ""
            if log.details:
                if 'text' in log.details:
                    details = f": {log.details['text'][:100]}"
                elif 'command' in log.details:
                    details = f": {log.details['command']}"
            
            lines.append(f"[{timestamp}] {activity_type}{details}")
        
        return "\n".join(lines)
    
    async def save_updated_profile(self, user: User, analysis: str):
        """Парсит анализ и сохраняет обновлённый профиль"""
        try:
            # Парсим ответ LLM
            summary = ""
            streams = []
            changes = ""
            
            for line in analysis.split('\n'):
                line = line.strip()
                if line.startswith("SUMMARY:"):
                    summary = line.replace("SUMMARY:", "").strip()
                elif line.startswith("STREAMS:"):
                    streams_str = line.replace("STREAMS:", "").strip()
                    streams = [s.strip() for s in streams_str.split(',') if s.strip()]
                elif line.startswith("CHANGES:"):
                    changes = line.replace("CHANGES:", "").strip()
            
            # Обновляем пользователя
            if summary:
                user.psychological_summary = summary
            
            if streams:
                user.streams = streams
            
            # Обновляем markers
            if not user.markers:
                user.markers = {}
            
            user.markers['profile_updated_at'] = datetime.now().isoformat()
            
            if changes:
                user.markers['last_profile_changes'] = changes
            
            await self.session.commit()
            
            logger.info(
                f"Saved updated profile for user {user.id}: "
                f"streams={streams}, changes={changes[:50] if changes else 'none'}"
            )
            
        except Exception as e:
            logger.error(f"Error saving profile for user {user.id}: {e}")
            await self.session.rollback()
            raise
    
    async def log_rotation_stats(self):
        """Логирует статистику ротации"""
        logger.info(
            f"Profile rotation completed: "
            f"processed={self.stats['processed']}, "
            f"updated={self.stats['updated']}, "
            f"errors={self.stats['errors']}, "
            f"skipped={self.stats['skipped']}"
        )
