import secrets
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class Settings(BaseSettings):
    # API Settings
    API_TITLE: str = "store_forge"
    API_DESCRIPTION: str = ""
    ENVIRONMENT: str = "development"
    SECRET_KEY: str = secrets.token_urlsafe(32)

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8

    # Database Settings
    DATABASE_URL: str

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="allow"
    )


    # Env settings for logging customization
    ENV_MODE: str = "LOCAL"
    LOG_LEVEL: str = "INFO"



settings = Settings()
