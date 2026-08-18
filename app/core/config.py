"""
Configurações centrais da aplicação.

Carrega variáveis do .env via Pydantic BaseSettings.
"""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Configurações do CodeLab Backend."""

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/codelab",
        alias="DATABASE_URL",
    )

    # Judge0
    judge0_api_url: str = Field(
        default="http://localhost:2358",
        alias="JUDGE0_API_URL",
    )
    judge0_api_key: str = Field(
        default="",
        alias="JUDGE0_API_KEY",
    )
    judge0_api_host: str = Field(
        default="",
        alias="JUDGE0_API_HOST",
    )

    # App
    app_name: str = "CodeLab"
    debug: bool = True

    # Security (JWT)
    secret_key: str = Field(
        default="SUPER_SECRET_KEY_CODELAB_123!@#",
        alias="SECRET_KEY",
    )
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 dias

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
