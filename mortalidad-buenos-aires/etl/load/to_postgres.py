"""Carga (UPSERT) del DataFrame transformado en PostgreSQL."""
import logging

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from etl.config import settings

logger = logging.getLogger(__name__)


COLUMNAS_FACT = [
    "anio",
    "sexo",
    "grupo_edad",
    "jurisdiccion",
    "cie10_causa_id",
    "cie10_clasificacion",
    "supracategoria",
    "cantidad",
    "poblacion",
    "tasa_por_100k",
]


def to_fact_defunciones(df: pd.DataFrame, chunksize: int = 5000) -> int:
    """Carga el DataFrame en la tabla ``fact_defunciones``.

    Estrategia: TRUNCATE + INSERT por chunks (más simple y rápido que UPSERT
    para una recarga completa del cubo; el ETL es idempotente).

    Args:
        df: DataFrame con las columnas esperadas (ver ``COLUMNAS_FACT``).
        chunksize: Tamaño de cada batch INSERT.

    Returns:
        Cantidad de filas insertadas.
    """
    df_load = df.rename(
        columns={
            "Sexo": "sexo",
            "jurisdicion_residencia_nombre": "jurisdiccion",
        }
    ).copy()

    faltan = [c for c in COLUMNAS_FACT if c not in df_load.columns]
    if faltan:
        raise ValueError(f"Faltan columnas para cargar fact_defunciones: {faltan}")

    df_load = df_load[COLUMNAS_FACT]

    try:
        engine = create_engine(settings.database_url, future=True)
        with engine.begin() as conn:
            conn.execute(text("TRUNCATE TABLE fact_defunciones"))
            df_load.to_sql(
                "fact_defunciones",
                conn,
                if_exists="append",
                index=False,
                chunksize=chunksize,
                method="multi",
            )
        logger.info(
            "fact_defunciones recargada",
            extra={"rows": len(df_load)},
        )
        return len(df_load)
    except SQLAlchemyError as exc:
        raise RuntimeError(
            f"Fallo cargando fact_defunciones: {exc}"
        ) from exc
