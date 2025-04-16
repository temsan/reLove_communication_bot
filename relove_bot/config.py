from pydantic import SecretStr, Field, HttpUrl, validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal, Optional, List, Set

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    """
    bot_token: SecretStr = Field(..., description="Telegram Bot Token")
    log_level: Literal['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'] = Field("INFO", description="Logging level")

    # Webhook settings (optional, only needed if using webhooks)
    webhook_host: Optional[HttpUrl] = Field(None, description="Webhook host URL (e.g., https://yourdomain.com)")
    webhook_path: str = Field("/webhook", description="Webhook path")
    webhook_secret: Optional[SecretStr] = Field(None, description="Webhook secret token")

    # Web server settings (needed for webhooks and health checks)
    web_server_host: str = Field("0.0.0.0", description="Host for the web server")
    web_server_port: int = Field(8080, description="Port for the web server")

    # Admin settings
    admin_ids: Set[int] = Field(default_factory=set, description="Set of Telegram User IDs for admins")

    # Database settings (add more as needed)
    # db_type: Optional[str] = Field(None, description="Database type (e.g., postgres)")
    # db_host: Optional[str] = Field(None, description="Database host")
    # db_port: Optional[int] = Field(None, description="Database port")
    # db_user: Optional[str] = Field(None, description="Database user")
    # db_password: Optional[SecretStr] = Field(None, description="Database password")
    # db_name: Optional[str] = Field(None, description="Database name")

    # Load settings from .env file if present (useful for local development)
    # In Kubernetes, environment variables are typically injected directly.
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    @validator('admin_ids', pre=True)
    def parse_admin_ids(cls, v):
        if isinstance(v, str):
            if not v: return set()
            try:
                return {int(admin_id.strip()) for admin_id in v.split(',')}
            except ValueError:
                raise ValueError("ADMIN_IDS must be a comma-separated list of integers.")
        return v

# Create a single instance of the settings to be imported elsewhere
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

    # print(f"DB Type: {settings.db_type}")
    # print(f"DB Host: {settings.db_host}") 