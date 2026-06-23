"""Fuente #1: CSV de defunciones de la República Argentina (2005-2022).

Fuente original: Datos Abiertos del Ministerio de Salud (datos.gob.ar).

Soporta tres orígenes (en orden de prioridad):
    1. ``CSV_URL=s3://bucket/key.csv``    — Tigris/MinIO/S3 (boto3).
    2. ``CSV_URL=https://…/file.csv``     — descarga HTTP (httpx).
    3. ``CSV_PATH=/path/local/file.csv``  — archivo local (dev).

Cache: cuando se descarga remoto, se persiste en ``data/raw/_cache.csv`` para
las siguientes invocaciones del mismo contenedor.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd

logger = logging.getLogger(__name__)

CACHE_PATH = Path("/tmp/mortalidad_csv_cache.csv")


def _download_s3(url: str, dest: Path) -> None:
    """Descarga ``s3://bucket/key`` usando credenciales del entorno."""
    import boto3  # import perezoso para no exigirlo en dev local

    parsed = urlparse(url)
    bucket = parsed.netloc
    key = parsed.path.lstrip("/")

    endpoint = os.getenv("AWS_ENDPOINT_URL_S3") or os.getenv("AWS_ENDPOINT_URL")
    region = os.getenv("AWS_REGION", "auto")

    logger.info(
        "Descargando CSV de object storage",
        extra={"bucket": bucket, "key": key, "endpoint": endpoint},
    )
    s3 = boto3.client("s3", endpoint_url=endpoint, region_name=region)
    dest.parent.mkdir(parents=True, exist_ok=True)
    s3.download_file(bucket, key, str(dest))


def _download_http(url: str, dest: Path) -> None:
    """Descarga via HTTP/HTTPS streaming."""
    import httpx

    logger.info("Descargando CSV via HTTP", extra={"url": url})
    dest.parent.mkdir(parents=True, exist_ok=True)
    with httpx.stream("GET", url, timeout=60.0, follow_redirects=True) as response:
        response.raise_for_status()
        with dest.open("wb") as fp:
            for chunk in response.iter_bytes(chunk_size=1 << 16):
                fp.write(chunk)


def _resolve_csv(local_path: Path | str | None) -> Path:
    """Decide de dónde leer el CSV (URL > local) y devuelve la ruta final."""
    csv_url = os.getenv("CSV_URL", "").strip()

    if csv_url:
        if CACHE_PATH.is_file() and CACHE_PATH.stat().st_size > 0:
            logger.info("Usando CSV cacheado", extra={"path": str(CACHE_PATH)})
            return CACHE_PATH

        scheme = urlparse(csv_url).scheme.lower()
        if scheme == "s3":
            _download_s3(csv_url, CACHE_PATH)
        elif scheme in {"http", "https"}:
            _download_http(csv_url, CACHE_PATH)
        else:
            raise ValueError(f"Esquema no soportado en CSV_URL: {scheme!r}")
        return CACHE_PATH

    if local_path is None:
        raise FileNotFoundError(
            "Ni CSV_URL ni un path local fueron provistos. "
            "Configura CSV_URL (s3:// o https://) o pasa un path al ETL."
        )

    p = Path(local_path)
    if not p.is_file():
        raise FileNotFoundError(
            f"No se encontró el CSV en {p}. "
            f"Setea CSV_URL para descarga remota o deja el archivo en data/raw/."
        )
    return p


def load_defunciones(path: str | Path | None = None) -> pd.DataFrame:
    """Lee el CSV de defunciones forzando tipos seguros en columnas problemáticas.

    Args:
        path: Ruta local de respaldo. Si ``CSV_URL`` está seteada en el entorno,
            se ignora y se descarga el archivo desde allí (con cache).

    Returns:
        DataFrame crudo con todas las columnas del archivo.

    Raises:
        FileNotFoundError: Si no hay CSV ni URL disponibles.
    """
    csv_path = _resolve_csv(path)
    logger.info("Leyendo CSV de defunciones", extra={"path": str(csv_path)})
    df = pd.read_csv(csv_path, dtype={"muerte_materna_id": str})
    logger.info("CSV cargado", extra={"rows": len(df), "cols": len(df.columns)})
    return df


def clear_cache() -> None:
    """Borra el CSV cacheado (útil para forzar re-download)."""
    if CACHE_PATH.is_file():
        CACHE_PATH.unlink()
        logger.info("Cache CSV limpiado", extra={"path": str(CACHE_PATH)})


__all__ = ["load_defunciones", "clear_cache", "CACHE_PATH"]


def _cli() -> None:
    """Sube un CSV local a Tigris (helper de uso ocasional).

    Uso:
        python -m etl.extract.load_csv upload <local.csv> <s3://bucket/key>
    """
    import sys

    if len(sys.argv) >= 4 and sys.argv[1] == "upload":
        import boto3
        local, remote = sys.argv[2], sys.argv[3]
        parsed = urlparse(remote)
        endpoint = os.getenv("AWS_ENDPOINT_URL_S3") or os.getenv("AWS_ENDPOINT_URL")
        s3 = boto3.client("s3", endpoint_url=endpoint, region_name=os.getenv("AWS_REGION", "auto"))
        s3.upload_file(local, parsed.netloc, parsed.path.lstrip("/"))
        print(f"✓ Subido {local} → {remote}")
        return
    print(__doc__ or "")
    print("\nUso: python -m etl.extract.load_csv upload <local.csv> <s3://bucket/key>")


if __name__ == "__main__":
    _cli()
