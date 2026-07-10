"""Carga lazy de los modelos joblib + funciones de inferencia.

Estrategia de carga (en orden):
    1. Disco local (``MODEL_DIR``) — rápido, ideal cuando hay volumen.
    2. PostgreSQL (tabla ``ml_artifacts``) — fallback para Fly.io multi-app
       sin volumen compartido.

Si ninguno provee los artefactos se lanza ``ModelsNotAvailable``.
"""
import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any
import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA


from api.config import settings

logger = logging.getLogger(__name__)


class ModelsNotAvailable(RuntimeError):
    """Se lanza cuando faltan artefactos tanto en disco como en BD."""


def _load_from_disk(model_dir: Path) -> tuple[Any, Any, Any, list[str], dict] | None:
    """Intenta cargar desde disco; devuelve None si falta algún archivo."""
    import joblib

    km_path  = model_dir / "kmeans.joblib"
    pca_path = model_dir / "pca.joblib"
    feat_path = model_dir / "features.joblib"
    scaler_path = model_dir / "scaler.joblib"
    meta_path = model_dir / "metadata.json"

    if not all(p.is_file() for p in (km_path, pca_path, feat_path)):
        return None

    kmeans   = joblib.load(km_path)
    pca      = joblib.load(pca_path)
    features = joblib.load(feat_path)
    # El scaler es opcional por compatibilidad con artefactos antiguos
    # entrenados antes de que se persistiera (modelos sin escalar). Si no
    # existe, se sigue funcionando pero sin garantía de consistencia.
    scaler   = joblib.load(scaler_path) if scaler_path.is_file() else None
    metadata = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.is_file() else {}
    logger.info("Modelos ML cargados desde disco", extra={"dir": str(model_dir)})
    return kmeans, pca, scaler, features, metadata


def _load_from_db() -> tuple[Any, Any, Any, list[str], dict] | None:
    """Carga modelos desde la tabla ``ml_artifacts``; None si faltan."""
    try:
        from etl.load.models_to_postgres import load_artifact

        kmeans, _    = load_artifact("kmeans")
        pca, _       = load_artifact("pca")
        features, _  = load_artifact("features")
        try:
            scaler, _ = load_artifact("scaler")
        except KeyError:
            scaler = None
        try:
            metadata, _ = load_artifact("metadata")
        except KeyError:
            metadata = {}
    except KeyError as exc:
        logger.warning("Modelos no encontrados en Postgres", extra={"error": str(exc)})
        return None
    except Exception:  # noqa: BLE001
        logger.exception("Fallo cargando modelos de Postgres")
        return None

    logger.info("Modelos ML cargados desde Postgres (ml_artifacts)")
    return kmeans, pca, scaler, list(features), dict(metadata or {})


@lru_cache(maxsize=1)
def _load_models() -> tuple[KMeans, PCA, Any, list[str], dict]:
    """Carga los modelos una sola vez por proceso (disco → BD)."""
    model_dir: Path = settings.model_dir

    loaded = _load_from_disk(model_dir) or _load_from_db()
    if loaded is None:
        raise ModelsNotAvailable(
            f"No hay modelos en {model_dir} ni en ml_artifacts. "
            f"Ejecuta `python -m etl.train_models`."
        )
    return loaded


def predict_cluster(values: dict) -> tuple[int, float]:
    """Predice cluster y distancia al centroide.

    Aplica el mismo preprocesador (``OneHotEncoder`` + ``StandardScaler``)
    ajustado en entrenamiento antes de llamar a ``kmeans.predict`` — el
    modelo fue entrenado sobre datos transformados, así que un vector crudo
    daría una predicción inconsistente.
    """


    kmeans, _, scaler, _, _ = _load_models()
    X = pd.DataFrame([values])
    if scaler is not None:
        X = scaler.transform(X)
    label = int(kmeans.predict(X)[0])
    centroid = kmeans.cluster_centers_[label]
    dist = float(np.linalg.norm(X[0] - centroid))
    return label, round(dist, 4)


def predict_pca(values: dict) -> tuple[float, float]:
    """Proyecta el vector (ya transformado con el mismo preprocesador de
    entrenamiento) a 2 componentes principales."""
    import pandas as pd

    _, pca, scaler, _, _ = _load_models()
    X = pd.DataFrame([values])
    if scaler is not None:
        X = scaler.transform(X)
    coords = pca.transform(X)[0]
    return float(round(coords[0], 4)), float(round(coords[1], 4))


