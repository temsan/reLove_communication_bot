"""
Улучшенный скрипт для массового обновления профилей пользователей.
Версия 2.0 с поддержкой различных стратегий и улучшенной производительностью.

Использование:
    # Быстрое заполнение базовыми шаблонами
    python scripts/fill_profiles_v2.py --strategy basic --all
    
    # LLM анализ для пользователей с активностью
    python scripts/fill_profiles_v2.py --strategy llm --all
    
    # Гибридный подход (LLM где возможно, basic для остальных)
    python scripts/fill_profiles_v2.py --strategy hybrid --all
    
    # Обновление только устаревших профилей
    python scripts/fill_profiles_v2.py --strategy llm --outdated --days 7
    
    # Параллельная обработка
    python scripts/fill_profiles_v2.py --strategy hybrid --all --workers 3
    
    # Dry-run режим
    python scripts/fill_profiles_v2.py --strategy basic --all --dry-run
"""
import asyncio
import logging
import sys
import argparse
from pathlib import Path
from typing import List
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from tqdm import tqdm

from relove_bot.db.models import User
from relove_bot.db.session import async_session
from relove_bot.services.profile_rotation_service_v2 import (
    ProfileRotationServiceV2,
    ProfileUpdateResult
)
from relove_bot.repositories.user_profile_repository import UserProfileRepository

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/fill_profiles_v2.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class ProfileFillOrchestrator:
    """Оркестратор процесса заполнения профилей"""
    
    def __init__(
        self,
        strategy: str = 'hybrid',
        batch_size: int = 10,
        workers: int = 1,
        dry_run: bool = False
    ):
        self.strategy = strategy
        self.batch_size = batch_size
        self.workers = workers
        self.dry_run = dry_run
        
        self.results: List[ProfileUpdateResult] = []
    
    async def fill_profiles(
        self,
        users: List[User],
        show_progress: bool = True
    ):
        """
        Заполняет профили для списка пользователей.
        
        Args:
            users: Список пользователей для обработки
            show_progress: Показывать прогресс-бар
        """
        if not users:
            logger.info("No users to process")
            return
        
        logger.info(
            f"Starting profile fill: {len(users)} users, "
            f"strategy={self.strategy}, workers={self.workers}, "
            f"dry_run={self.dry_run}"
        )
        
        if self.dry_run:
            logger.info("DRY RUN MODE - no changes will be saved")
            return
        
        # Создаём прогресс-бар
        pbar = tqdm(total=len(users), desc="Processing profiles") if show_progress else None
        
        try:
            # Обрабатываем пачками
            for i in range(0, len(users), self.batch_size):
                batch = users[i:i + self.batch_size]
                
                # Параллельная обработка внутри пачки
                if self.workers > 1:
                    results = await self._process_batch_parallel(batch)
                else:
                    results = await self._process_batch_sequential(batch)
                
                self.results.extend(results)
                
                if pbar:
                    pbar.update(len(batch))
                
                # Пауза между пачками
                if i + self.batch_size < len(users):
                    await asyncio.sleep(1)
        
        finally:
            if pbar:
                pbar.close()
        
        # Выводим статистику
        self._print_statistics()
    
    async def _process_batch_sequential(
        self,
        batch: List[User]
    ) -> List[ProfileUpdateResult]:
        """Последовательная обработка пачки"""
        results = []
        
        async with async_session() as session:
            service = ProfileRotationServiceV2(
                session,
                use_llm=(self.strategy in ['llm', 'hybrid']),
                fallback_to_basic=(self.strategy == 'hybrid')
            )
            
            for user in batch:
                try:
                    result = await service.update_user_profile(
                        user,
                        force_strategy=self.strategy if self.strategy != 'hybrid' else None
                    )
                    results.append(result)
                except Exception as e:
                    logger.error(f"Error processing user {user.id}: {e}")
                    results.append(ProfileUpdateResult(
                        user_id=user.id,
                        success=False,
                        strategy_used='error',
                        error=str(e)
                    ))
        
        return results
    
    async def _process_batch_parallel(
        self,
        batch: List[User]
    ) -> List[ProfileUpdateResult]:
        """Параллельная обработка пачки"""
        # Создаём задачи для параллельной обработки
        tasks = []
        
        for user in batch:
            task = self._process_single_user(user)
            tasks.append(task)
        
        # Выполняем параллельно с ограничением
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Обрабатываем исключения
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Error processing user {batch[i].id}: {result}")
                processed_results.append(ProfileUpdateResult(
                    user_id=batch[i].id,
                    success=False,
                    strategy_used='error',
                    error=str(result)
                ))
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def _process_single_user(self, user: User) -> ProfileUpdateResult:
        """Обрабатывает одного пользователя"""
        async with async_session() as session:
            service = ProfileRotationServiceV2(
                session,
                use_llm=(self.strategy in ['llm', 'hybrid']),
                fallback_to_basic=(self.strategy == 'hybrid')
            )
            
            return await service.update_user_profile(
                user,
                force_strategy=self.strategy if self.strategy != 'hybrid' else None
            )
    
    def _print_statistics(self):
        """Выводит статистику обработки"""
        if not self.results:
            return
        
        total = len(self.results)
        successful = sum(1 for r in self.results if r.success)
        failed = total - successful
        
        # Статистика по стратегиям
        llm_count = sum(1 for r in self.results if r.strategy_used == 'llm')
        basic_count = sum(1 for r in self.results if r.strategy_used == 'basic')
        hybrid_count = sum(1 for r in self.results if r.strategy_used == 'hybrid')
        
        # Производительность
        total_time = sum(r.processing_time for r in self.results)
        avg_time = total_time / total if total > 0 else 0
        
        # Токены LLM
        total_tokens = sum(r.llm_tokens_used for r in self.results)
        
        logger.info("\n" + "="*60)
        logger.info("СТАТИСТИКА ОБРАБОТКИ")
        logger.info("="*60)
        logger.info(f"Всего обработано: {total}")
        logger.info(f"Успешно: {successful} ({successful/total*100:.1f}%)")
        logger.info(f"Ошибок: {failed} ({failed/total*100:.1f}%)")
        logger.info("")
        logger.info("Стратегии:")
        logger.info(f"  LLM: {llm_count}")
        logger.info(f"  Basic: {basic_count}")
        logger.info(f"  Hybrid: {hybrid_count}")
        logger.info("")
        logger.info("Производительность:")
        logger.info(f"  Общее время: {total_time:.2f}с")
        logger.info(f"  Среднее время на пользователя: {avg_time:.2f}с")
        logger.info(f"  Токенов LLM использовано: {total_tokens}")
        logger.info("="*60)


