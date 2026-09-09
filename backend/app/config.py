"""Runtime settings, all overridable by environment variable."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TANDO_", env_file=".env", extra="ignore")

    app_name: str = "Tom & Ollie API"
    database_url: str = "sqlite:///./tomandollie.db"

    # Admin endpoints are key-protected. There is no default in production:
    # start-up fails rather than shipping a guessable key.
    admin_api_key: str = ""

    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    # Fulfilment rules (PRD §11). Chilled parcels must not sit in transit over
    # a weekend, so dispatch is Mon-Wed only, behind a same-day cut-off.
    dispatch_weekdays: str = "0,1,2"  # Monday=0
    dispatch_cutoff_hour: int = 12
    chilled_transit_days: int = 1
    ambient_transit_days: int = 2
    delivery_window_days: int = 60

    free_delivery_threshold_pence: int = 6000

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def dispatch_weekday_set(self) -> set[int]:
        return {int(day) for day in self.dispatch_weekdays.split(",") if day.strip() != ""}


@lru_cache
def get_settings() -> Settings:
    return Settings()
