"""Configurações carregadas de variáveis de ambiente."""

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    supabase_url: str
    supabase_key: SecretStr
    openai_api_key: SecretStr
    meta_verify_token: str
    meta_app_secret: SecretStr
    database_url: str


@lru_cache
def get_settings() -> Settings:
    return Settings()
