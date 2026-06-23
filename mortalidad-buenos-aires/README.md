# Mortalidad en la Provincia de Buenos Aires (2005-2022)

[![CI](https://img.shields.io/badge/CI-pytest%20%2B%20ruff-blue)]()
[![Python](https://img.shields.io/badge/python-3.11-blue.svg)]()
[![License](https://img.shields.io/badge/license-MIT-green.svg)]()

Solución **end-to-end** de análisis de datos sobre defunciones registradas en
la República Argentina entre 2005 y 2022, con foco en la Provincia de Buenos
Aires. Integra tres fuentes de datos, expone una API REST documentada,
sirve modelos no supervisados (K-Means + PCA) y un dashboard multi-audiencia.

> Trabajo presentado para la **Evaluación Parcial N°3 — SCY1101 Programación
> para la Ciencia de Datos** (Maleta Didáctica DuocUC).

---

## Arquitectura

```
┌─────────────┐  ┌─────────────────────┐  ┌──────────────────┐
│ CSV         │  │ API datos.gob.ar    │  │ PostgreSQL       │
│ defunciones │  │ (población INDEC)   │  │ (catálogo CIE10) │
└─────┬───────┘  └──────────┬──────────┘  └────────┬─────────┘
      │                     │                       │
      └─────────────────────┴───────────────────────┘
                            │
                            ▼
                   ┌──────────────────┐
                   │  ETL  (Python)   │
                   │  pandera + log   │
                   └────────┬─────────┘
                            │ UPSERT
                            ▼
                   ┌──────────────────┐
                   │   PostgreSQL     │
                   │  fact_defunciones│
                   └────────┬─────────┘
                            │
                ┌───────────┴────────────┐
                ▼                        ▼
        ┌───────────────┐        ┌──────────────────┐
        │ FastAPI (REST)│◄──────►│  Streamlit       │
        │  + ML joblib  │        │  Dashboard 3 vistas
        └───────────────┘        └──────────────────┘
              │
              └─► Docs OpenAPI en /docs
```

Detalle completo en [`docs/architecture.md`](docs/architecture.md).

## Stack

| Capa | Tecnología |
|---|---|
| Lenguaje | Python 3.11 |
| ETL | pandas, pandera, tenacity, SQLAlchemy |
| API | FastAPI + Uvicorn |
| ML | scikit-learn, joblib |
| Dashboard | Streamlit + Plotly |
| BD | PostgreSQL 16 |
| Contenedores | Docker (multi-stage) + docker-compose |
| Tests | pytest, pytest-cov |
| Object storage | Tigris (S3-compatible) para el CSV crudo |
| Despliegue | Fly.io (recomendado) / Railway.app |

## Estructura del repo

```
mortalidad-buenos-aires/
├── etl/         # Pipeline ETL (extract / transform / load + train_models)
├── api/         # FastAPI: routers, ORM, schemas, inferencia ML
├── dashboards/  # Streamlit multi-página (Ejecutiva / Técnica / Operativa)
├── docker/      # Dockerfiles, docker-compose.yml, init.sql
├── tests/       # pytest (ETL, API, modelos, dashboard)
├── docs/        # Arquitectura, API, deployment, manual usuario
├── repo/        # Evidencia de prácticas Git (branching, PRs, reviews)
├── data/        # raw / interim / processed / models (gitignored)
└── notebooks/   # EDA, clustering, PCA, supervisado (referencia original)
```

## Quickstart local (Docker)

```bash
# 1. Copia variables de entorno
cp .env.example .env

# 2. Descarga el CSV original a data/raw/
#    https://datos.gob.ar/dataset/salud-defunciones-ocurridas-y-registradas
#    (archivo: defunciones-ocurridas-y-registradas-en-la-republica-argentina-entre-los-anos-2005-2022.csv)

# 3. Levanta el stack completo
cd docker
docker compose up --build

# 4. Ejecuta el ETL una vez (carga datos a Postgres)
docker compose run --rm etl

# 5. Entrena modelos (en host o en contenedor etl)
docker compose run --rm etl python -m etl.train_models
```

URLs locales:

| Servicio | URL |
|---|---|
| API Swagger | http://localhost:8000/docs |
| API ReDoc | http://localhost:8000/redoc |
| Dashboard | http://localhost:8501 |
| Postgres | localhost:5432 (mortalidad/mortalidad) |

## Tests

```bash
pip install -r requirements-dev.txt
pytest -v --cov=etl --cov=api --cov-report=term-missing
```

## Despliegue

### Fly.io (recomendado — microservicios reales)

Pre-requisito (una sola vez):

```bash
# 1. Instala flyctl
brew install flyctl

# 2. Login interactivo
fly auth login

# 3. Token para que GitHub Actions despliegue por ti
fly auth token | gh secret set FLY_API_TOKEN \
    --repo CondePoponcio/mortalidad-buenos-aires
```

Sincronización de toda la infraestructura (reconciliador idempotente):

```bash
# 4. Descarga el CSV original a data/raw/
#    https://datos.gob.ar/dataset/salud-defunciones-ocurridas-y-registradas

# 5. Reconcilia el estado: crea/actualiza apps, Postgres, Tigris, secrets,
#    sube CSV (si difiere), despliega, arranca ETL. Idempotente.
./scripts/fly-init.sh
```

El script funciona como un **state synchronizer** (modelo tipo Terraform):
- Lee el estado actual de cada recurso.
- Aplica solo el delta para llegar al deseado.
- Maneja casos borde: cooldown de Tigris (fallback con timestamp), users
  huérfanos de Postgres (cleanup vía ssh + retry), CSV faltante en bucket
  (head_object check), secrets ya seteados (skip por digest).
- Se ejecuta automáticamente en cada `git push origin main` vía GitHub
  Actions (`.github/workflows/fly-deploy.yml`).

El seed es **automático**: el contenedor `mortalidad-etl` ejecuta
`etl.bootstrap` como CMD por defecto, que de forma idempotente:

1. Aplica `init.sql` si las tablas no existen.
2. Si `fact_defunciones` está vacía, descarga el CSV de Tigris y lo carga.
3. Si no hay modelos en `ml_artifacts`, entrena K-Means/PCA y los persiste.
4. Si todo ya existe, sale 0 inmediato (no-op).

Cada `git push origin main` redepliega los 3 servicios y, si fuera necesario,
re-siembra. El workflow `.github/workflows/fly-deploy.yml` automatiza esto.

Para verificar el seed manualmente:

```bash
fly logs --app mortalidad-etl
```

Para re-correrlo a mano (idempotente — útil cuando actualizaste el CSV en
Tigris o quieres reentrenar modelos):

```bash
# 1. Listar las máquinas del servicio ETL (toma el ID de la primera "app")
fly machine list --app mortalidad-etl

# 2. Arrancarla — la VM ejecuta `python -m etl.bootstrap` y vuelve a stopped
fly machine start <machine-id> --app mortalidad-etl

# 3. Seguir los logs en vivo
fly logs --app mortalidad-etl
```

El bootstrap es idempotente: detecta si la BD ya tiene datos / modelos y
salta esas fases. Una corrida en frío toma ~3-5 min (descarga CSV +
ETL + entrenamiento); una corrida con todo cacheado sale en ~10s.

URLs productivas:

| Servicio | URL |
|---|---|
| API Swagger | https://mortalidad-api.fly.dev/docs |
| Dashboard | https://mortalidad-dashboard.fly.dev |
| Postgres | `mortalidad-db.internal:5432` (privado) |
| Tigris bucket | `s3://mortalidad-data/` (privado) |

Las 3 apps Fly se hablan por DNS interno (`mortalidad-api.internal:8000`),
equivalente a la red privada de `docker-compose`. Guía detallada en
[`docs/deployment-fly.md`](docs/deployment-fly.md).

### Railway (alternativa)

Cada servicio (`api`, `dashboard`, `etl`) como servicio separado en Railway.
Guía en [`docs/deployment.md`](docs/deployment.md).

## Documentación

- [`docs/architecture.md`](docs/architecture.md) — Arquitectura y flujo de datos
- [`docs/api.md`](docs/api.md) — Endpoints, ejemplos curl
- [`docs/deployment-fly.md`](docs/deployment-fly.md) — Guía de despliegue Fly.io
- [`docs/deployment.md`](docs/deployment.md) — Guía de despliegue Railway
- [`docs/user_manual.md`](docs/user_manual.md) — Manual del dashboard
- [`docs/data_dictionary.md`](docs/data_dictionary.md) — Diccionario de datos

## Autor

Felipe Condore — SCY1101 · DuocUC 2025

## Licencia

MIT
