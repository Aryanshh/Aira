from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_ENV: str = "development"

    # Database (defaults to local SQLite; override with DATABASE_URL for Postgres)
    DATABASE_URL: str = "sqlite+aiosqlite:///./aira.db"

    # Security
    JWT_SECRET: str = "aira_development_jwt_secret_key_minimum_32_chars_long_1234567890"
    APP_ENCRYPTION_KEY: str = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    COOKIE_DOMAIN: Optional[str] = None
    COOKIE_SECURE: bool = False
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    RESET_TOKEN_EXPIRE_MINUTES: int = 60
    VERIFY_TOKEN_EXPIRE_HOURS: int = 24

    # Origins
    WEB_ORIGIN: str = "http://localhost:3000"
    API_BASE_URL: str = "http://localhost:8000"

    # Providers
    EMAIL_PROVIDER: str = "resend"
    EMAIL_API_KEY: str = ""
    EMAIL_FROM: str = "AIRA Care <care@aira.example.com>"

    SMS_PROVIDER: str = "twilio"
    SMS_ACCOUNT_SID: str = ""
    SMS_AUTH_TOKEN: str = ""
    SMS_FROM: str = ""

    WHATSAPP_PROVIDER: str = "twilio"
    WHATSAPP_FROM: str = ""

    # Web Push
    VAPID_PUBLIC_KEY: str = ""
    VAPID_PRIVATE_KEY: str = ""
    VAPID_SUBJECT: str = "mailto:care@aira.example.com"

    # SOS & Escalation
    SOS_ACK_WINDOW_SECONDS: int = 15
    SOS_MAX_ROUNDS: int = 3
    SOS_DEDUPE_WINDOW_SECONDS: int = 60

    # Seeding
    AUTO_SEED_ON_STARTUP: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
