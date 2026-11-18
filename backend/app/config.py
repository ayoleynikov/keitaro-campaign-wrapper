from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
_REPO_ROOT = _BACKEND_ROOT.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(
            str(_BACKEND_ROOT / ".env"),
            str(_REPO_ROOT / ".env"),
        ),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Keitaro Campaign Wrapper"
    database_url: str = "sqlite:///./data/app.db"
    keitaro_mode: str = "mock"  # mock | live
    keitaro_base_url: str = ""
    keitaro_api_key: str = ""
    keitaro_timeout_seconds: float = 30.0
    cors_origins: str = "http://127.0.0.1:43123,http://localhost:43123"
    # Illustrative default only — not a business requirement.
    default_google_redirect: str = "https://www.google.com/"
    default_country_filter_name: str = "country"
    # Live-QA safety (defaults keep mock tests unchanged).
    keitaro_disable_compensation: bool = False
    keitaro_forbid_delete: bool = False
    keitaro_create_campaign_state: str = "active"  # active | disabled
    keitaro_write_allowlist_name: str = ""
    keitaro_allowed_origin: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    from app.db.sqlite_paths import normalize_sqlite_database_url

    settings = Settings()
    object.__setattr__(settings, "database_url", normalize_sqlite_database_url(settings.database_url))
    return settings