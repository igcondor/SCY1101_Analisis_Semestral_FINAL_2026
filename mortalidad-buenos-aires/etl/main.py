"""Orquestador del pipeline ETL end-to-end.

Etapas:
    1. **Extract**: lee 3 fuentes — CSV (defunciones), API datos.gob.ar
       (población) y PostgreSQL (catálogo CIE-10).
    2. **Transform**: limpia, normaliza, agrega supracategoría y joina las
       fuentes (cálculo de tasa por 100k habitantes).
    3. **Load**: UPSERT a ``fact_defunciones`` en PostgreSQL.

Uso CLI:
    python -m etl.main

Uso programático:
    >>> from etl.main import run
    >>> df = run()
"""
from __future__ import annotations

import logging
import sys
import time
from dataclasses import dataclass

import pandas as pd

from etl.config import settings
from etl.extract.load_api import load_poblacion
from etl.extract.load_csv import load_defunciones
from etl.extract.load_db import load_dim_cie10
from etl.load.to_postgres import to_fact_defunciones
from etl.logging_config import setup_logging
from etl.schemas import validate_raw, validate_transformed
from etl.transform.cleaning import (
    drop_muerte_materna,
    eliminar_edad_sin_especificar,
    eliminar_jurisdiccion_nula,
    eliminar_sexo_desconocido,
    filtrar_jurisdiccion,
    limpiar_etiqueta_grupo_edad,
    mapear_cie10_faltantes,
    normalizar_cie10_upper,
)
from etl.transform.enrich import join_dim_cie10, join_poblacion
from etl.transform.feature_engineering import agregar_supracategoria

logger = logging.getLogger(__name__)


@dataclass
class ETLMetrics:
    """Métricas observables del pipeline para logging y monitoreo."""

    rows_raw: int = 0
    rows_clean: int = 0
    rows_enriched: int = 0
    rows_loaded: int = 0
    seconds: float = 0.0


def _clean(df: pd.DataFrame, jurisdiccion: str) -> pd.DataFrame:
    """Aplica todas las funciones de cleaning en orden."""
    df = drop_muerte_materna(df)
    df = normalizar_cie10_upper(df)
    df = mapear_cie10_faltantes(df)
    df = eliminar_jurisdiccion_nula(df)
    df = eliminar_sexo_desconocido(df)
    df = eliminar_edad_sin_especificar(df)
    df = limpiar_etiqueta_grupo_edad(df)
    df = filtrar_jurisdiccion(df, jurisdiccion)
    df = agregar_supracategoria(df)
    return df


def run(load_to_db: bool = False) -> pd.DataFrame:
    """Ejecuta el pipeline completo.

    Args:
        load_to_db: Si ``True``, carga el resultado a PostgreSQL.
            Cuando ``False`` solo devuelve el DataFrame (modo notebook/dev).

    Returns:
        DataFrame transformado y enriquecido.

    Raises:
        Exception: Cualquier fallo en una etapa se propaga tras logging.
    """
    setup_logging(level=settings.log_level, fmt=settings.log_format)
    metrics = ETLMetrics()
    t0 = time.perf_counter()

    # --- EXTRACT ---
    try:
        df_raw = load_defunciones(settings.csv_path)
        metrics.rows_raw = len(df_raw)
        validate_raw(df_raw)
    except Exception:
        logger.exception("Etapa EXTRACT (CSV) falló")
        raise

    try:
        df_poblacion = load_poblacion()
    except Exception:
        logger.exception("Etapa EXTRACT (API) falló")
        raise

    try:
        # La lectura del catálogo CIE-10 es independiente de si este run
        # escribe a fact_defunciones (load_to_db controla la escritura, no
        # debería gatear esta lectura). Antes, cualquier llamada con
        # load_to_db=False (como train_models.py/train_supervised_models.py
        # recalculando features) se saltaba dim_cie10 por completo aunque
        # ya tuviera datos en Postgres — el fallback try/except de abajo ya
        # cubre el caso real en que la tabla todavía no existe.
        df_cie10 = load_dim_cie10()
    except RuntimeError as exc:
        logger.warning(
            "No se pudo leer dim_cie10 de Postgres — se continúa sin enriquecer",
            extra={"error": str(exc)},
        )
        df_cie10 = pd.DataFrame()

    # --- TRANSFORM ---
    try:
        df_clean = _clean(df_raw, settings.jurisdiccion_foco)
        metrics.rows_clean = len(df_clean)
        df_enriched = join_poblacion(df_clean, df_poblacion)
        df_enriched = join_dim_cie10(df_enriched, df_cie10)
        metrics.rows_enriched = len(df_enriched)
        validate_transformed(df_enriched)
    except Exception:
        logger.exception("Etapa TRANSFORM falló")
        raise

    # --- LOAD ---
    if load_to_db:
        try:
            metrics.rows_loaded = to_fact_defunciones(df_enriched)
        except Exception:
            logger.exception("Etapa LOAD falló")
            raise

    metrics.seconds = round(time.perf_counter() - t0, 2)
    logger.info("ETL completado", extra=metrics.__dict__)
    return df_enriched


def main() -> int:
    """Punto de entrada CLI."""
    try:
        df = run(load_to_db=True)
        print(f"ETL OK — {len(df)} filas cargadas a fact_defunciones")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"ETL FALLÓ: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
