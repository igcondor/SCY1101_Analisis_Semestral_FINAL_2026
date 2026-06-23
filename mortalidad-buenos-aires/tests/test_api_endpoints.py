"""Tests de endpoints de la API usando TestClient + SQLite en memoria."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api import db as api_db
from api.main import app
from api.models import Base, FactDefuncion


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Reemplaza la sesión DB por SQLite local y siembra datos."""
    engine = create_engine(f"sqlite:///{tmp_path/'test.db'}", future=True)
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    # Seed
    with TestingSession() as s:
        s.add_all([
            FactDefuncion(
                anio=2020, sexo="varon", grupo_edad="De 35 a 54 anios",
                jurisdiccion="Buenos Aires", cie10_causa_id="I50",
                cie10_clasificacion="Insuficiencia cardíaca",
                supracategoria="Aparato circulatorio",
                cantidad=100, poblacion=17_000_000, tasa_por_100k=0.59,
            ),
            FactDefuncion(
                anio=2021, sexo="mujer", grupo_edad="De 75 anios y mas",
                jurisdiccion="Buenos Aires", cie10_causa_id="C18",
                cie10_clasificacion="Tumor maligno del colon",
                supracategoria="Neoplasias",
                cantidad=50, poblacion=17_100_000, tasa_por_100k=0.29,
            ),
        ])
        s.commit()

    def override_get_db():
        s = TestingSession()
        try:
            yield s
        finally:
            s.close()

    monkeypatch.setattr(api_db, "SessionLocal", TestingSession)
    app.dependency_overrides[api_db.get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_root(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "docs" in r.json()


def test_defunciones_listado(client):
    r = client.get("/defunciones")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    assert len(body["items"]) == 2


def test_defunciones_filtro_anio(client):
    r = client.get("/defunciones?anio=2020")
    assert r.status_code == 200
    assert r.json()["total"] == 1


def test_defunciones_filtro_sexo_invalido(client):
    r = client.get("/defunciones?sexo=otro")
    assert r.status_code == 422


def test_estadisticas_serie_temporal(client):
    r = client.get("/estadisticas/serie-temporal")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    assert data[0]["anio"] in (2020, 2021)


def test_estadisticas_top_causas(client):
    r = client.get("/estadisticas/top-causas?n=5")
    assert r.status_code == 200
    data = r.json()
    assert data[0]["supracategoria"] == "Aparato circulatorio"
    assert data[0]["total"] == 100


def test_estadisticas_por_grupo_edad(client):
    r = client.get("/estadisticas/por-grupo-edad")
    assert r.status_code == 200
    assert len(r.json()) == 2
