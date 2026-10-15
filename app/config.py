from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    bot_token: str = Field(alias="BOT_TOKEN")
    admin_ids_raw: str = Field(default="", alias="ADMIN_IDS")
    support_username: str = Field(default="", alias="SUPPORT_USERNAME")
    referral_reward: int = Field(default=250, ge=1, alias="REFERRAL_REWARD")
    min_withdrawal: int = Field(default=5000, ge=1, alias="MIN_WITHDRAWAL")
    database_url: str = Field(
        default="sqlite+aiosqlite:///data/bot.db", alias="DATABASE_URL"
    )

    @property
    def admin_ids(self) -> list[int]:
        return [
            int(item.strip())
            for item in self.admin_ids_raw.split(",")
            if item.strip()
        ]

    @field_validator("support_username", mode="before")
    @classmethod
    def clean_username(cls, value: object) -> str:
        return str(value or "").strip().lstrip("@")

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: object) -> str:
        url = str(value)
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+asyncpg://", 1)
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]

