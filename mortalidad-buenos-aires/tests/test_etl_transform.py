"""Tests unitarios de las funciones de limpieza y feature engineering."""
import pandas as pd

from etl.transform.cleaning import (
    drop_muerte_materna,
    eliminar_edad_sin_especificar,
    eliminar_sexo_desconocido,
    filtrar_jurisdiccion,
    limpiar_etiqueta_grupo_edad,
    mapear_cie10_faltantes,
    normalizar_cie10_upper,
)
from etl.transform.feature_engineering import (
    agregar_supracategoria,
    clasificar_cie10,
)


def test_drop_muerte_materna_quita_columnas(raw_df):
    out = drop_muerte_materna(raw_df)
    assert "muerte_materna_id" not in out.columns
    assert "muerte_materna_clasificacion" not in out.columns


def test_normalizar_cie10_upper(raw_df):
    out = normalizar_cie10_upper(raw_df)
    assert all(v.isupper() for v in out["cie10_causa_id"] if isinstance(v, str))


def test_mapear_cie10_rellena_clasificacion(raw_df):
    df = normalizar_cie10_upper(raw_df)
    out = mapear_cie10_faltantes(df)
    # U07 (COVID-19), K74 (fibrosis) e I50 (insuf cardíaca) deben quedar rellenos
    fila_covid = out[out["cie10_causa_id"] == "U07"].iloc[0]
    assert "COVID" in fila_covid["cie10_clasificacion"]


def test_eliminar_sexo_desconocido(raw_df):
    out = eliminar_sexo_desconocido(raw_df)
    assert "desconocido" not in out["Sexo"].values


def test_eliminar_edad_sin_especificar(raw_df):
    out = eliminar_edad_sin_especificar(raw_df)
    assert "06.Sin especificar" not in out["grupo_edad"].values


def test_limpiar_etiqueta_grupo_edad(raw_df):
    out = limpiar_etiqueta_grupo_edad(raw_df)
    assert all(not v.startswith("01.") for v in out["grupo_edad"])


def test_filtrar_jurisdiccion(raw_df):
    out = filtrar_jurisdiccion(raw_df, "Buenos Aires")
    assert (out["jurisdicion_residencia_nombre"] == "Buenos Aires").all()


def test_clasificar_cie10_capitulo_circulatorio():
    assert clasificar_cie10("I50") == "Aparato circulatorio"


def test_clasificar_cie10_caso_especial_D():
    assert clasificar_cie10("D10") == "Neoplasias"
    assert clasificar_cie10("D60") == "Sangre e inmunidad"


def test_clasificar_cie10_caso_especial_H():
    assert clasificar_cie10("H10") == "Enfermedades del ojo"
    assert clasificar_cie10("H80") == "Enfermedades del oído"


def test_clasificar_cie10_invalido():
    assert clasificar_cie10(None) == "Desconocido"
    assert clasificar_cie10("") == "Desconocido"


def test_agregar_supracategoria_columna(raw_df):
    df = normalizar_cie10_upper(raw_df)
    out = agregar_supracategoria(df)
    assert "supracategoria" in out.columns
    assert (out["supracategoria"].str.len() > 0).all()


def test_pipeline_cleaning_completo(raw_df):
    """Verifica que toda la cadena de cleaning no rompe ni vacía el df."""
    df = drop_muerte_materna(raw_df)
    df = normalizar_cie10_upper(df)
    df = mapear_cie10_faltantes(df)
    df = eliminar_sexo_desconocido(df)
    df = eliminar_edad_sin_especificar(df)
    df = limpiar_etiqueta_grupo_edad(df)
    df = filtrar_jurisdiccion(df, "Buenos Aires")
    assert len(df) >= 1
    assert isinstance(df, pd.DataFrame)
