"""Feature engineering: clasificación CIE-10 y encodings para ML."""
import logging

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import (
    LabelEncoder,
    MinMaxScaler,
    OneHotEncoder,
    OrdinalEncoder,
    StandardScaler,
)

logger = logging.getLogger(__name__)


# Capítulos CIE-10 oficiales agrupados por inicial.
CAPITULOS_CIE10: dict[str, str] = {
    "A": "Infecciosas y parasitarias",
    "B": "Infecciosas y parasitarias",
    "C": "Neoplasias",
    "E": "Endocrinas y metabólicas",
    "F": "Trastornos mentales",
    "G": "Sistema nervioso",
    "I": "Aparato circulatorio",
    "J": "Aparato respiratorio",
    "K": "Aparato digestivo",
    "L": "Piel y tejido subcutáneo",
    "M": "Osteomuscular",
    "N": "Aparato genitourinario",
    "O": "Embarazo y parto",
    "P": "Afecciones perinatales",
    "Q": "Malformaciones congénitas",
    "R": "Síntomas y signos inespecíficos",
    "S": "Traumatismos y envenenamientos",
    "T": "Traumatismos y envenenamientos",
    "V": "Causas externas",
    "W": "Causas externas",
    "X": "Causas externas",
    "Y": "Causas externas",
    "Z": "Factores de salud",
    "U": "Códigos especiales",
}

ORDEN_EDAD: list[str] = [
    "De a 0 a 14 anios",
    "De 15 a 34 anios",
    "De 35 a 54 anios",
    "De 55 a 74 anios",
    "De 75 anios y mas",
]


def clasificar_cie10(codigo: str | None) -> str:
    """Asigna un capítulo CIE-10 al código.

    Casos especiales:
        - ``D00-D48``: Neoplasias; ``D49+``: Sangre e inmunidad.
        - ``H00-H59``: Enfermedades del ojo; ``H60+``: Enfermedades del oído.

    Args:
        codigo: Código CIE-10 (p.ej. ``"I50"``).

    Returns:
        Nombre del capítulo, o ``"Desconocido"`` si no se reconoce.
    """
    if not isinstance(codigo, str) or len(codigo) < 1:
        return "Desconocido"
    letra = codigo[0]
    if letra == "D":
        try:
            num = int(codigo[1:3])
            return "Neoplasias" if num <= 48 else "Sangre e inmunidad"
        except ValueError:
            return "Desconocido"
    if letra == "H":
        try:
            num = int(codigo[1:3])
            return "Enfermedades del ojo" if num <= 59 else "Enfermedades del oído"
        except ValueError:
            return "Desconocido"
    return CAPITULOS_CIE10.get(letra, "Desconocido")


def agregar_supracategoria(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega la columna ``supracategoria`` con el capítulo CIE-10."""
    out = df.copy()
    out["supracategoria"] = out["cie10_causa_id"].apply(clasificar_cie10)
    return out


def transformacion_manual(df: pd.DataFrame) -> pd.DataFrame:
    """Encoding manual + escalado MinMax para clustering / PCA.

    Se usa un ``LabelEncoder`` independiente por columna (bug histórico del
    notebook original reusaba el mismo objeto, sobrescribiendo el fit).
    """
    out = df.copy()

    le_cie = LabelEncoder()
    out["cie10_clasificacion"] = le_cie.fit_transform(out["cie10_clasificacion"])

    le_sexo = LabelEncoder()
    out["Sexo"] = le_sexo.fit_transform(out["Sexo"])

    ord_edad = OrdinalEncoder(categories=[ORDEN_EDAD])
    out["grupo_edad"] = ord_edad.fit_transform(out[["grupo_edad"]])

    mm = MinMaxScaler()
    out["anio"] = mm.fit_transform(out[["anio"]])
    out["cantidad"] = mm.fit_transform(out[["cantidad"]])

    return out.drop(
        columns=[
            "jurisdiccion_de_residencia_id",
            "sexo_id",
            "cie10_causa_id",
            "jurisdicion_residencia_nombre",
        ],
        errors="ignore",
    )


def transformacion_pipeline(df: pd.DataFrame):
    """Pipeline sklearn con OneHot + StandardScaler.

    Returns:
        Tupla ``(matriz_transformada, ColumnTransformer)``.
    """
    pipeline = ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore"),
             ["cie10_clasificacion", "Sexo", "grupo_edad"]),
            ("num", StandardScaler(), ["anio", "cantidad"]),
        ]
    )
    matrix = pipeline.fit_transform(df)
    return matrix, pipeline
