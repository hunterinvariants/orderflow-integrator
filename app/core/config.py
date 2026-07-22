from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="ORDERFLOW_",
        extra="ignore",
    )

    app_name: str = "OrderFlow Integrator"
    app_version: str = "0.2.0"
    environment: str = "development"
    log_level: str = "INFO"
    default_currency: str = "USD"
    cors_origins: str = "*"
    database_url: str = "sqlite:///./orderflow.db"
    redis_url: str = "redis://localhost:6379/0"
    api_key: str = "demo-orderflow-key"
    celery_eager: bool = False
    max_delivery_attempts: int = 3

    @property
    def parsed_cors_origins(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
