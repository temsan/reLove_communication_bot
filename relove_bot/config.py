from typing import Literal, Optional, Set, List
from pydantic import Field, SecretStr, HttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import os

class Settings(BaseSettings):
    # Model configuration
    model_name: str = Field("meta-llama/llama-4-scout:free", env='MODEL_NAME', description="Название модели для OpenRouter")
    """
    Application settings loaded from environment variables.
    """
    # Load settings from .env and ignore extra variables
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore',
        protected_namespaces=('settings_',)
    )

    llm_attempts: int = Field(1, env='LLM_ATTEMPTS', description="Number of attempts to run LLM")

    bot_token: SecretStr = Field(..., env='BOT_TOKEN', description="Telegram Bot Token")
    log_level: Literal['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'] = Field("INFO", env='LOGLEVEL', description="Logging level")

    # Webhook settings
    webhook_host: Optional[HttpUrl] = Field(None, env='WEBHOOK_HOST', description="Webhook host URL (e.g., https://yourdomain.com)")
    webhook_path: str = Field("/webhook", env='WEBHOOK_PATH', description="Webhook path")
    webhook_secret: Optional[SecretStr] = Field(None, env='WEBHOOK_SECRET', description="Webhook secret token")

    # Web server settings
    web_server_host: str = Field("0.0.0.0", env='WEB_SERVER_HOST', description="Host for the web server")
    web_server_port: int = Field(8080, env='WEB_SERVER_PORT', description="Port for the web server")

    # Admin settings
    admin_ids: Set[int] = Field(default_factory=set, env='ADMIN_IDS', description="Set of Telegram User IDs for admins")

    # Database URL for SQLAlchemy
    db_url: str = Field(..., env='DB_URL', description="SQLAlchemy database URL")

    # OpenRouter settings
    openai_api_base: str = Field("https://openrouter.ai/api/v1", env='OPENAI_API_BASE', description="Base URL для OpenRouter API")
    
    # Hugging Face settings
    hugging_face_token: Optional[SecretStr] = Field(None, env='HUGGING_FACE_TOKEN', description="Hugging Face API token")

    # Channel for fill_all_profiles
    our_channel_id: str = Field(..., env='OUR_CHANNEL_ID', description="Telegram channel ID для массового обновления summary")
    discussion_channel_id: str = Field(..., env='DISCUSSION_CHANNEL_ID', description="ID канала для обсуждений/постов пользователей")

    # Telethon (Telegram API) settings
    tg_api_id: int = Field(..., env='TG_API_ID', description="Telegram API ID")
    tg_api_hash: SecretStr = Field(..., env='TG_API_HASH', description="Telegram API hash")
    tg_session: str = Field(..., env='TG_SESSION', description="Telethon session name")

    # Chat export settings
    chat_export_path: str = Field("chat_export.json", env='CHAT_EXPORT_PATH', 
                              description="Путь к файлу с экспортом чата для анализа")

    # Batch processing settings
    USER_PROCESSING_BATCH_SIZE: int = Field(200, env='USER_PROCESSING_BATCH_SIZE', description="Batch size for processing users")
    BATCH_PROCESSING_DELAY_SECONDS: float = Field(.5, env='BATCH_PROCESSING_DELAY_SECONDS', description="Delay in seconds between processing batches")

    # reLove streams configuration
    relove_streams: List[str] = Field(
        default_factory=lambda: ["Мужской", "Женский", "Смешанный", "Путь Героя"],
        description="Список доступных потоков reLove"
    )

    chat_export_path: str = Field('scripts/result.json', env='CHAT_EXPORT_PATH', description='Путь к файлу с экспортом чата (JSON)')

    # New settings from the code block
    USE_REDIS: bool = False
    REDIS_URL: Optional[str] = None

    # Logging settings
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_DIR: str = "logs"
    LOG_FILE: str = "bot.log"

    openrouter_api_key: Optional[SecretStr] = Field(None, env='OPENROUTER_API_KEY', description="OpenRouter API key")
    llm_api_key: SecretStr = Field(..., env='LLM_API_KEY', description="API key для OpenAI/OpenRouter/Groq")
    llm_api_base: str = Field("https://api.openai.com/v1", env='LLM_API_BASE', description="Base URL для OpenAI/OpenRouter/Groq")

    @property
    def log_file_path(self) -> str:
        """Получение пути к файлу лога"""
        return os.path.join(self.LOG_DIR, self.LOG_FILE)

    @field_validator('webhook_host', 'webhook_secret', mode='before')
    @classmethod
    def empty_str_to_none(cls, v):
        if isinstance(v, str) and not v.strip():
            return None
        return v

    @field_validator('admin_ids', mode='before')
    @classmethod
    def parse_admin_ids(cls, v):
        if isinstance(v, (str, int)):
            if isinstance(v, str):
                return {int(x.strip()) for x in v.split(',') if x.strip()}
            return {int(v)}
        return v

    @field_validator('LOG_LEVEL')
    def validate_log_level(cls, v):
        valid_levels = {'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'}
        if v.upper() not in valid_levels:
            raise ValueError(f'LOG_LEVEL must be one of {valid_levels}')
        return v.upper()

# Create a single instance of the settings to be imported elsewhere
settings = Settings()

def reload_settings():
    """Принудительно перечитывает .env и пересоздаёт объект settings."""
    global settings
    settings = Settings()

# Example usage (for testing):
if __name__ == "__main__":
    print("Loaded settings:")
    # Use .get_secret_value() to access the actual string from SecretStr
    print(f"Bot Token: {settings.bot_token.get_secret_value()[:5]}...") # Print only first 5 chars
    print(f"Log Level: {settings.log_level}")
    if settings.webhook_host:
        print(f"Webhook Host: {settings.webhook_host}")
        print(f"Webhook Path: {settings.webhook_path}")
        print(f"Webhook Secret: {settings.webhook_secret.get_secret_value()[:5]}..." if settings.webhook_secret else "Not set")
    print(f"Web Server Host: {settings.web_server_host}")
    print(f"Web Server Port: {settings.web_server_port}")
    print(f"Admin IDs: {settings.admin_ids}")
    print(f"Database URL: {settings.db_url}")
    print(f"OpenAI API Base: {settings.openai_api_base}")
    print(f"Fill Profiles Channel ID: {settings.our_channel_id}")
    print(f"Telegram API ID: {settings.tg_api_id}")
    print(f"Telegram API Hash: {settings.tg_api_hash.get_secret_value()[:5]}...")
    print(f"Telethon Session: {settings.tg_session}")

# Создаем директорию для логов, если она не существует
os.makedirs(settings.LOG_DIR, exist_ok=True)