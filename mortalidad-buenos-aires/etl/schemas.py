"""Esquemas Pandera para validar DataFrames en cada etapa del ETL.

Detecta tempranamente cambios en la estructura del CSV de origen o errores
de transformación que produzcan tipos o nulos inesperados.
"""
from pandera import Check, Column, DataFrameSchema

# Esquema esperado tras leer el CSV crudo (mínimo viable).
# Solo se validan columnas críticas del análisis para evitar fragilidad.
RAW_SCHEMA = DataFrameSchema(
    columns={
        "anio": Column(int, Check.in_range(2005, 2030), nullable=False),
        "cantidad": Column(int, Check.ge(0), nullable=False),
        "cie10_causa_id": Column(str, nullable=True),
        "cie10_clasificacion": Column(str, nullable=True),
        "jurisdicion_residencia_nombre": Column(str, nullable=True),
        "Sexo": Column(str, nullable=True),
        "grupo_edad": Column(str, nullable=True),
    },
    strict=False,  # Permite columnas adicionales que no usemos
    coerce=True,
)

# Esquema esperado tras todo el pipeline de limpieza/feature-engineering.
TRANSFORMED_SCHEMA = DataFrameSchema(
    columns={
        "anio": Column(int, Check.in_range(2005, 2030), nullable=False),
        "cantidad": Column(int, Check.ge(0), nullable=False),
        "cie10_clasificacion": Column(str, nullable=False),
        "Sexo": Column(str, Check.isin(["varon", "mujer"]), nullable=False),
        "grupo_edad": Column(str, nullable=False),
        "jurisdicion_residencia_nombre": Column(str, nullable=False),
        "supracategoria": Column(str, nullable=False),
    },
    strict=False,
    coerce=True,
)


def validate_raw(df) -> None:
    """Valida el DataFrame crudo recién leído del CSV.

    Raises:
        pandera.errors.SchemaError: Si alguna columna no cumple el contrato.
    """
    RAW_SCHEMA.validate(df, lazy=True)


def validate_transformed(df) -> None:
    """Valida el DataFrame ya transformado, listo para cargar a BD."""
    TRANSFORMED_SCHEMA.validate(df, lazy=True)
