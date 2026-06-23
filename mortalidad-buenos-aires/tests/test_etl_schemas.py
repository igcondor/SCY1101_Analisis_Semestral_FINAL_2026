"""Tests de validación pandera de los schemas."""
import pandas as pd
import pytest
from pandera.errors import SchemaErrors

from etl.schemas import validate_raw, validate_transformed


def test_raw_schema_ok(raw_df):
    validate_raw(raw_df)


def test_raw_schema_anio_fuera_de_rango():
    bad = pd.DataFrame({
        "anio": [1900],
        "cantidad": [1],
        "cie10_causa_id": ["I50"],
        "cie10_clasificacion": ["x"],
        "jurisdicion_residencia_nombre": ["Buenos Aires"],
        "Sexo": ["varon"],
        "grupo_edad": ["x"],
    })
    with pytest.raises(SchemaErrors):
        validate_raw(bad)


def test_transformed_schema_sexo_invalido():
    bad = pd.DataFrame({
        "anio": [2020],
        "cantidad": [10],
        "cie10_clasificacion": ["x"],
        "Sexo": ["intersex"],
        "grupo_edad": ["x"],
        "jurisdicion_residencia_nombre": ["BA"],
        "supracategoria": ["x"],
    })
    with pytest.raises(SchemaErrors):
        validate_transformed(bad)
