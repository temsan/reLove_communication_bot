"""
Сервис для пакетного заполнения профилей пользователей.
"""
import asyncio
import logging

from relove_bot.config import settings
from relove_bot.utils.fill_profiles import fill_all_profiles
from relove_bot.services.telegram_service import get_client, get_channel_users

logger = logging.getLogger(__name__)

async def process_all_channel_profiles_batch(channel_username: str, batch_size: int = 200):
    """
    Получает пользователей из канала порциями по batch_size и передаёт их на запись в fill_all_profiles.
    
    Args:
        channel_username: Имя или ID канала
        batch_size: Количество пользователей для обработки за один раз (макс. 200)
    """
    client = None
    processed_count = 0
    batch_number = 1
    
    try:
        client = await get_client()
        if not client:
            logger.critical("Не удалось получить Telegram клиента.")
            return
            
        logger.critical(f"Начинаем обработку пользователей канала {channel_username}...")
        
        # Собираем пользователей пачками
        current_batch = []
        
        async for user in get_channel_users(channel_username, batch_size=batch_size):
            current_batch.append(user)
            processed_count += 1
            
            # Когда набрали нужное количество пользователей, обрабатываем пачку
            if len(current_batch) >= batch_size:
                logger.critical(f"Обработка пачки #{batch_number} ({len(current_batch)} пользователей)...")
                try:
                    await fill_all_profiles(users=current_batch, client=client)
                    logger.critical(f"Успешно обработано {len(current_batch)} пользователей. Всего: {processed_count}")
                except Exception as e:
                    logger.critical(f"Ошибка при обработке пачки #{batch_number}: {e}")
                
                # Очищаем текущую пачку и увеличиваем счетчик
                current_batch = []
                batch_number += 1
        
        # Обработка оставшихся пользователей в последней пачке
        if current_batch:
            logger.critical(f"Обработка последней пачки из {len(current_batch)} пользователей...")
            try:
                await fill_all_profiles(users=current_batch, client=client)
                logger.critical(f"Успешно обработано {len(current_batch)} пользователей. Всего: {processed_count}")
            except Exception as e:
                logger.critical(f"Ошибка при обработке последней пачки: {e}")
        
        logger.critical(f"Обработка всех пользователей завершена. Всего обработано: {processed_count}")
        
    except Exception as e:
        logger.critical(f"КРИТИЧЕСКАЯ ОШИБКА: {e}", exc_info=True)
    finally:
        if client and client.is_connected():
            await client.disconnect()