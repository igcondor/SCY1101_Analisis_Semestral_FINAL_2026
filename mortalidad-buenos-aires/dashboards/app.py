"""Página principal (home) del dashboard.

Navega entre las tres vistas multi-audiencia en la sidebar izquierda.
"""
import streamlit as st

from dashboards.theme import set_page

set_page("Inicio", icon="🏥")

st.title("Mortalidad en la Provincia de Buenos Aires")
st.caption("Defunciones registradas 2005-2022 · Datos abiertos República Argentina")

st.markdown(
    """
Este dashboard ofrece tres lecturas del mismo dataset, adaptadas a distintas
audiencias:

- 📈 **Página Ejecutiva** — KPIs, tendencias anuales y principales causas en
  lenguaje de negocio. Apta para tomadores de decisión.
- 🔬 **Página Técnica** — clustering K-Means, proyección PCA y métricas de los
  modelos. Apta para equipos de ciencia de datos.
- 🛠 **Página Operativa** — filtros granulares, tabla cruda con descarga CSV y
  drill-down por causa. Apta para analistas y operaciones.

---

### Arquitectura

```
CSV (defunciones)  ─┐
API datos.gob.ar   ─┼──►  ETL  ──►  PostgreSQL  ──►  FastAPI  ──►  Dashboard
PostgreSQL (CIE10) ─┘                                  │
                                                    Modelos joblib
                                                    (KMeans · PCA)
```

### Estado de la API
"""
)

from dashboards import api_client  # noqa: E402 — import diferido

try:
    estado = api_client.health()
    if estado.get("database") == "up":
        st.success(f"API conectada — base de datos {estado['database']}")
    else:
        st.warning(f"API responde pero la base está {estado.get('database')}")
except Exception as exc:  # noqa: BLE001
    st.error(f"No se pudo conectar a la API ({api_client.API_URL}): {exc}")

st.divider()
st.caption(
    "Proyecto SCY1101 — Programación para la Ciencia de Datos · DuocUC 2025"
)
