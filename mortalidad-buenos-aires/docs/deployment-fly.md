# Despliegue en Fly.io (microservicios)

Esta guía levanta los **3 microservicios** (api, dashboard, etl) + un
PostgreSQL gestionado, todos en la misma organización Fly para que se
hablen por DNS interno (`<app>.internal`), de forma análoga a una red de
`docker-compose`.

## Arquitectura desplegada

```
┌─────────────────────────────────────────────────────────────────┐
│   Tu organización Fly (red privada WireGuard, IPv6)             │
│                                                                 │
│  mortalidad-api.internal:8000 ──┐                               │
│      ↑ HTTPS público            │ HTTP interno                  │
│      │                          ▼                               │
│  mortalidad-dashboard.internal:8501                             │
│      ↑ HTTPS público                                            │
│                                                                 │
│  mortalidad-db.internal:5432   ◄── DATABASE_URL inyectada       │
│  mortalidad-etl.internal       (job sin puerto público)         │
│                                                                 │
│  Tigris (object storage S3-compatible):                         │
│      s3://mortalidad-data/defunciones.csv                       │
│      AWS_ENDPOINT_URL_S3 inyectada en api y etl                 │
└─────────────────────────────────────────────────────────────────┘
```

## Pre-requisitos

```bash
# 1. Instala flyctl (macOS)
brew install flyctl

# 2. Login
fly auth login
```

## Opción 1 — Setup automático (recomendado)

```bash
cd mortalidad-buenos-aires
./scripts/fly-init.sh
```

El script es **idempotente**: si una app o el Postgres ya existen, los detecta y
continúa. Despliega los 3 servicios al final.

## Opción 2 — Manual (paso a paso)

### 1. Crear las 3 apps

```bash
fly apps create mortalidad-api
fly apps create mortalidad-dashboard
fly apps create mortalidad-etl
```

### 2. Crear el cluster Postgres

```bash
fly postgres create \
    --name mortalidad-db \
    --region scl \
    --initial-cluster-size 1 \
    --vm-size shared-cpu-1x \
    --volume-size 1
```

Guarda las credenciales que muestra al final (las necesitarás para `psql`).

### 3. Adjuntar Postgres a `api` y `etl`

```bash
fly postgres attach mortalidad-db --app mortalidad-api
fly postgres attach mortalidad-db --app mortalidad-etl
```

Esto inyecta `DATABASE_URL` como secret en cada app.

### 4. Aplicar el schema inicial

```bash
# Conectate al Postgres
fly postgres connect --app mortalidad-db -d mortalidad

# Dentro de psql, pega el contenido de docker/postgres/init.sql
\i /tmp/init.sql   # o copia/pega
```

Alternativa rápida:

```bash
fly proxy 5432 --app mortalidad-db &
PGPASSWORD=<password> psql -h localhost -U postgres -d mortalidad -f docker/postgres/init.sql
```

### 5. Bucket Tigris (object storage para el CSV)

```bash
# Crear bucket S3-compatible — inyecta AWS_* secrets en el ETL
fly storage create --name mortalidad-data --app mortalidad-etl

# Compartirlo con la API (si quisieras leer desde ahí también)
fly storage update mortalidad-data --add-app mortalidad-api

# Subir el CSV (una sola vez)
fly storage objects put mortalidad-data defunciones.csv \
    --file data/raw/defunciones-ocurridas-y-registradas-en-la-republica-argentina-entre-los-anos-2005-2022.csv

# Setear la URL en el ETL
fly secrets set CSV_URL=s3://mortalidad-data/defunciones.csv --app mortalidad-etl
```

### 6. Setear `DASHBOARD_ORIGIN` en el API

```bash
fly secrets set DASHBOARD_ORIGIN=https://mortalidad-dashboard.fly.dev \
    --app mortalidad-api
```

### 7. Desplegar las 3 apps

```bash
fly deploy -c fly/api.fly.toml --remote-only
fly deploy -c fly/dashboard.fly.toml --remote-only
fly deploy -c fly/etl.fly.toml --remote-only
```

