"""Enriquece el dataset con datos externos (población, catálogo CIE-10)."""
import logging

import pandas as pd

logger = logging.getLogger(__name__)


def join_poblacion(df: pd.DataFrame, df_poblacion: pd.DataFrame) -> pd.DataFrame:
    """Agrega la población anual y calcula tasa por 100.000 habitantes.

    Args:
        df: Defunciones con columna ``anio`` y ``cantidad``.
        df_poblacion: DataFrame con columnas ``anio`` y ``poblacion``.

    Returns:
        DataFrame con columnas adicionales ``poblacion`` y ``tasa_por_100k``.
    """
    out = df.merge(df_poblacion, on="anio", how="left")
    # Fallback: si el año no está en df_poblacion, usar la mediana de la
    # fuente externa (no del merge — podría tener todos NaN si es 1 sola fila).
    fallback = df_poblacion["poblacion"].median()
    out["poblacion"] = out["poblacion"].fillna(fallback)
    out["tasa_por_100k"] = (out["cantidad"] / out["poblacion"]) * 100_000
    logger.info(
        "Enriquecimiento con población completado",
        extra={"rows": len(out)},
    )
    return out


def join_dim_cie10(df: pd.DataFrame, df_cie10: pd.DataFrame) -> pd.DataFrame:
    """Joinea contra el catálogo CIE-10 leído desde PostgreSQL.

    Si la BD aún no tiene el catálogo (primera corrida), el merge es no-op.
    """
    if df_cie10.empty:
        logger.warning("dim_cie10 vacío — se omite enriquecimiento desde BD")
        return df
    out = df.copy()
    out["_letra"] = out["cie10_causa_id"].str[0]
    out = out.merge(
        df_cie10[["letra", "capitulo"]].rename(columns={"capitulo": "capitulo_bd"}),
        left_on="_letra",
        right_on="letra",
        how="left",
    )
    return out.drop(columns=["_letra", "letra"], errors="ignore")
