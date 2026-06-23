# Guía de despliegue en Railway.app

Railway no orquesta `docker-compose` directamente. Cada servicio se despliega
como un servicio independiente con su propio Dockerfile. El plugin oficial
de PostgreSQL provee `DATABASE_URL` por variable de entorno.

## Pre-requisitos

- Cuenta en [Railway](https://railway.app).
- Repo en GitHub con el código (ver `docs/git_setup.md`).
- CLI opcional: `npm i -g @railway/cli`.

## Paso a paso

### 1. Crear proyecto y plugin PostgreSQL

1. New Project → Empty Project.
2. `+ New` → **Database** → **Add PostgreSQL**. Esto crea un servicio
   `Postgres` que expone la variable `${{Postgres.DATABASE_URL}}`.

### 2. Cargar el esquema inicial

Conéctate a la BD con `psql $DATABASE_URL` o desde Railway → Postgres →
**Data** y ejecuta el contenido de `docker/postgres/init.sql`. Esto crea las
tablas `dim_cie10`, `dim_jurisdiccion`, `fact_defunciones` y las vistas.

### 3. Servicio `api`

1. `+ New` → **GitHub Repo** → selecciona el repo.
2. Settings → **Source Directory**: `.`
3. Settings → **Builder**: Dockerfile.
4. Settings → **Dockerfile Path**: `docker/Dockerfile.api`.
5. Variables:
   - `DATABASE_URL` = `${{Postgres.DATABASE_URL}}`
   - `MODEL_DIR` = `/app/data/models`
   - `DASHBOARD_ORIGIN` = URL pública del servicio dashboard (puedes setearla luego)
   - `LOG_LEVEL` = `INFO`
6. Settings → **Networking** → **Generate Domain** → copia la URL.
7. Settings → **Healthcheck Path**: `/health`.

### 4. Servicio `dashboard`

1. `+ New` → mismo repo.
2. **Dockerfile Path**: `docker/Dockerfile.dashboard`.
3. Variables:
   - `API_URL` = URL pública del servicio api del paso anterior.
4. Generate Domain.

### 5. Servicio `etl` (job de carga inicial)

El ETL es un job one-shot. Opciones:

**Opción A — Railway Cron** (recomendado, requiere plan Pro):

1. `+ New` → mismo repo.
2. **Dockerfile Path**: `docker/Dockerfile.etl`.
3. Variables: `DATABASE_URL`, `INDEC_API_URL`, `MODEL_DIR`, `CSV_PATH`.
4. Settings → **Cron Schedule**: `0 4 * * 1` (lunes 4am, por ejemplo).

**Opción B — Ejecución local apuntando a Railway**:

```bash
export DATABASE_URL="$(railway variables get DATABASE_URL --service Postgres)"
python -m etl.main
python -m etl.train_models
```

Sube los `.joblib` generados como Volume del servicio api o re-deploy con
los archivos en el árbol git.

### 6. Cargar el CSV crudo

El CSV es muy grande para subirlo a git. Tres opciones:

- **Volume Railway**: crea un Volume en el servicio `etl` montado en
  `/app/data/raw/` y sube el archivo via `railway run --service etl bash`.
- **S3 / URL pública**: modifica `etl/extract/load_csv.py` para descargar
  desde una URL configurable.
- **Ejecución local**: corre el ETL en tu máquina apuntando a la DB de
  Railway (más simple para evaluación).

### 7. Configurar `DASHBOARD_ORIGIN` y CORS

Vuelve al servicio `api` → Variables → setea
`DASHBOARD_ORIGIN=https://<tu-dashboard>.up.railway.app` y haz un redeploy
para que CORS deje pasar al dashboard.

### 8. Verificar

```bash
curl -s https://<tu-api>.up.railway.app/health
curl -s https://<tu-api>.up.railway.app/estadisticas/serie-temporal | head -c 200
open https://<tu-dashboard>.up.railway.app
```

## URLs públicas del despliegue

Reemplaza estos placeholders en el README cuando el deploy esté listo:

| Servicio | URL |
|---|---|
| API Swagger | `https://<api>.up.railway.app/docs` |
| Dashboard | `https://<dashboard>.up.railway.app` |
| Repo GitHub | `https://github.com/<usuario>/mortalidad-buenos-aires` |

## Troubleshooting

| Síntoma | Causa probable | Solución |
|---|---|---|
| `502` en la API | Healthcheck falla | Revisa `LOG_LEVEL=DEBUG` y los logs de Railway |
| Dashboard muestra "No se pudo conectar" | `API_URL` mal | Confirma que sea la URL pública con `https://` |
| CORS error | `DASHBOARD_ORIGIN=*` no se acepta con credenciales | Pon la URL exacta del dashboard |
| `503` en `/ml/*` | Faltan `.joblib` | Ejecuta `python -m etl.train_models` apuntando a la BD |
