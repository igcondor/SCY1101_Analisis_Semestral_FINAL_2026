"""Health & readiness probes (apuntan a Railway healthcheck)."""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from api.db import get_db
from api.schemas import HealthResponse, ReadyResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Liveness probe: no toca dependencias externas."""
    return HealthResponse()


@router.get("/ready", response_model=ReadyResponse)
def ready(db: Session = Depends(get_db)) -> ReadyResponse:
    """Readiness probe: valida conectividad con PostgreSQL."""
    try:
        db.execute(text("SELECT 1"))
        return ReadyResponse(status="ok", database="up")
    except SQLAlchemyError:
        return ReadyResponse(status="degraded", database="down")
