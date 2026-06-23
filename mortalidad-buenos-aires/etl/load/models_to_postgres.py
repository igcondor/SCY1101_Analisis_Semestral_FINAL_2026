"""Persistencia de modelos ML (joblib bytes) en PostgreSQL.

Permite que el contenedor ETL entrene/persista modelos y que el contenedor
API los lea sin necesidad de un volumen compartido. Indispensable en Fly.io,
donde los volúmenes son por-máquina y no se comparten entre apps.

Tabla de respaldo: ``ml_artifacts`` (ver ``docker/postgres/init.sql``).
"""
from __future__ import annotations

import io
import json
import logging
from typing import Any

import joblib
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from etl.config import settings

logger = logging.getLogger(__name__)


def _engine():
    """Crea un engine SQLAlchemy contra DATABASE_URL."""
    return create_engine(settings.database_url, future=True)


def save_artifact(name: str, obj: Any, metadata: dict | None = None) -> int:
    """Serializa ``obj`` con joblib y lo guarda como ``ml_artifacts.payload``.

    Args:
        name: Identificador único (p.ej. ``"kmeans"``, ``"pca"``).
        obj: Objeto Python serializable con joblib.
        metadata: Diccionario JSON opcional (métricas, fecha, features, …).

    Returns:
        Tamaño en bytes del payload escrito.

    Raises:
        RuntimeError: Si la BD rechaza la operación.
    """
    buffer = io.BytesIO()
    joblib.dump(obj, buffer, compress=3)
    payload = buffer.getvalue()
    meta_json = json.dumps(metadata or {}, ensure_ascii=False, default=str)

    try:
        with _engine().begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO ml_artifacts (name, payload, metadata, updated_at)
                    VALUES (:name, :payload, CAST(:metadata AS JSONB), NOW())
                    ON CONFLICT (name) DO UPDATE
                       SET payload    = EXCLUDED.payload,
                           metadata   = EXCLUDED.metadata,
                           updated_at = NOW()
                    """
                ),
                {"name": name, "payload": payload, "metadata": meta_json},
            )
    except SQLAlchemyError as exc:
        raise RuntimeError(f"No se pudo persistir artefacto '{name}': {exc}") from exc

    logger.info(
        "Artefacto ML persistido en Postgres",
        extra={"artifact": name, "size_bytes": len(payload)},
    )
    return len(payload)


def load_artifact(name: str) -> tuple[Any, dict]:
    """Lee un artefacto desde PostgreSQL y lo deserializa con joblib.

    Returns:
        Tupla ``(objeto_deserializado, metadata_dict)``.

    Raises:
        KeyError: Si el artefacto no existe en la tabla.
    """
    try:
        with _engine().connect() as conn:
            row = conn.execute(
                text("SELECT payload, metadata FROM ml_artifacts WHERE name = :name"),
                {"name": name},
            ).first()
    except SQLAlchemyError as exc:
        raise RuntimeError(f"No se pudo leer artefacto '{name}': {exc}") from exc

    if row is None:
        raise KeyError(f"Artefacto '{name}' no encontrado en ml_artifacts")

    payload, metadata = row
    obj = joblib.load(io.BytesIO(bytes(payload)))
    if isinstance(metadata, str):
        metadata = json.loads(metadata)
    return obj, dict(metadata or {})


def list_artifacts() -> list[dict]:
    """Lista artefactos disponibles (sin descargar el payload)."""
    try:
        with _engine().connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT name, size_bytes, updated_at, metadata "
                    "FROM ml_artifacts ORDER BY updated_at DESC"
                )
            ).all()
    except SQLAlchemyError as exc:
        raise RuntimeError(f"No se pudo listar artefactos: {exc}") from exc

    return [
        {
            "name": name,
            "size_bytes": int(size),
            "updated_at": ts.isoformat() if ts else None,
            "metadata": meta if isinstance(meta, dict) else json.loads(meta or "{}"),
        }
        for name, size, ts, meta in rows
    ]
