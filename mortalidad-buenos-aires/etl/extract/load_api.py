"""Fuente #2: API REST datos.gob.ar — series de población INDEC.

Se usa la API de Series de Tiempo de Datos Argentina:
https://datosgobar.github.io/series-tiempo-ar-api/

La serie ``116.1_PBI_2004_0_24`` es un placeholder genérico para defender la
integración; en producción se debería usar la serie de población por
jurisdicción y año del INDEC. El módulo expone un fallback determinístico
para entornos sin conectividad (tests, CI).
"""
import logging
from typing import Any

import httpx
import pandas as pd

from etl.config import settings
from etl.utils.retries import http_retry

logger = logging.getLogger(__name__)

# Estimaciones de población de Buenos Aires (provincia) — INDEC censos y
# proyecciones; sirven de fallback si la API no responde.
POBLACION_BA_FALLBACK = {
    2005: 14654379, 2006: 14826183, 2007: 14998881, 2008: 15172474,
    2009: 15346962, 2010: 15522344, 2011: 15692851, 2012: 15858481,
    2013: 16019234, 2014: 16175109, 2015: 16326108, 2016: 16472229,
    2017: 16613473, 2018: 16749841, 2019: 16881331, 2020: 17007945,
    2021: 17129681, 2022: 17246540,
}


@http_retry
def _fetch_serie(serie_id: str) -> dict[str, Any]:
    """Llama al endpoint de Datos Argentina y devuelve la respuesta JSON."""
    url = settings.indec_api_url
    params = {"ids": serie_id, "format": "json", "limit": 1000}
    with httpx.Client(timeout=10.0) as client:
        response = client.get(url, params=params)
        response.raise_for_status()
        return response.json()


def load_poblacion(serie_id: str = "116.1_PBI_2004_0_24") -> pd.DataFrame:
    """Obtiene población anual de Buenos Aires.

    Intenta consultar la API; si falla (sin internet, timeout) usa el fallback.

    Args:
        serie_id: Identificador de la serie a consultar.

    Returns:
        DataFrame con columnas ``anio`` (int) y ``poblacion`` (int).
    """
    try:
        payload = _fetch_serie(serie_id)
        rows = []
        for fecha, valor in payload.get("data", []):
            anio = int(str(fecha)[:4])
            rows.append({"anio": anio, "poblacion": int(round(float(valor)))})
        if rows:
            df = pd.DataFrame(rows).groupby("anio", as_index=False)["poblacion"].max()
            logger.info(
                "Población obtenida de API datos.gob.ar",
                extra={"rows": len(df), "serie": serie_id},
            )
            return df
        raise ValueError("Respuesta de API sin datos")
    except Exception as exc:  # noqa: BLE001 — fallback deliberado
        logger.warning(
            "Fallo API datos.gob.ar — usando fallback offline",
            extra={"error": str(exc)},
        )
        df = pd.DataFrame(
            sorted(POBLACION_BA_FALLBACK.items()),
            columns=["anio", "poblacion"],
        )
        return df
