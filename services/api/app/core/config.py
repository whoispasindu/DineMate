from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="DINEMATE_", extra="ignore")

    environment: str = "development"
    database_url: str = "postgresql+psycopg://dinemate:dinemate@localhost:5432/dinemate"
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:5174"]
    simulation_mode: bool = True
    db_connect_timeout_s: int = 3


@lru_cache
def get_settings() -> Settings:
    return Settings()
