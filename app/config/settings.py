"""Configuração exclusiva do backend novo; importar este módulo não lê o ambiente."""

from pathlib import Path
from urllib.parse import urlsplit
from typing import Literal

from pydantic import AnyHttpUrl, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Valores externos, sem credenciais ou endereço de banco implícitos."""

    model_config = SettingsConfigDict(
        env_prefix="CODELAB_V2_",
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="forbid",
        hide_input_in_errors=True,
    )

    environment: Literal["development", "test", "production"] = "development"
    database_url: SecretStr
    secret_key: SecretStr = Field(min_length=32)
    algorithm: Literal["HS256"] = "HS256"
    access_token_expire_minutes: int = Field(default=60 * 24 * 7, gt=0)

    judge0_api_url: AnyHttpUrl = AnyHttpUrl("http://localhost:2358")
    judge0_api_key: SecretStr = SecretStr("")
    judge0_api_host: str = ""
    judge0_time_limit_seconds: float = Field(default=2.0, gt=0, le=30)
    judge0_memory_limit_kb: int = Field(default=131_072, ge=1_024, le=1_048_576)
    judge0_request_timeout_seconds: float = Field(default=30.0, gt=0, le=120)
    # JSON array in CODELAB_V2_CORS_ORIGINS, e.g. ["http://localhost:5173"].
    cors_origins: list[str] = Field(default_factory=list)

    @field_validator("cors_origins")
    @classmethod
    def validate_cors_origins(cls, origins: list[str]) -> list[str]:
        for origin in origins:
            try:
                parsed = urlsplit(origin)
                # Avaliar .port também rejeita porta malformada ou fora de faixa.
                parsed.port
            except ValueError:
                raise ValueError("Origem CORS inválida.") from None
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username is not None
                or parsed.password is not None
                or parsed.path
                or parsed.query
                or parsed.fragment
                or origin != f"{parsed.scheme}://{parsed.netloc}"
            ):
                raise ValueError("Cada origem CORS deve ser uma origem HTTP(S) exata.")
        if len(origins) != len(set(origins)):
            raise ValueError("Não repita origens CORS.")
        return origins

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: SecretStr) -> SecretStr:
        try:
            url = make_url(value.get_secret_value())
        except (ArgumentError, ValueError):
            raise ValueError("Informe uma URL PostgreSQL/asyncpg válida.") from None

        if url.drivername != "postgresql+asyncpg" or not url.host or not url.username:
            raise ValueError("Use PostgreSQL com asyncpg, host e usuário explícitos.")
        if url.database not in {"codelab_v2", "codelab_v2_test"}:
            raise ValueError("O banco deve ser codelab_v2 ou codelab_v2_test.")
        overrides = {"database", "dbname", "host", "port", "user", "password", "dsn"}
        if overrides.intersection(key.lower() for key in url.query):
            raise ValueError("A query da URL não pode substituir a identidade do banco.")
        return value

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value().strip()) < 32:
            raise ValueError("Defina uma chave externa com pelo menos 32 caracteres.")
        return value

    @field_validator("judge0_api_url")
    @classmethod
    def validate_judge0_url(cls, value: AnyHttpUrl) -> AnyHttpUrl:
        if value.username is not None or value.password is not None or value.query or value.fragment:
            raise ValueError("Configure credenciais do Judge0 fora da URL.")
        return value

    @model_validator(mode="after")
    def validate_database_environment(self) -> "Settings":
        database = make_url(self.database_url.get_secret_value()).database
        expected = "codelab_v2_test" if self.environment == "test" else "codelab_v2"
        if database != expected:
            raise ValueError("O nome do banco não corresponde ao ambiente selecionado.")
        return self


def get_settings() -> Settings:
    """Carrega e valida somente quando solicitado pelo ponto de entrada."""
    return Settings()
