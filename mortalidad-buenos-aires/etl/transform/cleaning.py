"""Funciones de limpieza del DataFrame de defunciones.

Cada función recibe un DataFrame y devuelve uno nuevo (operaciones inmutables)
para facilitar testing y composición.
"""
import logging

import pandas as pd

logger = logging.getLogger(__name__)


def drop_muerte_materna(df: pd.DataFrame) -> pd.DataFrame:
    """Elimina columnas de muerte materna (casi 100% nulas)."""
    return df.drop(
        columns=["muerte_materna_id", "muerte_materna_clasificacion"],
        errors="ignore",
    ).copy()


def normalizar_cie10_upper(df: pd.DataFrame) -> pd.DataFrame:
    """Convierte el código CIE-10 a mayúsculas para evitar duplicados."""
    out = df.copy()
    out["cie10_causa_id"] = out["cie10_causa_id"].str.upper()
    return out


# Mapeo manual de códigos CIE-10 faltantes en la clasificación oficial.
# Cubre los códigos más frecuentes con clasificación nula en el dataset.
CIE10_FALTANTES: dict[str, str] = {
    "I84": "Hemorroides",
    "R97": "Hallazgos anormales de marcadores tumorales",
    "U07": "COVID-19",
    "U10": "Síndrome inflamatorio multisistémico asociado con COVID-19",
    "U12": "Evento adverso posterior a inmunización contra COVID-19",
    "P28": "Otros problemas respiratorios del recién nacido, originados en el período perinatal",
    "W74": "Ahogamiento y sumersión no especificados",
    "K74": "Fibrosis y cirrosis del hígado",
    "J18": "Neumonía, organismo no especificado",
    "I50": "Insuficiencia cardíaca",
    "K80": "Colelitiasis",
    "B99": "Otras enfermedades infecciosas y las no especificadas",
    "C18": "Tumor maligno del colon",
    "N18": "Enfermedad renal crónica",
    "K83": "Otras enfermedades de las vías biliares",
}


def mapear_cie10_faltantes(df: pd.DataFrame) -> pd.DataFrame:
    """Rellena ``cie10_clasificacion`` con descripciones manuales."""
    out = df.copy()
    out["cie10_clasificacion"] = out["cie10_clasificacion"].fillna(
        out["cie10_causa_id"].map(CIE10_FALTANTES)
    )
    return out


def eliminar_jurisdiccion_nula(df: pd.DataFrame) -> pd.DataFrame:
    """Descarta filas sin jurisdicción de residencia."""
    return df.dropna(subset=["jurisdicion_residencia_nombre"]).copy()


def eliminar_sexo_desconocido(df: pd.DataFrame) -> pd.DataFrame:
    """Descarta registros con sexo desconocido y normaliza valores válidos.

    El dataset puede contener variaciones como ``"Varón"``, ``"Mujer"``,
    espacios extra o capitalización inconsistente. Normaliza a las dos
    categorías canónicas ``varon`` / ``mujer``; cualquier otro valor (NA,
    "sin determinar", etc.) se descarta.
    """
    out = df.copy()
    sex_map = {
        "varon": "varon", "varón": "varon", "v": "varon",
        "masculino": "varon", "m": "varon",
        "mujer": "mujer", "f": "mujer", "femenino": "mujer",
    }
    out["Sexo"] = (
        out["Sexo"].astype(str).str.strip().str.lower().map(sex_map)
    )
    return out[out["Sexo"].isin(["varon", "mujer"])].copy()


def eliminar_edad_sin_especificar(df: pd.DataFrame) -> pd.DataFrame:
    """Descarta registros sin grupo de edad informado."""
    return df[df["grupo_edad"] != "06.Sin especificar"].copy()


def limpiar_etiqueta_grupo_edad(df: pd.DataFrame) -> pd.DataFrame:
    """Quita el prefijo numérico (``"01."``) y dobles espacios de grupo_edad."""
    out = df.copy()
    out["grupo_edad"] = (
        out["grupo_edad"].str.replace("  ", " ", regex=False).str[3:]
    )
    return out


def filtrar_jurisdiccion(
    df: pd.DataFrame, jurisdiccion: str = "Buenos Aires"
) -> pd.DataFrame:
    """Filtra una jurisdicción específica.

    Args:
        df: DataFrame a filtrar.
        jurisdiccion: Nombre exacto de la jurisdicción (case-sensitive).

    Returns:
        Subconjunto restringido a esa jurisdicción.
    """
    return df[df["jurisdicion_residencia_nombre"] == jurisdiccion].copy()


# Alias retrocompatible con notebooks existentes.
filtrar_buenos_aires = filtrar_jurisdiccion