async def main():
    """Главная функция"""
    parser = argparse.ArgumentParser(
        description="Массовое обновление профилей пользователей v2.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    # Режим работы
    mode_group = parser.add_mutually_exclusive_group(required=False)
    mode_group.add_argument(
        '--all',
        action='store_true',
        help='Обработать всех пользователей без профилей'
    )
    mode_group.add_argument(
        '--outdated',
        action='store_true',
        help='Обработать пользователей с устаревшими профилями'
    )
    mode_group.add_argument(
        '--user-id',
        type=int,
        help='ID конкретного пользователя'
    )
    
    # Стратегия
    parser.add_argument(
        '--strategy',
        choices=['basic', 'llm', 'hybrid'],
        default='hybrid',
        help='Стратегия заполнения профилей (по умолчанию: hybrid)'
    )
    
    # Параметры обработки
    parser.add_argument(
        '--batch-size',
        type=int,
        default=10,
        help='Размер пачки для обработки (по умолчанию: 10)'
    )
    parser.add_argument(
        '--workers',
        type=int,
        default=1,
        help='Количество параллельных воркеров (по умолчанию: 1)'
    )
    parser.add_argument(
        '--days',
        type=int,
        default=7,
        help='Количество дней для определения устаревшего профиля (по умолчанию: 7)'
    )
    
    # Дополнительные опции
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Режим проверки без сохранения изменений'
    )
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Показать только статистику без обработки'
    )
    
    args = parser.parse_args()
    
    # Проверяем что указан режим работы или --stats
    if not (args.all or args.outdated or args.user_id or args.stats):
        parser.error("one of the arguments --all --outdated --user-id --stats is required")
    
    # Показываем статистику
    if args.stats:
        async with async_session() as session:
            repo = UserProfileRepository(session)
            stats = await repo.get_profile_statistics()
            
            print("\n" + "="*60)
            print("СТАТИСТИКА ПРОФИЛЕЙ")
            print("="*60)
            print(f"Всего пользователей: {stats['total_users']}")
            print(f"С профилями: {stats['with_profiles']}")
            print(f"Без профилей: {stats['without_profiles']}")
            print(f"Активных: {stats['active_users']}")
            print(f"С потоками: {stats['with_streams']}")
            print(f"Процент заполнения: {stats['completion_rate']}%")
            print("="*60)
        return
    
    # Получаем пользователей для обработки
    async with async_session() as session:
        repo = UserProfileRepository(session)
        
        if args.all:
            users = await repo.get_users_without_profiles()
            logger.info(f"Found {len(users)} users without profiles")
        elif args.outdated:
            users = await repo.get_users_with_outdated_profiles(days_threshold=args.days)
            logger.info(f"Found {len(users)} users with outdated profiles")
        elif args.user_id:
            from sqlalchemy import select
            result = await session.execute(
                select(User).where(User.id == args.user_id)
            )
            user = result.scalar_one_or_none()
            if not user:
                logger.error(f"User {args.user_id} not found")
                return
            users = [user]
        else:
            users = []
    
    if not users:
        logger.info("No users to process")
        return
    
    # Создаём оркестратор и запускаем обработку
    orchestrator = ProfileFillOrchestrator(
        strategy=args.strategy,
        batch_size=args.batch_size,
        workers=args.workers,
        dry_run=args.dry_run
    )
    
    await orchestrator.fill_profiles(users)


if __name__ == "__main__":
    asyncio.run(main())
