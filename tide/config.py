"""Settings, read from environment variables (or a local .env file)."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://tide:tide@localhost:5432/tide"
    catalog_path: Path = Path("catalog.yaml")


settings = Settings()
