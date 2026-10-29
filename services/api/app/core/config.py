from datetime import datetime
from functools import lru_cache

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_JWT_SECRET = "dev-only-change-me-dinemate-jwt-secret"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="DINEMATE_", extra="ignore")

    environment: str = "development"
    database_url: str = "postgresql+psycopg://dinemate:dinemate@localhost:5432/dinemate"
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:5174"]
    simulation_mode: bool = True
    db_connect_timeout_s: int = 3
    demo_clock_start: datetime | None = None
    simulator_interval_s: float = 30.0
    simulator_api_url: str = "http://localhost:8000/api/v1"
    simulator_token: str = "dev-simulator-token"
    safety_simulator_token: str = "dev-safety-sim-token"
    simulator_devices: list[str] = ["sim-a", "sim-b", "sim-c"]
    rules_interval_s: float = 15.0
    jwt_secret: str = DEV_JWT_SECRET
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    login_attempts_per_minute: int = 5
    demo_password: str | None = None

    @field_validator("demo_clock_start", mode="before")
    @classmethod
    def blank_means_real_time(cls, value: object) -> object:
        return None if value == "" else value

    @model_validator(mode="after")
    def secret_set_outside_development(self) -> "Settings":
        if self.environment != "development" and self.jwt_secret == DEV_JWT_SECRET:
            raise ValueError("Set DINEMATE_JWT_SECRET to a long random value outside development.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
