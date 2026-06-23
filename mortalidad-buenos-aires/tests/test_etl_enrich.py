"""Tests del enriquecimiento con población y catálogo CIE-10."""
import pandas as pd

from etl.transform.enrich import join_dim_cie10, join_poblacion


def test_join_poblacion_agrega_tasa(raw_df, poblacion_df):
    df = raw_df[["anio", "cantidad"]].copy()
    out = join_poblacion(df, poblacion_df)
    assert "poblacion" in out.columns
    assert "tasa_por_100k" in out.columns
    assert (out["tasa_por_100k"] >= 0).all()


def test_join_poblacion_anios_faltantes_usan_mediana(poblacion_df):
    df = pd.DataFrame({"anio": [2030], "cantidad": [42]})
    out = join_poblacion(df, poblacion_df)
    assert not out["poblacion"].isna().any()


def test_join_dim_cie10_vacio_no_rompe():
    df = pd.DataFrame({"cie10_causa_id": ["I50", "C18"], "x": [1, 2]})
    out = join_dim_cie10(df, pd.DataFrame())
    pd.testing.assert_frame_equal(out, df)


def test_join_dim_cie10_agrega_capitulo():
    df = pd.DataFrame({"cie10_causa_id": ["I50", "C18"], "x": [1, 2]})
    dim = pd.DataFrame({"letra": ["I", "C"], "capitulo": ["Circulatorio", "Neoplasias"]})
    out = join_dim_cie10(df, dim)
    assert "capitulo_bd" in out.columns
    assert set(out["capitulo_bd"]) == {"Circulatorio", "Neoplasias"}
