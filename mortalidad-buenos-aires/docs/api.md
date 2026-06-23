# Referencia de la API

URL base local: `http://localhost:8000`

Las definiciones formales (OpenAPI 3.1) están en `/docs` (Swagger UI) y
`/redoc`. Lo que sigue es una referencia rápida con ejemplos `curl`.

## Health

### `GET /health`

Liveness probe. No toca la base.

```bash
curl -s http://localhost:8000/health
```

```json
{"status": "ok", "version": "1.0.0"}
```

### `GET /ready`

Readiness probe. Hace `SELECT 1` a la base.

```bash
curl -s http://localhost:8000/ready
```

```json
{"status": "ok", "database": "up"}
```

## Defunciones

### `GET /defunciones`

Listado paginado con filtros opcionales.

Parámetros:

| Nombre | Tipo | Default | Descripción |
|---|---|---|---|
| `anio` | int | – | 2005–2030 |
| `sexo` | str | – | `varon` o `mujer` |
| `grupo_edad` | str | – | Etiqueta exacta |
| `supracategoria` | str | – | Capítulo CIE-10 |
| `limit` | int | 100 | 1–1000 |
| `offset` | int | 0 | ≥ 0 |

```bash
curl -s "http://localhost:8000/defunciones?anio=2020&sexo=varon&limit=5"
```

## Estadísticas

### `GET /estadisticas/serie-temporal`

Total y tasa promedio por año.

```bash
curl -s http://localhost:8000/estadisticas/serie-temporal | jq '.[0]'
```

### `GET /estadisticas/top-causas?n=10&anio=2020`

Top-N capítulos CIE-10 por cantidad.

### `GET /estadisticas/por-grupo-edad`

Distribución por grupo de edad × sexo.

### `GET /estadisticas/tasa-mortalidad`

Tasa promedio por 100.000 habitantes, anual.

## ML

### `POST /ml/cluster`

Asigna el vector a un cluster K-Means.

```bash
curl -s -X POST http://localhost:8000/ml/cluster \
  -H "content-type: application/json" \
  -d '{
        "cie10_clasificacion": 10.0,
        "sexo": 1.0,
        "grupo_edad": 2.0,
        "anio": 0.5,
        "cantidad": 0.1
      }'
```

```json
{"cluster": 2, "distance_to_centroid": 0.4321}
```

### `POST /ml/pca`

Proyecta el vector a (PC1, PC2).

### `GET /ml/metadata`

Devuelve la metadata del último entrenamiento: timestamp, silhouette,
varianza explicada PCA, lista de features.

## Códigos de error

| HTTP | Significado |
|---|---|
| 422 | Validación Pydantic falló (parámetro inválido) |
| 503 | Modelos ML no están en disco — ejecuta `python -m etl.train_models` |
| 500 | Error no manejado (loggeado con stack en el contenedor) |
