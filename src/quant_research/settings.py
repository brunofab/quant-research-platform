from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    postgres_host: str = "db"
    postgres_port: int = 5432
    postgres_db: str
    postgres_user: str
    postgres_password: str


@lru_cache
def get_settings() -> Settings:
    """Return the application settings loaded from environment variables."""
    return Settings()
