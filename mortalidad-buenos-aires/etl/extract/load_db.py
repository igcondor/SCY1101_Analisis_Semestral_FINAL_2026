"""Fuente #3: PostgreSQL — catálogo CIE-10 (tabla dim_cie10).

La tabla es seedada por ``docker/postgres/init.sql`` al levantar el contenedor.
"""
import logging

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from etl.config import settings

logger = logging.getLogger(__name__)


def load_dim_cie10() -> pd.DataFrame:
    """Lee el catálogo de capítulos CIE-10 desde PostgreSQL.

    Returns:
        DataFrame con columnas ``letra``, ``capitulo``, ``descripcion``.

    Raises:
        RuntimeError: Si la BD no responde o la tabla no existe.
    """
    try:
        engine = create_engine(settings.database_url, future=True)
        with engine.connect() as conn:
            df = pd.read_sql(
                text("SELECT letra, capitulo, descripcion FROM dim_cie10"),
                conn,
            )
        logger.info("Catálogo CIE-10 leído de PostgreSQL", extra={"rows": len(df)})
        return df
    except SQLAlchemyError as exc:
        raise RuntimeError(
            f"No se pudo leer dim_cie10 de PostgreSQL: {exc}"
        ) from exc