def get_metadata() -> dict:
    """Devuelve la metadata del último entrenamiento."""
    _, _, _, _, meta = _load_models()
    return meta
def _load_from_disk_supervised(model_dir: Path) -> tuple[Any, Any, dict] | None:
    """Intenta cargar los modelos supervisados desde disco; None si falta algo."""
    import joblib

    clf_path = model_dir / "clasificador_grupo_edad.joblib"
    reg_path = model_dir / "regresor_cantidad.joblib"
    meta_path = model_dir / "metadata_supervisado.json"

    if not all(p.is_file() for p in (clf_path, reg_path)):
        return None

    clasificador = joblib.load(clf_path)
    regresor = joblib.load(reg_path)
    metadata = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.is_file() else {}
    logger.info("Modelos supervisados cargados desde disco", extra={"dir": str(model_dir)})
    return clasificador, regresor, metadata


def _load_from_db_supervised() -> tuple[Any, Any, dict] | None:
    """Carga modelos supervisados desde la tabla ``ml_artifacts``; None si faltan."""
    try:
        from etl.load.models_to_postgres import load_artifact

        clasificador, _ = load_artifact("clasificador_grupo_edad")
        regresor, _ = load_artifact("regresor_cantidad")
        try:
            metadata, _ = load_artifact("metadata_supervisado")
        except KeyError:
            metadata = {}
    except KeyError as exc:
        logger.warning("Modelos supervisados no encontrados en Postgres", extra={"error": str(exc)})
        return None
    except Exception:  # noqa: BLE001
        logger.exception("Fallo cargando modelos supervisados de Postgres")
        return None

    logger.info("Modelos supervisados cargados desde Postgres (ml_artifacts)")
    return clasificador, regresor, dict(metadata or {})


@lru_cache(maxsize=1)
def _load_supervised_models() -> tuple[Any, Any, dict]:
    """Carga los modelos supervisados una sola vez por proceso (disco → BD)."""
    model_dir: Path = settings.model_dir

    loaded = _load_from_disk_supervised(model_dir) or _load_from_db_supervised()
    if loaded is None:
        raise ModelsNotAvailable(
            f"No hay modelos supervisados en {model_dir} ni en ml_artifacts. "
            f"Ejecuta `python -m etl.train_supervised_models`."
        )
    return loaded


def predict_grupo_edad(supracategoria: str, sexo: str, anio: int, cantidad: int) -> tuple[str, dict]:
    """Predice el grupo de edad más probable y la distribución de probabilidad.

    El pipeline persistido incluye su propio preprocesamiento (one-hot +
    escalado), así que recibe las columnas crudas tal como las entrega el ETL.
    """
    import pandas as pd

    clasificador, _, _ = _load_supervised_models()

    entrada = pd.DataFrame([{
        "supracategoria": supracategoria,
        "Sexo": sexo,
        "anio": anio,
        "cantidad": cantidad,
    }])

    pred = clasificador.predict(entrada)[0]
    proba = clasificador.predict_proba(entrada)[0]
    clases = clasificador.classes_
    probabilidades = {str(c): round(float(p), 4) for c, p in zip(clases, proba, strict=True)}

    return str(pred), probabilidades


def predict_cantidad(anio: int, sexo: str, grupo_edad: str, supracategoria: str) -> float:
    """Predice la cantidad de defunciones esperada (ya reconvertida a escala original).

    El regresor persistido fue entrenado sobre ``log1p(cantidad)`` por el
    sesgo extremo del target (ver notebook de entrenamiento supervisado).
    Por eso aquí se aplica ``np.expm1`` antes de devolver el resultado: sin
    este paso, el número devuelto no sería interpretable como "cantidad de
    defunciones".
    """
    import pandas as pd

    _, regresor, _ = _load_supervised_models()

    entrada = pd.DataFrame([{
        "anio": anio,
        "Sexo": sexo,
        "grupo_edad": grupo_edad,
        "supracategoria": supracategoria,
    }])

    pred_log = regresor.predict(entrada)[0]
    return float(round(np.expm1(pred_log), 2))


def get_supervised_metadata() -> dict:
    """Devuelve la metadata del último entrenamiento supervisado."""
    _, _, meta = _load_supervised_models()
    return meta
