"""Application settings, read from environment variables (and the repo-root `.env`, if present)."""

from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.pay import PayRules

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Every variable is documented in `.env.example` at the repository root."""

    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    database_url: str = "postgresql+psycopg://shibutzim:shibutzim@localhost:5433/shibutzim"
    test_database_url: str = (
        "postgresql+psycopg://shibutzim:shibutzim@localhost:5433/shibutzim_test"
    )
    jwt_secret: str = "change-me-to-a-long-random-string"
    jwt_expires_hours: int = Field(default=8, gt=0)
    cors_origins: list[str] = ["http://localhost:5173"]
    timezone: str = "Asia/Jerusalem"
    seed_password: str = "shibutzim-demo"  # shared by every seeded demo user (scripts/seed.py)

    @property
    def pay_rules(self) -> PayRules:
        """The pay rules in force (architecture §5). v1 uses the product defaults."""
        return PayRules.default()

    @property
    def tz(self) -> ZoneInfo:
        """The zone for work-day and week boundaries; storage is always UTC."""
        return ZoneInfo(self.timezone)


@lru_cache
def get_settings() -> Settings:
    return Settings()