### 8. Cargar datos (ejecutar ETL una vez)

El CSV ya está en Tigris (paso 5). El ETL lo descarga al arrancar:

```bash
# Primera carga — lee Tigris, transforma, escribe a Postgres
fly machine run --app mortalidad-etl \
    registry.fly.io/mortalidad-etl:latest \
    python -m etl.main

# Entrenar modelos (los persiste en ml_artifacts dentro de Postgres)
fly machine run --app mortalidad-etl \
    registry.fly.io/mortalidad-etl:latest \
    python -m etl.train_models
```

### 9. Verificar

```bash
curl -s https://mortalidad-api.fly.dev/health
curl -s https://mortalidad-api.fly.dev/estadisticas/serie-temporal | head -c 200
open https://mortalidad-dashboard.fly.dev
```

## Auto-deploy con GitHub Actions

El workflow `.github/workflows/fly-deploy.yml` despliega automáticamente
los 3 servicios en cada push a `main`.

Pre-req: crear un token y agregarlo al repo:

```bash
fly auth token   # copia el output
```

En GitHub: Settings → Secrets and variables → Actions → New repository secret
- Nombre: `FLY_API_TOKEN`
- Valor: el token

## Operaciones comunes

| Tarea | Comando |
|---|---|
| Ver logs en vivo | `fly logs --app mortalidad-api` |
| Conexión SSH al contenedor | `fly ssh console --app mortalidad-api` |
| Conectarse a Postgres | `fly postgres connect --app mortalidad-db -d mortalidad` |
| Re-correr el ETL | `fly machine run --app mortalidad-etl … python -m etl.main` |
| Escalar vertical | `fly scale vm shared-cpu-2x --app mortalidad-api` |
| Setear secret | `fly secrets set KEY=value --app mortalidad-api` |
| Ver estado | `fly status --app mortalidad-api` |

## Hibernación y costos

Las 3 apps usan `auto_stop_machines = "stop"`. Cuando no hay tráfico se
apagan; al primer request despiertan en 1-2 s. El free tier de Fly cubre:

- 3 VMs `shared-cpu-1x` con 256MB
- 3GB de Postgres en cluster simple
- 160GB de tráfico saliente

Para este proyecto académico el costo esperado es **\$0/mes** mientras el
tráfico se mantenga bajo.

## Equivalencias con docker-compose

| docker-compose | Fly.io |
|---|---|
| `services:` con misma red | Apps de la misma org, red privada automática |
| `links: - api` | DNS interno `<app>.internal` |
| `environment:` | `[env]` en toml + `fly secrets set` |
| `depends_on` | No hay; `<app>.internal` resuelve cuando la app está up |
| `volumes:` | `fly volumes create` + `[[mounts]]` |
| `ports: "8000:8000"` | `[http_service] internal_port = 8000` |
| Job sin `ports` | Sin `[http_service]` |
| `command:` | `processes = ["app"]` + `[processes]` |
| Healthcheck | `[checks]` |

## Troubleshooting

| Problema | Causa probable | Solución |
|---|---|---|
| `502 Bad Gateway` en el API | Healthcheck fallando | `fly logs --app mortalidad-api` para ver el error de arranque |
| Dashboard dice "No se pudo conectar" | `API_URL` mal o app dormida | Confirma `mortalidad-api.fly.dev/health` responde |
| `/ml/cluster` devuelve 503 | No hay modelos en disco ni en Postgres | Corre `fly machine run … python -m etl.train_models` |
| ETL OOM (out of memory) | 1GB no alcanza para el CSV completo | `fly scale vm shared-cpu-2x --memory 2048 --app mortalidad-etl` |
| Apps no se hablan | No están en la misma org | Verifica con `fly apps list --org personal` |
| ETL falla con `NoCredentialsError` | Faltan secrets de Tigris | Verifica `fly secrets list --app mortalidad-etl` muestra `AWS_*` y `BUCKET_NAME` |
| `CSV_URL` no se descarga | `CSV_URL` mal seteada | `fly secrets list --app mortalidad-etl` debe mostrar `CSV_URL` (sin valor por seguridad) |
