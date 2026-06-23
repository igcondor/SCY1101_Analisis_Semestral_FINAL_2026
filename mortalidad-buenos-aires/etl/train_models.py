"""Entrena y persiste los modelos no supervisados (K-Means, PCA).

Refactor de los notebooks ``clustering.ipynb`` y ``pca.ipynb`` a un script
reproducible que genera los artefactos consumidos por la API.

Persiste **dos veces**:
    1. En disco local (``data/models/``) para iteración rápida en dev.
    2. En PostgreSQL (tabla ``ml_artifacts``) para que la API los lea sin
       necesidad de volumen compartido (clave en Fly.io multi-app).

Uso:
    python -m etl.train_models
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

import joblib
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from etl.config import settings
from etl.load.models_to_postgres import save_artifact
from etl.logging_config import setup_logging
from etl.main import run as run_etl
from etl.transform.feature_engineering import transformacion_manual

logger = logging.getLogger(__name__)

FEATURES = ["cie10_clasificacion", "Sexo", "grupo_edad", "anio", "cantidad"]


def _prepare_matrix(df: pd.DataFrame) -> tuple[pd.DataFrame, StandardScaler]:
    """Aplica transformación manual, selecciona las features y las
    estandariza (media 0, varianza 1).

    Sin este paso, ``cie10_clasificacion`` (LabelEncoder, rango ~0-1300)
    domina por completo la distancia euclidiana frente a variables como
    ``Sexo`` o ``grupo_edad`` (rango 0-4) o ``anio``/``cantidad`` (ya en
    [0,1] por MinMaxScaler) — tanto KMeans como PCA quedan sesgados a esa
    única columna. Se usa ``StandardScaler`` sobre las 5 features para que
    todas pesen de forma comparable, igual que en ``notebooks/pca.ipynb``
    y ``notebooks/clustering.ipynb``.

    El ``scaler`` ajustado se devuelve (y se persiste) porque la API debe
    aplicar exactamente la misma transformación a los vectores que llegan
    por ``/ml/cluster`` y ``/ml/pca`` antes de pasarlos a los modelos.
    """
    df_enc = transformacion_manual(df)
    X = df_enc[FEATURES].copy()
    scaler = StandardScaler()
    X_scaled = pd.DataFrame(scaler.fit_transform(X), columns=FEATURES, index=X.index)
    return X_scaled, scaler


def _label_clusters(kmeans: KMeans, features: list[str]) -> dict[str, dict]:
    """Asigna una etiqueta de "clase de riesgo" (lenguaje actuarial) a cada
    cluster, a partir del ranking de su centroide en ``grupo_edad`` (driver
    actuarial primario de mortalidad) y ``cantidad`` (volumen relativo de
    casos).

    El índice que KMeans asigna a cada cluster es arbitrario y puede
    cambiar entre corridas (no hay garantía de que "cluster 0" sea siempre
    el mismo grupo demográfico) — por eso la etiqueta se calcula a partir
    del centroide en vez de hardcodear "cluster 0 = riesgo bajo". El
    ranking es válido aunque los centroides estén en espacio estandarizado:
    ``StandardScaler`` es una transformación monótona por columna, así que
    no altera el orden relativo entre clusters.
    """
    idx_edad = features.index("grupo_edad")
    idx_cantidad = features.index("cantidad")
    centers = kmeans.cluster_centers_
    k = centers.shape[0]

    rank_edad = centers[:, idx_edad].argsort().argsort()       # 0 = menor edad promedio
    rank_cantidad = centers[:, idx_cantidad].argsort().argsort()  # 0 = menor volumen

    tier_names_k4 = [
        "Riesgo bajo — perfil joven",
        "Riesgo moderado-bajo",
        "Riesgo moderado-alto",
        "Riesgo alto — perfil de edad avanzada",
    ]
    tier_names = tier_names_k4 if k == 4 else [f"Riesgo nivel {i + 1}/{k}" for i in range(k)]

    profiles: dict[str, dict] = {}
    for c in range(k):
        base_label = tier_names[int(rank_edad[c])]
        if rank_cantidad[c] == k - 1:
            base_label += " (alta concentración de casos)"
        elif rank_cantidad[c] == 0:
            base_label += " (baja concentración de casos)"
        profiles[str(c)] = {
            "label": base_label,
            "rank_edad": int(rank_edad[c]),
            "rank_cantidad": int(rank_cantidad[c]),
        }
    return profiles


def _train_kmeans(X: pd.DataFrame, k: int = 4, random_state: int = 42) -> dict:
    """Entrena KMeans y reporta silhouette + inercia + perfiles de cluster."""
    kmeans = KMeans(n_clusters=k, n_init=10, random_state=random_state)
    labels = kmeans.fit_predict(X)
    sample_size = min(5000, len(X))
    sil = float(
        silhouette_score(
            X.sample(sample_size, random_state=random_state),
            pd.Series(labels).sample(sample_size, random_state=random_state),
        )
    )
    return {
        "model": kmeans,
        "metrics": {
            "k": k,
            "silhouette_5k": round(sil, 4),
            "inertia": round(float(kmeans.inertia_), 2),
            "cluster_profiles": _label_clusters(kmeans, list(X.columns)),
        },
    }


def _train_pca(X: pd.DataFrame, n_components: int = 2) -> dict:
    """Entrena PCA y devuelve modelo + varianza explicada + loadings.

    ``loadings`` es el peso de cada feature original en cada componente
    (``pca.components_.T``), expuesto como ``{feature: [peso_PC1, peso_PC2]}``
    para que el dashboard pueda mostrar qué variables explican cada eje sin
    tener que recalcular nada.
    """
    pca = PCA(n_components=n_components, random_state=42)
    pca.fit(X)
    loadings = {
        feature: [round(float(v), 4) for v in pca.components_[:, i]]
        for i, feature in enumerate(X.columns)
    }
    return {
        "model": pca,
        "metrics": {
            "n_components": n_components,
            "explained_variance_ratio": [
                round(float(v), 4) for v in pca.explained_variance_ratio_
            ],
            "total_explained": round(float(pca.explained_variance_ratio_.sum()), 4),
            "loadings": loadings,
        },
    }


def train_and_persist(model_dir: Path | None = None, push_to_db: bool = True) -> dict:
    """Entrena KMeans y PCA, los persiste y devuelve metadata.

    Args:
        model_dir: Directorio destino local. Si es ``None`` usa ``settings.model_dir``.
        push_to_db: Si ``True`` también guarda en la tabla ``ml_artifacts``.

    Returns:
        Diccionario con todas las métricas.
    """
    setup_logging(level=settings.log_level, fmt=settings.log_format)
    model_dir = model_dir or settings.model_dir
    model_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Cargando dataset transformado vía ETL")
    df = run_etl(load_to_db=False)
    X, scaler = _prepare_matrix(df)
    logger.info("Matriz de entrenamiento lista", extra={"shape": list(X.shape)})

    km_result = _train_kmeans(X)
    pca_result = _train_pca(X)

    metadata = {
        "trained_at": datetime.now(UTC).isoformat(),
        "rows_train": int(len(X)),
        "features": FEATURES,
        "kmeans": km_result["metrics"],
        "pca": pca_result["metrics"],
    }

    # --- 1. Disco local (dev / cache rápida) ---
    joblib.dump(km_result["model"], model_dir / "kmeans.joblib")
    joblib.dump(pca_result["model"], model_dir / "pca.joblib")
    joblib.dump(FEATURES, model_dir / "features.joblib")
    joblib.dump(scaler, model_dir / "scaler.joblib")
    (model_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # --- 2. PostgreSQL (storage compartido entre apps Fly) ---
    if push_to_db:
        try:
            save_artifact("kmeans",   km_result["model"],  metadata={"kmeans":  metadata["kmeans"]})
            save_artifact("pca",      pca_result["model"], metadata={"pca":     metadata["pca"]})
            save_artifact("features", FEATURES,            metadata={"features": FEATURES})
            save_artifact("scaler",   scaler,               metadata={})
            save_artifact("metadata", metadata,            metadata=metadata)
        except Exception:  # noqa: BLE001
            logger.exception("Fallo persistiendo modelos en Postgres (continuando)")

    logger.info("Modelos persistidos", extra={"dir": str(model_dir), "db": push_to_db})
    return metadata


def main() -> int:
    try:
        meta = train_and_persist()
        print(json.dumps(meta, indent=2, ensure_ascii=False))
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"Entrenamiento FALLÓ: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
