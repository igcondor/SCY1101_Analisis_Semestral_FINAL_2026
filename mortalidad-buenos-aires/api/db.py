"""Conexión y sesión SQLAlchemy para la API."""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from api.config import settings

engine = create_engine(
    settings.database_url,
    future=True,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator[Session, None, None]:
    """Dependencia FastAPI: provee una sesión por request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
