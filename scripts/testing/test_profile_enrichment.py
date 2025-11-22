"""
Тестирование заполнения профилей пользователей в разных кейсах.
"""
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from relove_bot.db.session import async_session
from relove_bot.db.models import User, GenderEnum
from relove_bot.services.profile_enrichment import (
    determine_journey_stage,
    create_metaphysical_profile,
    determine_streams
)
from sqlalchemy import select

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Тестовые профили для разных кейсов
TEST_PROFILES = {
    "beginner": """
Пользователь только начинает свой путь. Чувствует дискомфорт в текущей жизни,
но не знает, что делать. Много жалоб на обстоятельства, работу, отношения.
Ищет внешние причины проблем. Интересуется саморазвитием, но пока только читает книги.
Страх перемен, откладывает действия. Хочет изменений, но боится выйти из зоны комфорта.
    """,
    
    "seeker": """
Активно ищет свой путь. Прошёл несколько тренингов, читает много литературы.
Понимает, что проблемы внутри, но ещё не знает, как с ними работать.
Есть опыт медитаций, практик осознанности. Чувствует зов к чему-то большему.
Готов к изменениям, но нужна поддержка и направление. Открыт новому опыту.
    """,
    
    "transformer": """
Активно трансформирует свою жизнь. Прошёл через глубокие кризисы и вышел обновлённым.
Работает с тенью, интегрирует разные части себя. Понимает свои паттерны и триггеры.
Практикует регулярно, видит результаты. Готов идти в самые тёмные уголки души.
Начинает помогать другим, делится опытом. Чувствует связь с чем-то большим.
    """,
    
    "dark_path": """
Человек в глубоком кризисе. Депрессия, саморазрушение, потеря смысла.
Много гнева, обиды на мир. Чувство жертвы, все виноваты кроме него.
Закрыт от людей, не доверяет никому. Ищет спасения, но отвергает помощь.
Застрял в прошлом, не может отпустить обиды. Страдание стало привычным.
    """,
    
    "light_path": """
Человек в состоянии любви и принятия. Прошёл через трансформацию и вышел к свету.
Видит красоту во всём, даже в боли. Принимает себя и других такими, какие есть.
Транслирует любовь и поддержку. Помогает другим на их пути. Чувствует единство.
Живёт в потоке, доверяет жизни. Благодарен за всё, что происходит.
    """,
    
    "empty": """
Краткий профиль без деталей.
    """,
}


async def test_profile_enrichment(profile_name: str, profile_text: str):
    """Тестирует обогащение одного профиля."""
    logger.info(f"\n{'='*60}")
    logger.info(f"Testing profile: {profile_name}")
    logger.info(f"{'='*60}")
    
    # 1. Определяем этап пути героя
    logger.info("\n1. Determining journey stage...")
    hero_stage = await determine_journey_stage(profile_text)
    if hero_stage:
        logger.info(f"✅ Hero stage: {hero_stage.value}")
    else:
        logger.warning("❌ Could not determine hero stage")
    
    # 2. Создаём метафизический профиль
    logger.info("\n2. Creating metaphysical profile...")
    metaphysics = await create_metaphysical_profile(profile_text)
    if metaphysics:
        logger.info(f"✅ Metaphysics:")
        logger.info(f"   Planet: {metaphysics.get('planet')}")
        logger.info(f"   Karma: {metaphysics.get('karma')}")
        logger.info(f"   Balance: {metaphysics.get('light_dark_balance')}")
    else:
        logger.warning("❌ Could not create metaphysical profile")
    
    # 3. Определяем потоки
    logger.info("\n3. Determining streams...")
    streams = await determine_streams(profile_text)
    if streams:
        logger.info(f"✅ Streams: {', '.join(streams)}")
    else:
        logger.warning("❌ Could not determine streams")
    
    return {
        'hero_stage': hero_stage,
        'metaphysics': metaphysics,
        'streams': streams
    }


async def test_real_user(user_id: int):
    """Тестирует обогащение реального пользователя из БД."""
    logger.info(f"\n{'='*60}")
    logger.info(f"Testing real user: {user_id}")
    logger.info(f"{'='*60}")
    
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            logger.error(f"User {user_id} not found")
            return
        
        logger.info(f"User: {user.first_name} {user.last_name} (@{user.username})")
        
        if not user.profile:
            logger.warning("User has no profile")
            return
        
        logger.info(f"\nCurrent profile (first 200 chars):")
        logger.info(user.profile[:200] + "...")
        
        # Обогащаем профиль
        result = await test_profile_enrichment("real_user", user.profile)
        
        # Обновляем пользователя
        if result['hero_stage']:
            user.hero_stage = result['hero_stage']
        
        if result['metaphysics']:
            user.metaphysics = result['metaphysics']
        
        if result['streams']:
            user.streams = result['streams']
        
        await session.commit()
        logger.info("\n✅ User updated in database")


async def test_all_profiles():
    """Тестирует все тестовые профили."""
    logger.info("\n" + "="*60)
    logger.info("TESTING ALL PROFILE TYPES")
    logger.info("="*60)
    
    results = {}
    
    for profile_name, profile_text in TEST_PROFILES.items():
        result = await test_profile_enrichment(profile_name, profile_text)
        results[profile_name] = result
        await asyncio.sleep(2)  # Пауза между запросами
    
    # Итоговая таблица
    logger.info("\n" + "="*60)
    logger.info("SUMMARY")
    logger.info("="*60)
    
    for profile_name, result in results.items():
        logger.info(f"\n{profile_name.upper()}:")
        logger.info(f"  Hero Stage: {result['hero_stage'].value if result['hero_stage'] else 'N/A'}")
        logger.info(f"  Planet: {result['metaphysics'].get('planet') if result['metaphysics'] else 'N/A'}")
        logger.info(f"  Balance: {result['metaphysics'].get('light_dark_balance') if result['metaphysics'] else 'N/A'}")
        logger.info(f"  Streams: {', '.join(result['streams']) if result['streams'] else 'N/A'}")


async def main():
    """Главная функция."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test profile enrichment")
    parser.add_argument('--all', action='store_true', help='Test all profile types')
    parser.add_argument('--user', type=int, help='Test specific user by ID')
    parser.add_argument('--profile', choices=list(TEST_PROFILES.keys()), help='Test specific profile type')
    
    args = parser.parse_args()
    
    if args.all:
        await test_all_profiles()
    elif args.user:
        await test_real_user(args.user)
    elif args.profile:
        await test_profile_enrichment(args.profile, TEST_PROFILES[args.profile])
    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())
