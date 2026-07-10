"""Pydantic schemas para request/response de la API."""
from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "1.0.0"


class ReadyResponse(BaseModel):
    status: str
    database: str


class DefuncionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    anio: int
    sexo: str
    grupo_edad: str
    jurisdiccion: str
    cie10_causa_id: str | None = None
    cie10_clasificacion: str
    supracategoria: str
    cantidad: int
    poblacion: int | None = None
    tasa_por_100k: float | None = None


class DefuncionesPage(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[DefuncionOut]


class SerieTemporalPoint(BaseModel):
    anio: int
    total_defunciones: int
    tasa_promedio: float | None = None


class TopCausa(BaseModel):
    supracategoria: str
    total: int


class GrupoEdadStat(BaseModel):
    grupo_edad: str
    sexo: str
    total: int


class TasaMortalidadPoint(BaseModel):
    anio: int
    tasa_por_100k: float


# --- ML ---


class ClusterRequest(BaseModel):
    supracategoria: str = Field(..., description="Capítulo CIE-10 agregado, ej. 'Aparato circulatorio'.")
    sexo: float = Field(..., ge=0, le=1, description="0 = mujer, 1 = varón.")
    grupo_edad: float = Field(..., ge=0, le=4, description="Edad ordinal 0..4.")
    anio: float = Field(..., ge=0, le=1, description="Año escalado a [0, 1].")
    cantidad: float = Field(..., ge=0, le=1, description="Cantidad escalada a [0, 1].")


class ClusterResponse(BaseModel):
    cluster: int
    distance_to_centroid: float


class PCAResponse(BaseModel):
    pc1: float
    pc2: float


class ModelMetadata(BaseModel):
    trained_at: str
    rows_train: int
    features: list[str]
    kmeans: dict
    pca: dict


# --- ML supervisado (clasificación de grupo_edad / regresión de cantidad) ---
#
# A diferencia de ClusterRequest (que espera valores ya escalados a mano por
# quien llama), estos requests reciben las columnas "crudas" tal como las
# entrega el ETL. El pipeline persistido (.joblib) incluye su propio
# ColumnTransformer y hace el one-hot/escalado internamente.


class PredictGrupoEdadRequest(BaseModel):
    supracategoria: str = Field(..., description="Capítulo CIE-10 agregado, ej. 'Aparato circulatorio'.")
    sexo: str = Field(..., description="'varon' o 'mujer'.")
    anio: int = Field(..., ge=2005, le=2030, description="Año de la observación.")
    cantidad: int = Field(..., ge=0, description="Cantidad de defunciones de esa combinación.")


class PredictGrupoEdadResponse(BaseModel):
    grupo_edad_predicho: str
    probabilidades: dict[str, float] = Field(
        ..., description="Probabilidad por clase según el Random Forest."
    )


class PredictCantidadRequest(BaseModel):
    anio: int = Field(..., ge=2005, le=2030)
    sexo: str = Field(..., description="'varon' o 'mujer'.")
    grupo_edad: str = Field(..., description="Una de las 5 categorías de grupo de edad.")
    supracategoria: str = Field(..., description="Capítulo CIE-10 agregado.")


class PredictCantidadResponse(BaseModel):
    cantidad_predicha: float = Field(..., description="Cantidad de defunciones estimada (escala original).")


class SupervisedModelMetadata(BaseModel):
    trained_at: str
    rows_train: int
    clasificador_grupo_edad: dict
    regresor_cantidad: dict
