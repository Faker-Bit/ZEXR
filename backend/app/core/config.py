"""Application configuration.

Every value is overridable through environment variables so the same image can
run locally (SQLite / in-process scheduler) and in production (PostgreSQL +
Redis + Celery workers).
"""

from __future__ import annotations

import secrets
from functools import lru_cache
from typing import Literal

from pydantic import Field, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env", "../../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ------------------------------------------------------------------ app
    app_name: str = "ZEXR Deal Hub API"
    app_slug: str = "zexrdealhub"
    app_version: str = "1.0.0"
    environment: Literal["local", "dev", "staging", "production"] = "local"
    debug: bool = True
    api_prefix: str = "/api/v1"
    site_url: str = "http://localhost:3000"
    docs_url: str = "/docs"

    # ------------------------------------------------------------- database
    database_url: str = Field(default="sqlite:///./zexrdealhub.db")
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_echo: bool = False

    # -------------------------------------------------------------- security
    secret_key: str = Field(default_factory=lambda: secrets.token_urlsafe(48))
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 60 * 12
    refresh_token_ttl_days: int = 30
    cookie_name: str = "zexrdealhub_token"
    cookie_secure: bool = False
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # ----------------------------------------------------------------- redis
    redis_url: str = "redis://localhost:6379/0"
    cache_ttl_seconds: int = 120
    cache_enabled: bool = True

    # --------------------------------------------------------------- celery
    celery_broker_url: str = ""
    celery_result_backend: str = ""
    celery_task_always_eager: bool = False

    # ------------------------------------------------------------ discovery
    # Hard switch. When false the discovery worker refuses to fetch anything.
    discovery_enabled: bool = True
    # RFC 7231 product token: no spaces, or servers reject the request outright.
    discovery_user_agent: str = (
        "ZEXRDealHubBot/1.0 (+https://zexrdealhub.com/bot; respects robots.txt)"
    )
    discovery_default_timeout: float = 20.0
    discovery_default_rate_limit_per_hour: int = 30
    discovery_cache_ttl_seconds: int = 900
    discovery_max_retries: int = 3
    # Auto-publish discovered offers. Default OFF: everything lands in review.
    discovery_auto_publish: bool = False
    # Allow fetching pages that are known to sit behind a login wall / paywall.
    discovery_allow_paywalled: bool = False

    # ---------------------------------------------------------- verification
    verify_enabled: bool = True
    verify_interval_hours: int = 12
    verify_broken_link_threshold: int = 3
    scheduler_enabled: bool = True
    scheduler_tick_seconds: int = 60

    # ------------------------------------------------------------ rate limits
    rate_limit_enabled: bool = True
    rate_limit_default: str = "240/minute"
    rate_limit_auth: str = "20/minute"
    rate_limit_search: str = "90/minute"
    rate_limit_write: str = "30/minute"

    # --------------------------------------------------------- email/notify
    email_backend: Literal["console", "smtp", "none"] = "console"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_from: str = "no-reply@zexrdealhub.com"

    # --------------------------------------------------------------- oauth
    oauth_redirect_uri: str = "http://localhost:3000/auth/callback"
    google_client_id: str = ""
    google_client_secret: str = ""
    github_client_id: str = ""
    github_client_secret: str = ""

    # -------------------------------------------------------------- frontend
    # Absolute URL of the API, used by the Next.js server components.
    api_base_url: str = "http://localhost:8000"

    @field_validator("cors_origins", mode="after")
    @classmethod
    def _normalise_origins(cls, value: str) -> str:
        return ",".join(origin.strip() for origin in value.split(",") if origin.strip())

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def effective_broker_url(self) -> str:
        return self.celery_broker_url or self.redis_url

    @property
    def effective_result_backend(self) -> str:
        return self.celery_result_backend or self.redis_url



@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()