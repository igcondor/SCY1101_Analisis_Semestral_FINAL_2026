"""Endpoints de listado y filtrado de defunciones."""
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.db import get_db
from api.models import FactDefuncion
from api.schemas import DefuncionesPage, DefuncionOut

router = APIRouter(prefix="/defunciones", tags=["defunciones"])


@router.get("", response_model=DefuncionesPage)
def listar(
    db: Annotated[Session, Depends(get_db)],
    anio: int | None = Query(None, ge=2005, le=2030),
    sexo: str | None = Query(None, pattern="^(varon|mujer)$"),
    grupo_edad: str | None = None,
    supracategoria: str | None = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> DefuncionesPage:
    """Lista defunciones con filtros opcionales y paginación."""
    stmt = select(FactDefuncion)
    conds = []
    if anio is not None:
        conds.append(FactDefuncion.anio == anio)
    if sexo is not None:
        conds.append(FactDefuncion.sexo == sexo)
    if grupo_edad is not None:
        conds.append(FactDefuncion.grupo_edad == grupo_edad)
    if supracategoria is not None:
        conds.append(FactDefuncion.supracategoria == supracategoria)
    if conds:
        stmt = stmt.where(*conds)

    total = db.scalar(
        select(func.count()).select_from(FactDefuncion).where(*conds)
        if conds
        else select(func.count()).select_from(FactDefuncion)
    ) or 0

    rows = db.scalars(stmt.order_by(FactDefuncion.id).limit(limit).offset(offset)).all()
    return DefuncionesPage(
        total=int(total),
        limit=limit,
        offset=offset,
        items=[DefuncionOut.model_validate(r) for r in rows],
    )
