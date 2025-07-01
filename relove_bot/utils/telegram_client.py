import logging
from telethon import TelegramClient
from relove_bot.config import settings

logger = logging.getLogger(__name__)

_client = None

async def get_client():
    """
    Returns a Telegram client in user mode.
    Uses the session specified in settings.
    """
    global _client
    if _client is None:
        # Получаем значения из настроек с правильной обработкой SecretStr
        api_id = int(settings.tg_api_id)
        api_hash = settings.tg_api_hash.get_secret_value() if hasattr(settings.tg_api_hash, 'get_secret_value') else str(settings.tg_api_hash)
        session_name = settings.tg_session if hasattr(settings, 'tg_session') else 'relove_bot'
        
        _client = TelegramClient(
            session=session_name,
            api_id=api_id,
            api_hash=api_hash,
            device_model='reLove Bot',
            system_version='1.0',
            app_version='1.0',
            lang_code='en',
            system_lang_code='en',
        )
    return _client 