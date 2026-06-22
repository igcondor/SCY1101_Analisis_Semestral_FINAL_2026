"""Endpoints de agregaciones para el dashboard."""
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.db import get_db
from api.models import FactDefuncion
from api.schemas import (
    GrupoEdadStat,
    SerieTemporalPoint,
    TasaMortalidadPoint,
    TopCausa,
)

router = APIRouter(prefix="/estadisticas", tags=["estadisticas"])


@router.get("/serie-temporal", response_model=list[SerieTemporalPoint])
def serie_temporal(db: Annotated[Session, Depends(get_db)]) -> list[SerieTemporalPoint]:
    """Defunciones totales y tasa promedio por año."""
    stmt = (
        select(
            FactDefuncion.anio,
            func.sum(FactDefuncion.cantidad).label("total"),
            func.avg(FactDefuncion.tasa_por_100k).label("tasa"),
        )
        .group_by(FactDefuncion.anio)
        .order_by(FactDefuncion.anio)
    )
    return [
        SerieTemporalPoint(
            anio=anio,
            total_defunciones=int(total or 0),
            tasa_promedio=float(tasa) if tasa is not None else None,
        )
        for anio, total, tasa in db.execute(stmt).all()
    ]


@router.get("/top-causas", response_model=list[TopCausa])
def top_causas(
    db: Annotated[Session, Depends(get_db)],
    n: int = Query(10, ge=1, le=50),
    anio: int | None = Query(None, ge=2005, le=2030),
) -> list[TopCausa]:
    """Top-N supracategorías por cantidad de defunciones."""
    stmt = select(
        FactDefuncion.supracategoria,
        func.sum(FactDefuncion.cantidad).label("total"),
    ).group_by(FactDefuncion.supracategoria)
    if anio is not None:
        stmt = stmt.where(FactDefuncion.anio == anio)
    stmt = stmt.order_by(func.sum(FactDefuncion.cantidad).desc()).limit(n)
    return [TopCausa(supracategoria=cat, total=int(total or 0))
            for cat, total in db.execute(stmt).all()]


@router.get("/por-grupo-edad", response_model=list[GrupoEdadStat])
def por_grupo_edad(db: Annotated[Session, Depends(get_db)]) -> list[GrupoEdadStat]:
    """Defunciones por grupo de edad y sexo."""
    stmt = (
        select(
            FactDefuncion.grupo_edad,
            FactDefuncion.sexo,
            func.sum(FactDefuncion.cantidad).label("total"),
        )
        .group_by(FactDefuncion.grupo_edad, FactDefuncion.sexo)
        .order_by(FactDefuncion.grupo_edad, FactDefuncion.sexo)
    )
    return [
        GrupoEdadStat(grupo_edad=ge, sexo=sx, total=int(total or 0))
        for ge, sx, total in db.execute(stmt).all()
    ]


@router.get("/tasa-mortalidad", response_model=list[TasaMortalidadPoint])
def tasa_mortalidad(db: Annotated[Session, Depends(get_db)]) -> list[TasaMortalidadPoint]:
    """Tasa promedio de mortalidad por 100k habitantes por año."""
    stmt = (
        select(FactDefuncion.anio, func.avg(FactDefuncion.tasa_por_100k).label("tasa"))
        .group_by(FactDefuncion.anio)
        .order_by(FactDefuncion.anio)
    )
    return [
        TasaMortalidadPoint(anio=int(anio), tasa_por_100k=float(tasa or 0))
        for anio, tasa in db.execute(stmt).all()
    ]
