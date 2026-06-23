"""Configuración centralizada del ETL via variables de entorno."""
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


class ETLSettings(BaseSettings):
    """Settings del pipeline ETL leídos desde el entorno (.env)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    database_url: str = Field(
        default="postgresql+psycopg2://mortalidad:mortalidad@localhost:5432/mortalidad",
        description="Cadena de conexión a PostgreSQL en formato SQLAlchemy.",
    )
    csv_path: Path = Field(
        default=Path(
            "data/raw/defunciones-ocurridas-y-registradas-en-la-republica-argentina"
            "-entre-los-anos-2005-2022.csv"
        ),
        description="Ruta local al CSV (fallback si CSV_URL no está seteada).",
    )
    csv_url: str = Field(
        default="",
        description=(
            "URL de origen del CSV. Soporta s3://bucket/key (Tigris/S3/MinIO) "
            "o https://… Tiene prioridad sobre csv_path."
        ),
    )
    jurisdiccion_foco: str = Field(
        default="Buenos Aires",
        description="Jurisdicción objetivo del análisis.",
    )
    indec_api_url: str = Field(
        default="https://apis.datos.gob.ar/series/api/series",
        description="Endpoint base de la API de series de tiempo de datos.gob.ar.",
    )
    model_dir: Path = Field(
        default=Path("data/models"),
        description="Directorio donde se persisten los artefactos joblib.",
    )
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="json", description="'json' o 'plain'")

    @field_validator("database_url", mode="before")
    @classmethod
    def _normalize_db_url(cls, v: str) -> str:
        return normalize_database_url(v) if isinstance(v, str) else v


settings = ETLSettings()
