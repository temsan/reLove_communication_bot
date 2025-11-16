"""
Улучшенный сервис для ротации профилей пользователей.
Версия 2.0 с fallback стратегиями и улучшенной надёжностью.
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict

from sqlalchemy.ext.asyncio import AsyncSession

from relove_bot.db.models import User, UserActivityLog
from relove_bot.services.llm_service import llm_service
from relove_bot.services.telegram_service import telegram_service
from relove_bot.repositories.user_profile_repository import UserProfileRepository

logger = logging.getLogger(__name__)


@dataclass
class ProfileUpdateResult:
    """Результат обновления профиля"""
    user_id: int
    success: bool
    strategy_used: str  # 'llm', 'basic', 'hybrid'
    summary: Optional[str] = None
    streams: Optional[List[str]] = None
    error: Optional[str] = None
    llm_tokens_used: int = 0
    processing_time: float = 0.0


class ProfileRotationServiceV2:
    """Улучшенный сервис для ротации профилей"""
    
    # Базовые профили для fallback
    BASIC_PROFILES = [
        {
            'summary': 'Пользователь находится в начале пути самопознания. Проявляет интерес к духовному развитию и трансформации.',
            'streams': ['Путь Героя', 'Пробуждение']
        },
        {
            'summary': 'Активный участник сообщества. Интересуется глубинной психологией и работой с подсознанием.',
            'streams': ['Трансформация Тени', 'Прошлые Жизни']
        },
        {
            'summary': 'Ищет гармонию в отношениях и работу с эмоциональной сферой. Открыт к новому опыту.',
            'streams': ['Открытие Сердца', 'Путь Героя']
        },
        {
            'summary': 'Работает с кармическими паттернами и прошлым опытом. Стремится к освобождению от старых программ.',
            'streams': ['Прошлые Жизни', 'Трансформация Тени']
        },
        {
            'summary': 'Находится на этапе пробуждения сознания. Интересуется метафизикой и духовными практиками.',
            'streams': ['Пробуждение', 'Путь Героя']
        }
    ]
    
    def __init__(
        self,
        session: AsyncSession,
        use_llm: bool = True,
        fallback_to_basic: bool = True,
        llm_timeout: float = 30.0
    ):
        self.session = session
        self.repository = UserProfileRepository(session)
        self.use_llm = use_llm
        self.fallback_to_basic = fallback_to_basic
        self.llm_timeout = llm_timeout
        
        self.stats = {
            'processed': 0,
            'updated': 0,
            'errors': 0,
            'skipped': 0,
            'llm_used': 0,
            'basic_used': 0,
            'hybrid_used': 0
        }
    
    async def update_user_profile(
        self,
        user: User,
        force_strategy: Optional[str] = None
    ) -> ProfileUpdateResult:
        """
        Обновляет профиль пользователя с автоматическим выбором стратегии.
        
        Args:
            user: Пользователь для обновления
            force_strategy: Принудительная стратегия ('llm', 'basic', 'hybrid')
            
        Returns:
            Результат обновления профиля
        """
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Определяем стратегию
            if force_strategy:
                strategy = force_strategy
            else:
                strategy = await self._choose_strategy(user)
            
            # Выполняем обновление по выбранной стратегии
            if strategy == 'llm':
                result = await self._update_with_llm(user)
            elif strategy == 'basic':
                result = await self._update_with_basic(user)
            elif strategy == 'hybrid':
                result = await self._update_with_hybrid(user)
            else:
                raise ValueError(f"Unknown strategy: {strategy}")
            
            # Обновляем статистику
            if result.success:
                self.stats['updated'] += 1
                if result.strategy_used == 'llm':
                    self.stats['llm_used'] += 1
                elif result.strategy_used == 'basic':
                    self.stats['basic_used'] += 1
                elif result.strategy_used == 'hybrid':
                    self.stats['hybrid_used'] += 1
            else:
                self.stats['errors'] += 1
            
            self.stats['processed'] += 1
            
            # Добавляем время обработки
            result.processing_time = asyncio.get_event_loop().time() - start_time
            
            return result
            
        except Exception as e:
            logger.error(f"Error updating profile for user {user.id}: {e}", exc_info=True)
            self.stats['errors'] += 1
            self.stats['processed'] += 1
            
            return ProfileUpdateResult(
                user_id=user.id,
                success=False,
                strategy_used='error',
                error=str(e),
                processing_time=asyncio.get_event_loop().time() - start_time
            )
    
    async def _choose_strategy(self, user: User) -> str:
        """
        Выбирает оптимальную стратегию для пользователя.
        
        Логика:
        - Если есть логи активности и use_llm=True -> 'llm'
        - Если нет логов но есть базовая информация -> 'basic'
        - Если есть частичные данные -> 'hybrid'
        """
        # Проверяем наличие логов активности
        has_activity = await self._has_recent_activity(user.id)
        
        if has_activity and self.use_llm:
            return 'llm'
        elif self.fallback_to_basic:
            return 'basic'
        else:
            return 'hybrid'
    
    async def _has_recent_activity(self, user_id: int, limit: int = 10) -> bool:
        """Проверяет наличие недавней активности"""
        from sqlalchemy import select
        
        query = select(UserActivityLog).where(
            UserActivityLog.user_id == user_id
        ).limit(limit)
        
        result = await self.session.execute(query)
        logs = result.scalars().all()
        
        return len(logs) > 0
    
    async def _update_with_llm(self, user: User) -> ProfileUpdateResult:
        """Обновление профиля через LLM анализ"""
        try:
            # Получаем данные для анализа
            logs = await self._get_recent_logs(user.id, limit=50)
            posts = await self._get_user_posts(user.id)
            
            if not logs and not posts:
                # Fallback к basic если нет данных
                if self.fallback_to_basic:
                    logger.info(f"No data for LLM analysis for user {user.id}, falling back to basic")
                    return await self._update_with_basic(user)
                else:
                    return ProfileUpdateResult(
                        user_id=user.id,
                        success=False,
                        strategy_used='llm',
                        error="No data available for LLM analysis"
                    )
            
            # Формируем промпт
            prompt = self._build_llm_prompt(user, logs, posts)
            
            # Вызываем LLM с таймаутом
            try:
                analysis = await asyncio.wait_for(
                    llm_service.analyze_text(prompt, max_tokens=800),
                    timeout=self.llm_timeout
                )
            except asyncio.TimeoutError:
                logger.warning(f"LLM timeout for user {user.id}")
                if self.fallback_to_basic:
                    return await self._update_with_basic(user)
                raise
            
            if not analysis:
                if self.fallback_to_basic:
                    return await self._update_with_basic(user)
                return ProfileUpdateResult(
                    user_id=user.id,
                    success=False,
                    strategy_used='llm',
                    error="Empty LLM response"
                )
            
            # Парсим ответ
            parsed = self._parse_llm_response(analysis)
            
            if not parsed.get('summary'):
                if self.fallback_to_basic:
                    return await self._update_with_basic(user)
                return ProfileUpdateResult(
                    user_id=user.id,
                    success=False,
                    strategy_used='llm',
                    error="Failed to parse LLM response"
                )
            
            # Сохраняем профиль
            await self._save_profile(
                user,
                summary=parsed['summary'],
                streams=parsed.get('streams', []),
                metadata={
                    'strategy': 'llm',
                    'llm_changes': parsed.get('changes', '')
                }
            )
            
            return ProfileUpdateResult(
                user_id=user.id,
                success=True,
                strategy_used='llm',
                summary=parsed['summary'],
                streams=parsed.get('streams', []),
                llm_tokens_used=len(analysis.split())  # Приблизительная оценка
            )
            
        except Exception as e:
            logger.error(f"LLM update failed for user {user.id}: {e}")
            if self.fallback_to_basic:
                return await self._update_with_basic(user)
            raise
    
    async def _update_with_basic(self, user: User) -> ProfileUpdateResult:
        """Обновление профиля базовым шаблоном"""
        try:
            # Выбираем профиль циклически на основе user_id
            profile = self.BASIC_PROFILES[user.id % len(self.BASIC_PROFILES)]
            
            # Сохраняем профиль
            await self._save_profile(
                user,
                summary=profile['summary'],
                streams=profile['streams'],
                metadata={'strategy': 'basic', 'auto_generated': True}
            )
            
            return ProfileUpdateResult(
                user_id=user.id,
                success=True,
                strategy_used='basic',
                summary=profile['summary'],
                streams=profile['streams']
            )
            
        except Exception as e:
            logger.error(f"Basic update failed for user {user.id}: {e}")
            raise
    
    async def _update_with_hybrid(self, user: User) -> ProfileUpdateResult:
        """Гибридное обновление: пытается LLM, fallback к basic"""
        try:
            # Пытаемся LLM
            result = await self._update_with_llm(user)
            
            if result.success:
                result.strategy_used = 'hybrid'
                return result
            
            # Fallback к basic
            result = await self._update_with_basic(user)
            result.strategy_used = 'hybrid'
            return result
            
        except Exception as e:
            logger.error(f"Hybrid update failed for user {user.id}: {e}")
            # Последняя попытка - basic
            return await self._update_with_basic(user)
    
    async def _get_recent_logs(
        self,
        user_id: int,
        limit: int = 50
    ) -> List[UserActivityLog]:
        """Получает последние логи активности"""
        from sqlalchemy import select
        
        query = select(UserActivityLog).where(
            UserActivityLog.user_id == user_id
        ).order_by(
            UserActivityLog.timestamp.desc()
        ).limit(limit)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def _get_user_posts(self, user_id: int) -> Optional[str]:
        """Получает посты пользователя"""
        try:
            posts = await telegram_service.get_user_posts(user_id, limit=10)
            if posts:
                return "\n\n".join(posts)
            return None
        except Exception as e:
            logger.debug(f"Could not get posts for user {user_id}: {e}")
            return None
    
    def _build_llm_prompt(
        self,
        user: User,
        logs: List[UserActivityLog],
        posts: Optional[str]
    ) -> str:
        """Формирует промпт для LLM"""
        old_summary = user.psychological_summary or "Профиль отсутствует"
        activity_text = self._format_activity_logs(logs) if logs else "Нет данных об активности"
        posts_text = f"\n\nПОСТЫ ПОЛЬЗОВАТЕЛЯ:\n{posts}" if posts else ""
        
        return f"""Обнови психологический профиль пользователя на основе новых данных.

