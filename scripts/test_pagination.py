import asyncio
from relove_bot.services.telegram_service import get_channel_users, get_channel_participants_count
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    channel_id = "@reLoveBot"  # Замените на ваш ID канала
    batch_size = 200
    
    try:
        # Получаем общее количество участников
        total_count = await get_channel_participants_count(channel_id)
        logger.info(f"Всего участников в канале: {total_count}")
        
        # Тестируем пагинацию
        async for user_id in get_channel_users(channel_id, batch_size):
            logger.info(f"Получен пользователь: {user_id}")
            
            # Для тестирования обрабатываем только первые 10 пользователей
            if user_id > 10:
                break
                
    except Exception as e:
        logger.error(f"Ошибка при тестировании пагинации: {e}")

if __name__ == "__main__":
    asyncio.run(main())
