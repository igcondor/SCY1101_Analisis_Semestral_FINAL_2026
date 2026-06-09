# mortalidad-buenos-aires

Proyecto de ciencia de datos sobre defunciones registradas en la República Argentina (2005-2022), con foco en la jurisdicción de Buenos Aires. Material original distribuido desde el notebook `Progra_Ev_2_ReIntento (2).ipynb`.

## Estructura

```
mortalidad-buenos-aires/
├── data/                # Datos crudos, externos, procesados y de validación
├── notebooks/           # EDA, clustering, PCA, entrenamiento supervisado
├── etl/                 # Extract / Transform / Load + utilidades + main.py
├── api/                 # (placeholder)
├── dashboards/          # (placeholder)
├── tests/               # (placeholder)
├── docker/              # (placeholder)
├── docs/                # (placeholder)
└── repo/                # (placeholder)
```

## Setup

```bash
pip install -r requirements.txt
```

## Datos

Coloque el archivo CSV original en `data/raw/`:

```
data/raw/defunciones-ocurridas-y-registradas-en-la-republica-argentina-entre-los-anos-2005-2022.csv
```

## Ejecución

### Pipeline ETL

```bash
python -m etl.main
```

Devuelve un DataFrame con 119.308 filas (defunciones filtradas para Buenos Aires).

### Notebooks

Ejecutar desde la carpeta `notebooks/`:

- `EDA.ipynb` — exploración, limpieza, feature engineering, correlación y visualizaciones temporales/por edad.
- `clustering.ipynb` — K-Means (K=4) con método del codo y Silhouette Score.
- `pca.ipynb` — PCA 2D, loadings, scatters y centroides.
- `entrenamiento_supervisado.ipynb` — placeholder (sección original incompatible omitida).

## Notas

- La sección de Random Forest del notebook original (`04_hyperparameter_optimization`, celdas 92-104) se descarta porque dependía de datasets retail (`TransManual.csv`, `clean_retail_store_sales.csv`) y de `src.preprocesamiento_data`, recursos no disponibles e incompatibles con el dominio de mortalidad.
- Las carpetas `api/`, `dashboards/`, `tests/`, `docker/`, `docs/` y `repo/` se crean vacías como esqueleto del proyecto.
