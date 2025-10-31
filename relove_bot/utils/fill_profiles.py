import asyncio
import logging
import sys
from typing import Optional, List, Dict, Any
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.functions.channels import GetFullChannelRequest
from relove_bot.db.models import User, GenderEnum
from relove_bot.utils.telegram_client import get_client
from relove_bot.services.telegram_service import get_channel_users
from relove_bot.utils.interests import get_user_streams
from relove_bot.db.database import get_db_session, setup_database, get_engine
from relove_bot.services.profile_service import ProfileService
from relove_bot.db.repository import UserRepository
from tqdm import tqdm
from relove_bot.config import settings
from relove_bot.services.llm_service import llm_service
import traceback

logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('fill_profiles_debug.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

# Очищаем лог-файл после настройки логгера
try:
    with open('fill_profiles_debug.log', 'w', encoding='utf-8') as f:
        f.write('')
    logger.info("Лог-файл очищен")
except Exception as e:
    logger.warning(f"Не удалось очистить лог-файл: {e}")

async def get_user_by_id(session: AsyncSession, user_id: int) -> Optional[User]:
    """Получает пользователя по ID."""
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()

async def fill_user_profile(user_id: int, session: AsyncSession, client) -> None:
    """Заполняет профиль пользователя данными из Telegram."""
    try:
        # Получаем пользователя
        user = await get_user_by_id(session, user_id)
        if not user or not user.username:
            logger.error(f"Пользователь {user_id} не найден или не имеет username")
            return

        # Получаем полную информацию о пользователе
        try:
            full_user = await client(GetFullUserRequest(user.username))
            about = full_user.full_user.about if full_user and full_user.full_user else ""
        except Exception as e:
            logger.error(f"Ошибка при получении информации о пользователе {user.username}: {str(e)}")
            about = ""

        # Получаем потоки пользователя
        streams = await get_user_streams(about)
        
        # Проверяем саммари
        needs_summary = (
            not user.psychological_summary or 
            not user.psychological_summary.startswith("1. ОТРАЖЕНИЕ В ЗЕРКАЛЕ:")
        )
        
        # Обновляем профиль напрямую через User
        stmt = (
            update(User)
            .where(User.id == user_id)
            .values(
                gender=GenderEnum.female,  # по умолчанию female
                streams=streams,  # передаем уже готовый список
                psychological_summary=None if needs_summary else user.psychological_summary  # сбрасываем саммари, если нужно перезаполнить
            )
        )
        await session.execute(stmt)
        await session.commit()
        logger.info(f"Профиль пользователя {user_id} успешно обновлен")

    except Exception as e:
        logger.error(f"Ошибка при обновлении профиля пользователя {user_id}: {str(e)}")
        await session.rollback()

async def fill_all_profiles():
    """
    Заполняет профили всех пользователей из канала.
    """
    client = None
    session = None
    try:
        # Инициализируем клиент Telegram
        client = await get_client()
        if not client.is_connected():
            await client.connect()
            
        if not await client.is_user_authorized():
            logger.error("Клиент не авторизован. Пожалуйста, авторизуйтесь в Telegram.")
            return
            
        # Получаем сессию базы данных
        session = get_db_session()
        repo = UserRepository(session)
        
        # Получаем пользователей из канала
        channel_id = settings.our_channel_id
        logger.info(f"Получаем пользователей из канала {channel_id}")
        
        # Создаем экземпляр ProfileService (принимает session, а не репозиторий)
        profile_service = ProfileService(session)
        
        # Получаем общее количество пользователей для прогресс-бара
        total_users = 0
        try:
            channel_entity = await client.get_entity(channel_id)
            full_chat = await client(GetFullChannelRequest(channel_entity))
            total_users = getattr(full_chat.full_chat, 'participants_count', 0)
            logger.info(f"Всего участников в канале: {total_users}")
        except Exception as e:
            logger.warning(f"Не удалось получить количество участников: {e}")
        
        # Яркий прогрессбар
        with tqdm(
            total=total_users if total_users > 0 else None,
            desc="\033[1;32mОбработка пользователей\033[0m",
            bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}, {percentage:3.0f}%]",
            ncols=100,
            file=sys.stdout,
            colour='green',
        ) as pbar:
            # Получаем пользователей пачками
            async for user in get_channel_users(channel_id, batch_size=200):
                try:
                    # Проверяем тип user
                    if isinstance(user, int):
                        user_id = user
                        tg_user = None
                    else:
                        tg_user = user
                        user_id = user.id

                    # Проверяем существование пользователя в БД
                    db_user = await repo.get_by_id(user_id)
                    if not db_user:
                        logger.warning(f"Пользователь {user_id} не найден в базе данных")
                        continue

                    # Анализируем профиль с повторными попытками и обработкой ошибок
                    max_retries = 3
                    success = False
                    
                    for attempt in range(max_retries):
                        try:
                            result = await profile_service.analyze_profile(
                                user_id=user_id,
                                main_channel_id=channel_id,
                                tg_user=tg_user
                            )
                            if result:
                                logger.info(f"✅ Успешно обновлен профиль пользователя {user_id}")
                                success = True
                                break
                            else:
                                if attempt < max_retries - 1:
                                    logger.warning(f"⚠️ Попытка {attempt + 1}/{max_retries} для пользователя {user_id} не удалась, повторяем...")
                                    await asyncio.sleep(2)  # Пауза перед повторной попыткой
                                
                        except Exception as e:
                            error_msg = str(e)
                            # Если это временная ошибка (rate limit, сеть), повторяем
                            if "rate limit" in error_msg.lower() or "timeout" in error_msg.lower():
                                if attempt < max_retries - 1:
                                    wait_time = (attempt + 1) * 5  # Экспоненциальная задержка
                                    logger.warning(f"⏳ Временная ошибка для {user_id}, ждём {wait_time}с перед повтором...")
                                    await asyncio.sleep(wait_time)
                                    continue
                            
                            if attempt < max_retries - 1:
                                logger.warning(f"⚠️ Ошибка при попытке {attempt + 1}/{max_retries} для {user_id}: {error_msg[:100]}")
                                await asyncio.sleep(2)
                            else:
                                logger.error(f"❌ Критическая ошибка для пользователя {user_id}: {error_msg}")
                    
                    if not success:
                        logger.warning(f"⚠️ Не удалось обновить профиль пользователя {user_id} после {max_retries} попыток")
                    
                    pbar.update(1)
                    
                    # Небольшая пауза между пользователями для избежания rate limit
                    await asyncio.sleep(0.5)
                except Exception as e:
                    logger.error(f"Ошибка при обработке пользователя {user_id if isinstance(user, int) else getattr(user, 'id', 'N/A')}: {e}")
                    continue
                    
        logger.info("Скрипт заполнения профилей успешно завершил работу.")
    except Exception as e:
        logger.error(f"Ошибка при заполнении профилей: {e}")
        logger.error(traceback.format_exc())
    finally:
        if session is not None:
            await session.close()
        if client is not None and client.is_connected():
            await client.disconnect()

async def main():
    """Основная функция для заполнения профилей."""
    await fill_all_profiles()

if __name__ == "__main__":
    asyncio.run(main())


