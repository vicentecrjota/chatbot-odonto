"""Configurações carregadas de variáveis de ambiente."""

from functools import lru_cache
from typing import Optional

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    supabase_url: str = Field(validation_alias="SUPABASE_URL")
    supabase_anon_key: SecretStr = Field(validation_alias="SUPABASE_ANON_KEY")
    supabase_service_role_key: SecretStr = Field(validation_alias="SUPABASE_SERVICE_ROLE_KEY")
    openai_api_key: Optional[SecretStr] = None
    meta_verify_token: Optional[str] = None
    meta_app_secret: Optional[SecretStr] = None
    meta_access_token: Optional[SecretStr] = None
    database_url: Optional[str] = None
    environment: str = "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()
