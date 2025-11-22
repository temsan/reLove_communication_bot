#!/usr/bin/env python3
import asyncio
import logging
import sys
from pathlib import Path
from dotenv import load_dotenv

# Добавляем корень проекта в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))

from relove_bot.config import settings
from telethon import TelegramClient

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

async def main():
    client = None
    try:
        # Загружаем настройки из .env
        load_dotenv()
        
        # Создаем клиент
        api_id = settings.tg_api_id
        api_hash = settings.tg_api_hash.get_secret_value()
        session_name = settings.tg_session
        
        logger.info(f"Инициализация клиента с session_name={session_name}")
        client = TelegramClient(session_name, api_id, api_hash)
        
        # Подключаемся
        await client.connect()
        
        # Проверяем авторизацию
        if not await client.is_user_authorized():
            logger.info("Требуется авторизация в Telegram")
            phone = input("Введите номер телефона (с кодом страны, например +7...): ")
            await client.send_code_request(phone)
            code = input("Введите код из Telegram: ")
            await client.sign_in(phone, code)
            logger.info("Авторизация успешно завершена")
        else:
            logger.info("Клиент уже авторизован")
            
        # Проверяем подключение
        me = await client.get_me()
        logger.info(f"Подключено как: {me.first_name} (@{me.username})")
        
    except Exception as e:
        logger.error(f"Ошибка при авторизации: {e}")
    finally:
        if client and client.is_connected():
            await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main()) 