СТАРЫЙ ПРОФИЛЬ:
{old_summary}

ПОСЛЕДНЯЯ АКТИВНОСТЬ:
{activity_text}
{posts_text}

ЗАДАЧА:
Проанализируй данные и создай обновлённый профиль.

Ответь СТРОГО в JSON формате:
{{
  "summary": "краткое описание психологического состояния (2-3 предложения)",
  "streams": ["Поток 1", "Поток 2"],
  "changes": "что изменилось с последнего обновления"
}}

ДОСТУПНЫЕ ПОТОКИ:
- Путь Героя
- Прошлые Жизни
- Открытие Сердца
- Трансформация Тени
- Пробуждение
"""
    
    def _format_activity_logs(self, logs: List[UserActivityLog]) -> str:
        """Форматирует логи активности"""
        lines = []
        for log in logs[:20]:  # Ограничиваем для промпта
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
    
    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """
        Парсит ответ LLM с поддержкой JSON и текстового формата.
        """
        # Пытаемся распарсить как JSON
        try:
            # Ищем JSON в ответе
            start = response.find('{')
            end = response.rfind('}') + 1
            if start != -1 and end > start:
                json_str = response[start:end]
                return json.loads(json_str)
        except json.JSONDecodeError:
            pass
        
        # Fallback: парсим текстовый формат
        result = {}
        lines = response.split('\n')
        
        for line in lines:
            line = line.strip()
            if line.startswith("SUMMARY:") or line.startswith('"summary"'):
                result['summary'] = line.split(':', 1)[1].strip().strip('"')
            elif line.startswith("STREAMS:") or line.startswith('"streams"'):
                streams_str = line.split(':', 1)[1].strip().strip('[]"')
                result['streams'] = [s.strip().strip('"') for s in streams_str.split(',') if s.strip()]
            elif line.startswith("CHANGES:") or line.startswith('"changes"'):
                result['changes'] = line.split(':', 1)[1].strip().strip('"')
        
        return result
    
    async def _save_profile(
        self,
        user: User,
        summary: str,
        streams: List[str],
        metadata: Dict[str, Any]
    ):
        """Сохраняет обновлённый профиль"""
        user.psychological_summary = summary
        user.streams = streams
        
        if not user.markers:
            user.markers = {}
        
        user.markers['profile_updated_at'] = datetime.now().isoformat()
        user.markers.update(metadata)
        
        await self.session.commit()
    
    def get_stats(self) -> Dict[str, Any]:
        """Возвращает статистику обработки"""
        return self.stats.copy()
