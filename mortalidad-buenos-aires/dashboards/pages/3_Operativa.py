"""Página Operativa — filtros granulares, tabla y drill-down."""
import pandas as pd
import plotly.express as px
import streamlit as st

from dashboards import api_client
from dashboards.theme import PALETTE, set_page

set_page("Operativa", icon="🛠")

st.title("Vista Operativa")
st.caption("Exploración granular con filtros, tabla descargable y drill-down.")

# --- Filtros ---
with st.sidebar:
    st.header("Filtros")
    anio = st.selectbox("Año", [None, *range(2005, 2023)], index=0)
    sexo = st.selectbox("Sexo", [None, "varon", "mujer"], index=0)
    grupo_edad = st.selectbox(
        "Grupo de edad",
        [None, "De a 0 a 14 anios", "De 15 a 34 anios", "De 35 a 54 anios",
         "De 55 a 74 anios", "De 75 anios y mas"],
        index=0,
    )
    supracat = st.text_input("Supracategoría CIE-10 (texto exacto)", value="")
    limit = st.slider("Filas a mostrar", 50, 1000, 200, step=50)

try:
    payload = api_client.defunciones(
        anio=anio,
        sexo=sexo,
        grupo_edad=grupo_edad,
        supracategoria=supracat or None,
        limit=limit,
    )
except Exception as exc:  # noqa: BLE001
    st.error(f"No se pudo cargar la API: {exc}")
    st.stop()

st.metric("Total filas según filtros", payload["total"])
df = pd.DataFrame(payload["items"])

if df.empty:
    st.info("No hay resultados para los filtros aplicados.")
    st.stop()

# --- Tabla ---
st.subheader("Detalle")
st.dataframe(df, use_container_width=True, height=380)

st.download_button(
    "⬇️ Descargar CSV",
    data=df.to_csv(index=False).encode("utf-8"),
    file_name="defunciones_filtrado.csv",
    mime="text/csv",
)

st.divider()

# --- Drill-down ---
st.subheader("Drill-down: defunciones por capítulo en la selección")
agg = (
    df.groupby("supracategoria", as_index=False)["cantidad"]
    .sum()
    .sort_values("cantidad", ascending=True)
)
fig = px.bar(
    agg,
    x="cantidad",
    y="supracategoria",
    orientation="h",
    color="supracategoria",
    color_discrete_sequence=PALETTE,
)
fig.update_layout(showlegend=False, height=420,
                 xaxis_title="Defunciones",
                 yaxis_title="Capítulo CIE-10")
st.plotly_chart(fig, use_container_width=True)
