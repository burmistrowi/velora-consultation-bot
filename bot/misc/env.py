import os
import re

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        extra="ignore",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    BOT_TOKEN: str = ""
    BOT_RUN_MODE: str = "polling"  # polling | webhook
    WEBHOOK_URL: str | None = None  # required for webhook mode

    # Optional: single database URL override (recommended for local dev).
    DATABASE_URL: str | None = "sqlite:///./consultation_bot.sqlite3"

    DB_USER: str = "postgres"
    DB_PASS: str = "postgres"
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "consultation_bot"

    ENABLE_WEB_SERVER: bool = False
    WEB_HOST: str = "0.0.0.0"
    WEB_PORT: int = 8080
    WEB_TIMEOUT: int = 60
    WEB_MAX_CONNECTIONS: int = 100

    WEB_SERVICE_HOST: str = "localhost"
    WEB_SERVICE_PORT: int = 8000

    WEB_WEBHOOK_PATH: str = "/webhook"

    ADMIN_IDS: str = ""

    BOOKING_LIMIT: int = 3

    CURRENCY: str = "RUB"
    CURRENCY_SYMBOL: str = "₽"

    CONSULTATION_PRICE: float = 1500.0

    @model_validator(mode="before")
    @classmethod
    def _normalize_env(cls, data: object) -> object:
        """Поддержка панелей, где токен задан под произвольным именем переменной."""
        merged = dict(data) if isinstance(data, dict) else {}
        if merged.get("BOT_TOKEN"):
            return merged
        token_re = re.compile(r"^\d+:[A-Za-z0-9_-]+$")
        for value in os.environ.values():
            if isinstance(value, str) and token_re.match(value.strip()):
                merged["BOT_TOKEN"] = value.strip()
                break
        return merged

    @model_validator(mode="after")
    def _validate_bot_token(self) -> "Settings":
        if not self.BOT_TOKEN:
            raise ValueError("BOT_TOKEN is required (set BOT_TOKEN in .env or environment)")
        return self

    @property
    def database_url(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return (
            f"postgresql://{self.DB_USER}:{self.DB_PASS}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    @property
    def bot_token(self) -> str:
        return self.BOT_TOKEN

    @property
    def web_config(self) -> dict:
        return {
            "host": self.WEB_HOST,
            "port": self.WEB_PORT,
            "timeout": self.WEB_TIMEOUT,
            "max_connections": self.WEB_MAX_CONNECTIONS,
        }

    @property
    def some_service_url(self) -> str:
        return f"http://{self.WEB_SERVICE_HOST}:{self.WEB_SERVICE_PORT}"

    @property
    def admin_id(self) -> int:
        ids = self.admin_ids
        if not ids:
            raise ValueError("ADMIN_IDS is empty — add at least one Telegram user id")
        return ids[0]

    @property
    def admin_ids(self) -> list[int]:
        if not self.ADMIN_IDS.strip():
            return []
        return [int(admin_id.strip()) for admin_id in self.ADMIN_IDS.split(",") if admin_id.strip()]

    @property
    def currency_info(self) -> dict:
        return {
            "code": self.CURRENCY,
            "symbol": self.CURRENCY_SYMBOL,
        }


settings = Settings()
