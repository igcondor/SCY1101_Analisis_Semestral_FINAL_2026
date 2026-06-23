"""Entrena y persiste los modelos supervisados (clasificación y regresión).

Refactor del notebook ``notebooks/entrenamiento_supervisado.ipynb`` a un
script reproducible que genera los artefactos consumidos por la API.

Modelos entrenados:
    1. Clasificador de ``grupo_edad`` (Random Forest, tuneado con GridSearchCV)
       a partir de ``supracategoria``, ``Sexo``, ``anio`` y ``cantidad``.
    2. Regresor de ``cantidad`` (Random Forest, tuneado con GridSearchCV)
       sobre ``log1p(cantidad)``, a partir de ``anio``, ``Sexo``,
       ``grupo_edad`` y ``supracategoria``.

A diferencia de los modelos no supervisados (``train_models.py``), aquí cada
``.joblib`` es un ``Pipeline`` completo de Scikit-learn (preprocesamiento +
modelo), no el estimador "pelado". Esto evita que la API tenga que
reimplementar a mano el one-hot/escalado/orden de columnas: simplemente le
pasa un DataFrame con las columnas crudas y el pipeline hace el resto.

Persiste **dos veces**, igual que ``train_models.py``:
    1. En disco local (``data/models/``) para iteración rápida en dev.
    2. En PostgreSQL (tabla ``ml_artifacts``) para que la API los lea sin
       necesidad de volumen compartido (clave en Fly.io multi-app).

Uso:
    python -m etl.train_supervised_models
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import accuracy_score, f1_score, r2_score, mean_absolute_error
from sklearn.model_selection import GridSearchCV, StratifiedKFold, KFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder, StandardScaler

from etl.config import settings
from etl.load.models_to_postgres import save_artifact
from etl.logging_config import setup_logging
from etl.main import run as run_etl

logger = logging.getLogger(__name__)

RANDOM_STATE = 42

ORDEN_EDAD = [
    "De a 0 a 14 anios",
    "De 15 a 34 anios",
    "De 35 a 54 anios",
    "De 55 a 74 anios",
    "De 75 anios y mas",
]

FEATURES_CLF = ["supracategoria", "Sexo", "anio", "cantidad"]
TARGET_CLF = "grupo_edad"

FEATURES_REG = ["anio", "Sexo", "grupo_edad", "supracategoria"]
TARGET_REG = "cantidad"


def _train_classifier(df: pd.DataFrame) -> dict:
    """Entrena el clasificador de grupo_edad con GridSearchCV sobre Random Forest.

    Ver la justificación completa (por qué grupo_edad y no supracategoria
    como target, por qué Random Forest, etc.) en
    ``notebooks/entrenamiento_supervisado.ipynb``.
    """
    X = df[FEATURES_CLF].copy()
    y = df[TARGET_CLF].copy()

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_STATE, stratify=y
    )

    preprocessor = ColumnTransformer(transformers=[
        ("cat", OneHotEncoder(handle_unknown="ignore"), ["supracategoria", "Sexo"]),
        ("num", StandardScaler(), ["anio", "cantidad"]),
    ])

    pipe = Pipeline([
        ("prep", preprocessor),
        ("clf", RandomForestClassifier(random_state=RANDOM_STATE, n_jobs=-1)),
    ])

    param_grid = {
        "clf__n_estimators": [80, 100],
        "clf__max_depth": [10, 20],
    }
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)

    # Baseline: mismo pipeline con los hiperparámetros por defecto de
    # sklearn (n_estimators=100, max_depth=None), SIN GridSearchCV. Se
    # reporta para poder mostrar el impacto real del tuning, no solo el
    # resultado ya optimizado (ver indicador de hiperparámetros en la pauta).
    baseline_scores = cross_val_score(pipe, X_train, y_train, cv=cv, scoring="f1_macro", n_jobs=-1)
    baseline_cv_f1_macro = round(float(baseline_scores.mean()), 4)

    grid = GridSearchCV(pipe, param_grid, cv=cv, scoring="f1_macro", n_jobs=-1)
    grid.fit(X_train, y_train)

    y_pred = grid.best_estimator_.predict(X_test)
    metrics = {
        "best_params": grid.best_params_,
        "baseline_cv_f1_macro": baseline_cv_f1_macro,
        "cv_f1_macro": round(float(grid.best_score_), 4),
        "tuning_delta_f1_macro": round(float(grid.best_score_) - baseline_cv_f1_macro, 4),
        "test_accuracy": round(float(accuracy_score(y_test, y_pred)), 4),
        "test_f1_macro": round(float(f1_score(y_test, y_pred, average="macro")), 4),
    }
    logger.info("Clasificador entrenado", extra=metrics)

    return {
        "model": grid.best_estimator_,
        "features": FEATURES_CLF,
        "target": TARGET_CLF,
        "metrics": metrics,
    }


def _train_regressor(df: pd.DataFrame) -> dict:
    """Entrena el regresor de cantidad con GridSearchCV sobre Random Forest.

    Se entrena sobre ``log1p(cantidad)`` por el sesgo extremo del target
    (ver notebook). El pipeline persistido predice en escala log1p: quien
    consuma el modelo debe aplicar ``np.expm1`` al resultado para obtener
    la cantidad de defunciones en escala real.
    """
    X = df[FEATURES_REG].copy()
    y_log = np.log1p(df[TARGET_REG].copy())

    X_train, X_test, y_train, y_test = train_test_split(
        X, y_log, test_size=0.2, random_state=RANDOM_STATE
    )

    preprocessor = ColumnTransformer(transformers=[
        ("cat_nom", OneHotEncoder(handle_unknown="ignore"), ["Sexo", "supracategoria"]),
        ("cat_ord", OrdinalEncoder(categories=[ORDEN_EDAD]), ["grupo_edad"]),
        ("num", StandardScaler(), ["anio"]),
    ])

    pipe = Pipeline([
        ("prep", preprocessor),
        ("reg", RandomForestRegressor(random_state=RANDOM_STATE, n_jobs=-1)),
    ])

    param_grid = {
        "reg__n_estimators": [80, 100],
        "reg__max_depth": [10, 20],
    }
    cv = KFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)

    # Baseline sin tunear (mismo criterio que en el clasificador).
    baseline_scores = cross_val_score(pipe, X_train, y_train, cv=cv, scoring="r2", n_jobs=-1)
    baseline_cv_r2_log = round(float(baseline_scores.mean()), 4)

    grid = GridSearchCV(pipe, param_grid, cv=cv, scoring="r2", n_jobs=-1)
    grid.fit(X_train, y_train)

    y_pred_log = grid.best_estimator_.predict(X_test)
    y_test_orig = np.expm1(y_test)
    y_pred_orig = np.expm1(y_pred_log)

    metrics = {
        "best_params": grid.best_params_,
        "baseline_cv_r2_log": baseline_cv_r2_log,
        "cv_r2_log": round(float(grid.best_score_), 4),
        "tuning_delta_r2_log": round(float(grid.best_score_) - baseline_cv_r2_log, 4),
        "test_r2_log": round(float(r2_score(y_test, y_pred_log)), 4),
        "test_mae_log": round(float(mean_absolute_error(y_test, y_pred_log)), 4),
        "test_r2_orig": round(float(r2_score(y_test_orig, y_pred_orig)), 4),
        "test_mae_orig": round(float(mean_absolute_error(y_test_orig, y_pred_orig)), 2),
        "target_transform": "log1p",
    }
    logger.info("Regresor entrenado", extra=metrics)

    return {
        "model": grid.best_estimator_,
        "features": FEATURES_REG,
        "target": TARGET_REG,
        "metrics": metrics,
    }


def train_and_persist(model_dir: Path | None = None, push_to_db: bool = True) -> dict:
    """Entrena ambos modelos supervisados, los persiste y devuelve metadata.

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
    logger.info("Dataset listo", extra={"shape": list(df.shape)})

    clf_result = _train_classifier(df)
    reg_result = _train_regressor(df)

    metadata = {
        "trained_at": datetime.now(UTC).isoformat(),
        "rows_train": int(len(df)),
        "clasificador_grupo_edad": {
            "features": clf_result["features"],
            "target": clf_result["target"],
            "metrics": clf_result["metrics"],
        },
        "regresor_cantidad": {
            "features": reg_result["features"],
            "target": reg_result["target"],
            "metrics": reg_result["metrics"],
        },
    }

    # --- 1. Disco local (dev / cache rápida) ---
    joblib.dump(clf_result["model"], model_dir / "clasificador_grupo_edad.joblib")
    joblib.dump(reg_result["model"], model_dir / "regresor_cantidad.joblib")
    (model_dir / "metadata_supervisado.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # --- 2. PostgreSQL (storage compartido entre apps Fly) ---
    if push_to_db:
        try:
            save_artifact(
                "clasificador_grupo_edad", clf_result["model"],
                metadata={"features": clf_result["features"], "metrics": clf_result["metrics"]},
            )
            save_artifact(
                "regresor_cantidad", reg_result["model"],
                metadata={"features": reg_result["features"], "metrics": reg_result["metrics"]},
            )
            save_artifact("metadata_supervisado", metadata, metadata=metadata)
        except Exception:  # noqa: BLE001
            logger.exception("Fallo persistiendo modelos supervisados en Postgres (continuando)")

    logger.info("Modelos supervisados persistidos", extra={"dir": str(model_dir), "db": push_to_db})
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
