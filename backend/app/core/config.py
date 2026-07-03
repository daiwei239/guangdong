from functools import lru_cache
from typing import List

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ImportError:  # pragma: no cover - fallback for older environments
    from pydantic import BaseSettings
    SettingsConfigDict = None

try:
    from pydantic import field_validator
except ImportError:  # pragma: no cover
    field_validator = None


class Settings(BaseSettings):
    if SettingsConfigDict is not None:
        model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    app_name: str = "semi-real-backend"
    app_version: str = "0.1.0"
    debug: bool = True
    database_url: str = "sqlite:///./semi_real_backend.db"
    postgres_url: str = "postgresql+psycopg://guangdong_user:guangdong_pass@localhost:5432/guangdong_resource_mapping"

    neo4j_enabled: bool = False
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "guangdong_pass"

    redis_enabled: bool = False
    redis_url: str = "redis://localhost:6379/0"

    if field_validator is not None:
        @field_validator("debug", mode="before")
        @classmethod
        def parse_debug(cls, value):
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                normalized = value.strip().lower()
                if normalized in {"1", "true", "yes", "on", "debug", "development"}:
                    return True
                if normalized in {"0", "false", "no", "off", "release", "prod", "production"}:
                    return False
            return bool(value)

    if SettingsConfigDict is None:
        class Config:
            env_file = ".env"
            case_sensitive = False
            extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
