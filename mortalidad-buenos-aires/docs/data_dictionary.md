# Diccionario de datos

## Fuentes

### 1. CSV defunciones (Datos Abiertos Argentina)

- Origen: <https://datos.gob.ar/dataset/salud-defunciones-ocurridas-y-registradas>
- Archivo: `defunciones-ocurridas-y-registradas-en-la-republica-argentina-entre-los-anos-2005-2022.csv`
- Cobertura: 2005-2022, todas las jurisdicciones de Argentina.
- Filas: ~10M registros agregados por (año, sexo, edad, jurisdicción, CIE-10).

### 2. API datos.gob.ar — series de tiempo INDEC

- Endpoint: `https://apis.datos.gob.ar/series/api/series`
- Doc: <https://datosgobar.github.io/series-tiempo-ar-api/>
- Uso: población anual de la provincia para calcular tasa por 100k.
- Fallback: tabla `POBLACION_BA_FALLBACK` en `etl/extract/load_api.py`.

### 3. PostgreSQL — `dim_cie10`

- Tabla seedada por `docker/postgres/init.sql`.
- 26 filas (una por letra inicial CIE-10).

## Tabla `fact_defunciones`

| Columna | Tipo | Descripción |
|---|---|---|
| `id` | BIGSERIAL PK | Identificador interno |
| `anio` | INTEGER | Año del fallecimiento |
| `sexo` | TEXT | `varon` o `mujer` |
| `grupo_edad` | TEXT | Etiqueta de quintil etario (ya limpia) |
| `jurisdiccion` | TEXT | Jurisdicción de residencia |
| `cie10_causa_id` | TEXT | Código CIE-10 (3 chars) |
| `cie10_clasificacion` | TEXT | Descripción del código |
| `supracategoria` | TEXT | Capítulo CIE-10 agrupado |
| `cantidad` | INTEGER | Defunciones registradas |
| `poblacion` | BIGINT | Población del año (de la API) |
| `tasa_por_100k` | NUMERIC(10,4) | `cantidad / poblacion * 100000` |

Índices: `anio`, `sexo`, `grupo_edad`, `supracategoria`, `(anio, supracategoria)`.

## Tabla `dim_cie10`

| Columna | Tipo | Descripción |
|---|---|---|
| `letra` | CHAR(1) PK | Letra inicial del código (A, B, C, …) |
| `capitulo` | TEXT | Nombre del capítulo |
| `descripcion` | TEXT | Rango y descripción larga |

## Transformaciones del ETL

| Función | Efecto |
|---|---|
| `drop_muerte_materna` | Elimina dos columnas ~100% nulas |
| `normalizar_cie10_upper` | `i50` → `I50` |
| `mapear_cie10_faltantes` | Rellena `cie10_clasificacion` para 15 códigos |
| `eliminar_jurisdiccion_nula` | Drop rows sin jurisdicción |
| `eliminar_sexo_desconocido` | Drop `Sexo == "desconocido"` |
| `eliminar_edad_sin_especificar` | Drop `grupo_edad == "06.Sin especificar"` |
| `limpiar_etiqueta_grupo_edad` | Quita prefijo `"01."` y dobles espacios |
| `filtrar_jurisdiccion` | Restringe a la jurisdicción foco (default Buenos Aires) |
| `agregar_supracategoria` | Calcula capítulo CIE-10 |
| `join_poblacion` | Agrega `poblacion` + `tasa_por_100k` |
| `join_dim_cie10` | Joina catálogo desde Postgres |

## Validación pandera

Esquemas definidos en `etl/schemas.py`:

- `RAW_SCHEMA` — valida lo que sale del CSV.
- `TRANSFORMED_SCHEMA` — valida lo que va a la BD.

Si una validación falla, el ETL aborta y loggea el detalle.
