"""Wrapper httpx contra la API. Cacheado por Streamlit."""
import os
from typing import Any

import httpx
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")


def _get(path: str, params: dict | None = None) -> Any:
    with httpx.Client(timeout=15.0, base_url=API_URL) as client:
        r = client.get(path, params=params)
        r.raise_for_status()
        return r.json()


def _post(path: str, body: dict) -> Any:
    with httpx.Client(timeout=15.0, base_url=API_URL) as client:
        r = client.post(path, json=body)
        r.raise_for_status()
        return r.json()


@st.cache_data(ttl=600, show_spinner=False)
def serie_temporal() -> list[dict]:
    return _get("/estadisticas/serie-temporal")


@st.cache_data(ttl=600, show_spinner=False)
def top_causas(n: int = 10, anio: int | None = None) -> list[dict]:
    params: dict[str, Any] = {"n": n}
    if anio is not None:
        params["anio"] = anio
    return _get("/estadisticas/top-causas", params)


@st.cache_data(ttl=600, show_spinner=False)
def por_grupo_edad() -> list[dict]:
    return _get("/estadisticas/por-grupo-edad")


@st.cache_data(ttl=600, show_spinner=False)
def tasa_mortalidad() -> list[dict]:
    return _get("/estadisticas/tasa-mortalidad")


@st.cache_data(ttl=300, show_spinner=False)
def defunciones(
    anio: int | None = None,
    sexo: str | None = None,
    grupo_edad: str | None = None,
    supracategoria: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> dict:
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if anio:
        params["anio"] = anio
    if sexo:
        params["sexo"] = sexo
    if grupo_edad:
        params["grupo_edad"] = grupo_edad
    if supracategoria:
        params["supracategoria"] = supracategoria
    return _get("/defunciones", params)


@st.cache_data(ttl=3600, show_spinner=False)
def ml_metadata() -> dict:
    return _get("/ml/metadata")


def ml_cluster(payload: dict) -> dict:
    return _post("/ml/cluster", payload)


def ml_pca(payload: dict) -> dict:
    return _post("/ml/pca", payload)


@st.cache_data(ttl=3600, show_spinner=False)
def ml_metadata_supervisado() -> dict:
    return _get("/ml/metadata-supervisado")


def ml_predict_grupo_edad(payload: dict) -> dict:
    """payload: {supracategoria, sexo, anio, cantidad}."""
    return _post("/ml/predict-grupo-edad", payload)


def ml_predict_cantidad(payload: dict) -> dict:
    """payload: {anio, sexo, grupo_edad, supracategoria}."""
    return _post("/ml/predict-cantidad", payload)


@st.cache_data(ttl=60, show_spinner=False)
def health() -> dict:
    return _get("/ready")
