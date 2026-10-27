from datetime import datetime
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="DINEMATE_", extra="ignore")

    environment: str = "development"
    database_url: str = "postgresql+psycopg://dinemate:dinemate@localhost:5432/dinemate"
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:5174"]
    simulation_mode: bool = True
    db_connect_timeout_s: int = 3
    demo_clock_start: datetime | None = None
    simulator_interval_s: float = 30.0

    @field_validator("demo_clock_start", mode="before")
    @classmethod
    def blank_means_real_time(cls, value: object) -> object:
        return None if value == "" else value


@lru_cache
def get_settings() -> Settings:
    return Settings()
