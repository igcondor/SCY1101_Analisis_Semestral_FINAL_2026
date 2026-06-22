"""Endpoints de inferencia ML: clustering K-Means, proyección PCA y los
modelos supervisados (clasificación de grupo_edad / regresión de cantidad).
"""
from fastapi import APIRouter, HTTPException, status

from api import ml
from api.schemas import (
    ClusterRequest,
    ClusterResponse,
    ModelMetadata,
    PCAResponse,
    PredictCantidadRequest,
    PredictCantidadResponse,
    PredictGrupoEdadRequest,
    PredictGrupoEdadResponse,
    SupervisedModelMetadata,
)

router = APIRouter(prefix="/ml", tags=["ml"])


def _to_vector(req: ClusterRequest) -> list[float]:
    return [req.cie10_clasificacion, req.sexo, req.grupo_edad, req.anio, req.cantidad]


@router.post("/cluster", response_model=ClusterResponse)
def cluster(req: ClusterRequest) -> ClusterResponse:
    """Asigna el vector de features a un cluster del modelo K-Means persistido."""
    try:
        label, dist = ml.predict_cluster(_to_vector(req))
    except ml.ModelsNotAvailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    return ClusterResponse(cluster=label, distance_to_centroid=dist)


@router.post("/pca", response_model=PCAResponse)
def pca(req: ClusterRequest) -> PCAResponse:
    """Proyecta el vector de features a 2 componentes principales."""
    try:
        pc1, pc2 = ml.predict_pca(_to_vector(req))
    except ml.ModelsNotAvailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    return PCAResponse(pc1=pc1, pc2=pc2)


@router.get("/metadata", response_model=ModelMetadata)
def metadata() -> ModelMetadata:
    """Metadata del último entrenamiento (timestamp + métricas)."""
    try:
        return ModelMetadata(**ml.get_metadata())
    except ml.ModelsNotAvailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc


@router.post("/predict-grupo-edad", response_model=PredictGrupoEdadResponse)
def predict_grupo_edad(req: PredictGrupoEdadRequest) -> PredictGrupoEdadResponse:
    """Predice el grupo de edad más probable dado sexo, año, supracategoría y cantidad."""
    try:
        grupo_edad, probabilidades = ml.predict_grupo_edad(
            supracategoria=req.supracategoria,
            sexo=req.sexo,
            anio=req.anio,
            cantidad=req.cantidad,
        )
    except ml.ModelsNotAvailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    return PredictGrupoEdadResponse(grupo_edad_predicho=grupo_edad, probabilidades=probabilidades)


@router.post("/predict-cantidad", response_model=PredictCantidadResponse)
def predict_cantidad(req: PredictCantidadRequest) -> PredictCantidadResponse:
    """Predice la cantidad de defunciones esperada para una combinación dada."""
    try:
        cantidad = ml.predict_cantidad(
            anio=req.anio,
            sexo=req.sexo,
            grupo_edad=req.grupo_edad,
            supracategoria=req.supracategoria,
        )
    except ml.ModelsNotAvailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    return PredictCantidadResponse(cantidad_predicha=cantidad)


@router.get("/metadata-supervisado", response_model=SupervisedModelMetadata)
def metadata_supervisado() -> SupervisedModelMetadata:
    """Metadata del último entrenamiento supervisado (timestamp + métricas)."""
    try:
        return SupervisedModelMetadata(**ml.get_supervised_metadata())
    except ml.ModelsNotAvailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
