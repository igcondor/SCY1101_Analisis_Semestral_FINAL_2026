# Manual de usuario — Dashboard Mortalidad Buenos Aires

El dashboard tiene una **página principal** y tres vistas en la barra lateral
izquierda. Cada vista está pensada para una audiencia distinta.

## Página principal (Inicio)

- Resumen del proyecto y arquitectura.
- Indicador de estado de la API: verde si la base responde, rojo si no.

## 📈 Vista Ejecutiva

**Audiencia**: tomadores de decisión, gerencia, salud pública.

**Qué ofrece**:
- 4 KPIs: defunciones totales, tasa promedio, principal causa, variación interanual.
- Tendencia anual (línea).
- Top 10 causas por capítulo CIE-10 (barras horizontales).
- Lectura ejecutiva auto-generada en lenguaje de negocio.

**Cómo usarla**: solo abrirla. No hay filtros — la vista es agregada.

## 🔬 Vista Técnica

**Audiencia**: data scientists, equipo técnico.

**Qué ofrece**:
- Métricas del modelo: filas entrenadas, K del K-Means, silhouette, varianza PCA.
- Formulario de **predicción interactiva**: completas 5 features y obtienes:
  - Cluster asignado.
  - Distancia al centroide.
  - Coordenadas (PC1, PC2) del PCA.
- Distribución de defunciones por grupo de edad y sexo.

**Cómo usarla**:
1. Asegúrate que `python -m etl.train_models` haya generado los `.joblib`.
2. Modifica los valores numéricos de las features.
3. Click **Predecir** → ves cluster y proyección PCA.

## 🛠 Vista Operativa

**Audiencia**: analistas, operaciones, fiscalización.

**Qué ofrece**:
- Filtros en sidebar: año, sexo, grupo de edad, supracategoría.
- Tabla con detalle (ordenable, descargable como CSV).
- Drill-down por capítulo en la selección.

**Cómo usarla**:
1. Aplica filtros en la sidebar.
2. Revisa la tabla.
3. Exporta CSV con el botón ⬇️.
4. Mira el gráfico de barras para ver la distribución de la selección.

## Tip de defensa

Cada vista responde a un focus distinto de la pauta: la Ejecutiva cubre
"valor de negocio", la Técnica cubre "argumentación técnica" y la Operativa
cubre "adaptación a usuario operativo". Mostrarlas en ese orden durante la
presentación demuestra capacidad de adaptar el discurso por audiencia.
