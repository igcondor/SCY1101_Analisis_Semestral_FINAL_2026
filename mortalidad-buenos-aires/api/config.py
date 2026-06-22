"""Configuración de la API leída desde el entorno."""
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def normalize_database_url(url: str) -> str:
    """Reescribe esquemas legacy al formato que espera SQLAlchemy 2.0.

    ``fly postgres attach`` inyecta ``postgres://…`` (deprecado en SA 2.0).
    Lo convertimos a ``postgresql+psycopg2://…``.
    """
    if url.startswith("postgres://"):
        return "postgresql+psycopg2://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg2://" + url[len("postgresql://"):]
    return url


class APISettings(BaseSettings):
    """Settings de la API FastAPI."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    database_url: str = Field(
        default="postgresql+psycopg2://mortalidad:mortalidad@localhost:5432/mortalidad",
    )
    model_dir: Path = Field(default=Path("data/models"))
    dashboard_origin: str = Field(
        default="*",
        description="Origen permitido por CORS (URL del dashboard).",
    )
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="json")

    @field_validator("database_url", mode="before")
    @classmethod
    def _normalize_db_url(cls, v: str) -> str:
        return normalize_database_url(v) if isinstance(v, str) else v


settings = APISettings()
