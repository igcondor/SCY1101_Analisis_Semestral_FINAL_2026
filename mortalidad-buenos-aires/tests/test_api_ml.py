"""Tests de los endpoints ML cuando faltan modelos persistidos."""
from fastapi.testclient import TestClient

from api.main import app


def test_ml_cluster_sin_modelos_devuelve_503(tmp_path, monkeypatch):
    """Sin .joblib en disco, /ml/cluster responde 503."""
    monkeypatch.setattr("api.config.settings.model_dir", tmp_path)
    # Limpia la cache lru
    from api import ml
    ml._load_models.cache_clear()

    client = TestClient(app)
    r = client.post("/ml/cluster", json={
        "supracategoria": "Aparato circulatorio",
        "sexo": 1.0,
        "grupo_edad": 2.0,
        "anio": 0.5,
        "cantidad": 0.1,
    })
    assert r.status_code == 503
    assert "kmeans" in r.json()["detail"].lower() or "model" in r.json()["detail"].lower()


def test_ml_pca_sin_modelos_devuelve_503(tmp_path, monkeypatch):
    monkeypatch.setattr("api.config.settings.model_dir", tmp_path)
    from api import ml
    ml._load_models.cache_clear()

    client = TestClient(app)
    r = client.post("/ml/pca", json={
        "supracategoria": "Aparato circulatorio", "sexo": 0.0, "grupo_edad": 2.0,
        "anio": 0.5, "cantidad": 0.1,
    })
    assert r.status_code == 503
