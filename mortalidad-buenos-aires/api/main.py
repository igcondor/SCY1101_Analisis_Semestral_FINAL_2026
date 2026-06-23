"""FastAPI app — Mortalidad Buenos Aires.

Endpoints en ``/docs`` (Swagger) y ``/redoc``.
"""
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.config import settings
from api.routers import defunciones, estadisticas, health, ml
from etl.logging_config import setup_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa logging al arrancar y limpia al terminar."""
    setup_logging(level=settings.log_level, fmt=settings.log_format)
    logger.info("API arrancando")
    yield
    logger.info("API deteniéndose")


app = FastAPI(
    title="Mortalidad Buenos Aires — API",
    description=(
        "API REST que sirve datos agregados y modelos no supervisados sobre "
        "defunciones registradas en la provincia de Buenos Aires (2005-2022)."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.dashboard_origin] if settings.dashboard_origin != "*" else ["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Loggea cada request con latencia."""
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
    logger.info(
        "request",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "latency_ms": elapsed_ms,
        },
    )
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Excepción no manejada")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error", "error": str(exc)},
    )


app.include_router(health.router)
app.include_router(defunciones.router)
app.include_router(estadisticas.router)
app.include_router(ml.router)


@app.get("/", tags=["root"])
def root() -> dict[str, str]:
    """Hint con links a docs/swagger."""
    return {
        "name": "Mortalidad Buenos Aires API",
        "docs": "/docs",
        "redoc": "/redoc",
        "health": "/health",
    }
