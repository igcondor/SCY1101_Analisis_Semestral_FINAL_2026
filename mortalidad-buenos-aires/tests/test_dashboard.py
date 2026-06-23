"""Smoke test del dashboard usando streamlit.testing.v1."""
from streamlit.testing.v1 import AppTest


def test_home_carga(monkeypatch):
    # Evita llamadas reales a la API durante el test
    monkeypatch.setattr(
        "dashboards.api_client.health",
        lambda: {"status": "ok", "database": "up"},
    )
    at = AppTest.from_file("dashboards/app.py", default_timeout=15)
    at.run()
    assert not at.exception
    assert any("Mortalidad" in str(t.value) for t in at.title)
