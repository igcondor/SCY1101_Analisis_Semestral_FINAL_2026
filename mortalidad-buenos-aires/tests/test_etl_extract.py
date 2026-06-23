"""Tests de extract: CSV missing path + fallback de la API."""
import pandas as pd
import pytest

from etl.extract.load_api import POBLACION_BA_FALLBACK, load_poblacion
from etl.extract.load_csv import load_defunciones


def test_load_csv_raises_when_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_defunciones(tmp_path / "noexiste.csv")


def test_load_poblacion_fallback(monkeypatch):
    """Sin red, debe caer al fallback determinístico."""
    def fake_fetch(_):
        raise ConnectionError("simulado")

    monkeypatch.setattr("etl.extract.load_api._fetch_serie", fake_fetch)
    df = load_poblacion()
    assert isinstance(df, pd.DataFrame)
    assert {"anio", "poblacion"}.issubset(df.columns)
    assert len(df) == len(POBLACION_BA_FALLBACK)
