"""Fixtures compartidos por los tests."""
from __future__ import annotations

import pandas as pd
import pytest


@pytest.fixture
def raw_df() -> pd.DataFrame:
    """DataFrame mínimo con la estructura del CSV original."""
    return pd.DataFrame(
        {
            "anio": [2018, 2019, 2020, 2021, 2018],
            "cantidad": [10, 25, 100, 50, 5],
            "cie10_causa_id": ["i50", "C18", "U07", "k74", "x99"],
            "cie10_clasificacion": [
                None, "Tumor maligno del colon", None, None, "Otros"
            ],
            "jurisdicion_residencia_nombre": [
                "Buenos Aires", "Buenos Aires", "Buenos Aires",
                "Córdoba", "Buenos Aires",
            ],
            "jurisdiccion_de_residencia_id": [6, 6, 6, 14, 6],
            "Sexo": ["varon", "mujer", "varon", "desconocido", "varon"],
            "sexo_id": [1, 2, 1, 3, 1],
            "grupo_edad": [
                "01.De a 0 a 14 anios",
                "02.De 15 a 34 anios",
                "05.De 75 anios y mas",
                "06.Sin especificar",
                "03.De 35 a 54 anios",
            ],
            "muerte_materna_id": ["X", "X", "X", "X", "X"],
            "muerte_materna_clasificacion": [None] * 5,
        }
    )


@pytest.fixture
def poblacion_df() -> pd.DataFrame:
    """Mock pequeño de población anual."""
    return pd.DataFrame(
        {
            "anio": [2018, 2019, 2020, 2021],
            "poblacion": [16_700_000, 16_850_000, 17_000_000, 17_100_000],
        }
    )
