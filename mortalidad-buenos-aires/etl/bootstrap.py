"""Auto-seed idempotente del stack — corre como CMD del contenedor ETL.

Pasos:
    1. Aplica ``docker/postgres/init.sql`` si las tablas no existen.
    2. Si ``fact_defunciones`` está vacía → corre el ETL (carga datos).
    3. Si los modelos no supervisados (K-Means/PCA) no están en
       ``ml_artifacts`` → entrena y persiste.
    4. Si los modelos supervisados (clasificador/regresor) no están en
       ``ml_artifacts`` → entrena y persiste.
    5. Si todo ya existe → exit 0 inmediato (idempotente).

Diseñado para correr múltiples veces sin efectos colaterales: cada deploy a
Fly arranca una máquina ETL nueva que ejecuta esto y se apaga.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from etl.config import settings
from etl.logging_config import setup_logging

logger = logging.getLogger(__name__)

# Cuando el contenedor se construye, init.sql se copia a /app/init.sql.
# Localmente queda en docker/postgres/init.sql.
INIT_SQL_PATHS = [
    Path("/app/init.sql"),
    Path(__file__).parent.parent / "docker" / "postgres" / "init.sql",
]


def _find_init_sql() -> Path:
    for path in INIT_SQL_PATHS:
        if path.is_file():
            return path
    raise FileNotFoundError(f"No se encontró init.sql en ninguna de: {INIT_SQL_PATHS}")


def _engine():
    return create_engine(settings.database_url, future=True)


def schema_exists() -> bool:
    """¿Existe la tabla principal ``fact_defunciones``?"""
    try:
        with _engine().connect() as conn:
            row = conn.execute(
                text(
                    "SELECT 1 FROM information_schema.tables "
                    "WHERE table_name = 'fact_defunciones'"
                )
            ).first()
            return row is not None
    except SQLAlchemyError as exc:
        logger.exception("No se pudo verificar el schema", extra={"error": str(exc)})
        return False


def fact_row_count() -> int:
    try:
        with _engine().connect() as conn:
            row = conn.execute(text("SELECT COUNT(*) FROM fact_defunciones")).first()
            return int(row[0]) if row else 0
    except SQLAlchemyError:
        return 0


def unsupervised_models_exist() -> bool:
    """¿Están K-Means/PCA/features ya persistidos en ``ml_artifacts``?"""
    try:
        with _engine().connect() as conn:
            row = conn.execute(
                text(
                    "SELECT COUNT(*) FROM ml_artifacts "
                    "WHERE name IN ('kmeans', 'pca', 'features')"
                )
            ).first()
            return bool(row and int(row[0]) >= 3)
    except SQLAlchemyError:
        return False


def supervised_models_exist() -> bool:
    """¿Están el clasificador y el regresor ya persistidos en ``ml_artifacts``?

    Antes el bootstrap solo chequeaba los artefactos no supervisados
    (kmeans/pca/features), así que si esos tres ya existían se saltaba
    *todo* el entrenamiento — incluido el de los modelos supervisados, que
    nunca llegaban a generarse en un deploy nuevo. Esta verificación es
    independiente para que el paso 4 se ejecute aunque el paso 3 ya esté
    completo.
    """
    try:
        with _engine().connect() as conn:
            row = conn.execute(
                text(
                    "SELECT COUNT(*) FROM ml_artifacts "
                    "WHERE name IN ('clasificador_grupo_edad', 'regresor_cantidad', "
                    "'metadata_supervisado')"
                )
            ).first()
            return bool(row and int(row[0]) >= 3)
    except SQLAlchemyError:
        return False


def apply_init_sql() -> None:
    """Ejecuta el contenido de ``init.sql`` contra la BD configurada."""
    sql_path = _find_init_sql()
    logger.info("Aplicando init.sql", extra={"path": str(sql_path)})
    sql = sql_path.read_text(encoding="utf-8")
    with _engine().begin() as conn:
        conn.exec_driver_sql(sql)
    logger.info("Schema aplicado")


def apply_grants() -> None:
    """Otorga permisos a usuarios listados en ``GRANT_USERS`` (CSV).

    Idempotente: se ejecuta en cada bootstrap independientemente de si el
    schema ya existía o se acaba de crear. Necesario en Fly donde la API
    se conecta con un user distinto al que crea las tablas.
    """
    grant_users = [u.strip() for u in os.getenv("GRANT_USERS", "").split(",") if u.strip()]
    if not grant_users:
        return
    grant_sql = ""
    for user in grant_users:
        grant_sql += f"""
        GRANT USAGE ON SCHEMA public TO {user};
        GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {user};
        GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {user};
        ALTER DEFAULT PRIVILEGES IN SCHEMA public
            GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {user};
        ALTER DEFAULT PRIVILEGES IN SCHEMA public
            GRANT USAGE, SELECT ON SEQUENCES TO {user};
        """
    try:
        with _engine().begin() as conn:
            conn.exec_driver_sql(grant_sql)
        logger.info("Permisos otorgados", extra={"users": grant_users})
    except Exception:  # noqa: BLE001
        logger.exception("Fallo otorgando permisos (continuando)")


def run_etl() -> int:
    """Importa y ejecuta el pipeline ETL principal."""
    from etl.main import run as run_etl_pipeline

    df = run_etl_pipeline(load_to_db=True)
    logger.info("ETL completado", extra={"rows": len(df)})
    return len(df)


def train_models() -> None:
    """Importa y ejecuta el entrenamiento no supervisado (K-Means/PCA)."""
    from etl.train_models import train_and_persist

    meta = train_and_persist(push_to_db=True)
    logger.info("Modelos no supervisados entrenados", extra={"rows_train": meta["rows_train"]})


def train_supervised_models() -> None:
    """Importa y ejecuta el entrenamiento supervisado (clasificador + regresor)."""
    from etl.train_supervised_models import train_and_persist as train_and_persist_supervised

    meta = train_and_persist_supervised(push_to_db=True)
    logger.info("Modelos supervisados entrenados", extra={"rows_train": meta["rows_train"]})


def main() -> int:
    """Punto de entrada del contenedor ETL."""
    setup_logging(level=settings.log_level, fmt=settings.log_format)
    logger.info("Bootstrap iniciado")

    # 1. Schema
    if not schema_exists():
        logger.info("Schema ausente — aplicando init.sql")
        try:
            apply_init_sql()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Fallo aplicando schema")
            print(f"Bootstrap FALLÓ aplicando schema: {exc}", file=sys.stderr)
            return 1
    else:
        logger.info("Schema ya existe — skip init.sql")

    # 1b. Permisos (idempotente, corre en cada bootstrap)
    apply_grants()

    # 2. Datos
    n_rows = fact_row_count()
    if n_rows == 0:
        logger.info("fact_defunciones vacía — ejecutando ETL")
        try:
            run_etl()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Fallo ejecutando ETL")
            print(f"Bootstrap FALLÓ en ETL: {exc}", file=sys.stderr)
            return 1
    else:
        logger.info("fact_defunciones ya tiene datos — skip ETL", extra={"rows": n_rows})

    # 3. Modelos no supervisados (K-Means/PCA)
    if not unsupervised_models_exist():
        logger.info("Modelos no supervisados ausentes — entrenando")
        try:
            train_models()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Fallo entrenando modelos no supervisados")
            print(f"Bootstrap FALLÓ entrenando (no supervisado): {exc}", file=sys.stderr)
            return 1
    else:
        logger.info("Modelos no supervisados ya persistidos — skip entrenamiento")

    # 4. Modelos supervisados (clasificador + regresor)
    if not supervised_models_exist():
        logger.info("Modelos supervisados ausentes — entrenando")
        try:
            train_supervised_models()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Fallo entrenando modelos supervisados")
            print(f"Bootstrap FALLÓ entrenando (supervisado): {exc}", file=sys.stderr)
            return 1
    else:
        logger.info("Modelos supervisados ya persistidos — skip entrenamiento")

    logger.info("Bootstrap completado")
    print("✓ Bootstrap completado")
    return 0


if __name__ == "__main__":
    sys.exit(main())
