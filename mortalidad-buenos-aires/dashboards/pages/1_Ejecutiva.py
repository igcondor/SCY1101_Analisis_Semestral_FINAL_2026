"""Página Ejecutiva — orientada a tomadores de decisión.

Lenguaje de negocio (marco actuarial / aseguradora), KPIs grandes, lecturas
de alto nivel. Mortalidad histórica = siniestralidad para una aseguradora
de vida/salud: estos datos son el insumo central de tablas de mortalidad,
cálculo de reservas y diseño de producto.
"""
import pandas as pd
import plotly.express as px
import streamlit as st

from dashboards import api_client
from dashboards.theme import PALETTE, set_page

set_page("Ejecutiva", icon="📈")

st.title("Vista Ejecutiva — Riesgo de Mortalidad")
st.caption(
    "Resumen de siniestralidad histórica para decisiones de producto, "
    "suscripción y reservas. Audiencia: dirección de negocio / actuarial."
)

try:
    serie = pd.DataFrame(api_client.serie_temporal())
    causas = pd.DataFrame(api_client.top_causas(n=10))
except Exception as exc:  # noqa: BLE001
    st.error(f"No se pudo cargar la API: {exc}")
    st.stop()

if serie.empty:
    st.warning("Aún no hay datos cargados. Ejecuta el ETL primero.")
    st.stop()

# --- KPIs ---
total = int(serie["total_defunciones"].sum())
tasa_prom = float(serie["tasa_promedio"].fillna(0).mean())
top_causa = causas.iloc[0]["supracategoria"] if not causas.empty else "—"
ultimo = serie.iloc[-1]
penultimo = serie.iloc[-2] if len(serie) > 1 else ultimo
yoy = (ultimo["total_defunciones"] / penultimo["total_defunciones"] - 1) * 100

k1, k2, k3, k4 = st.columns(4)
k1.metric("Siniestros históricos registrados", f"{total:,.0f}".replace(",", "."))
k2.metric("Tasa de mortalidad promedio (/100k)", f"{tasa_prom:,.1f}")
k3.metric("Riesgo dominante (capítulo CIE-10)", top_causa)
k4.metric(f"Variación de siniestralidad {ultimo['anio']} vs {penultimo['anio']}", f"{yoy:+.1f}%")

st.divider()

# --- Tendencia anual ---
st.subheader("Evolución histórica de la siniestralidad")
fig_line = px.line(
    serie,
    x="anio",
    y="total_defunciones",
    markers=True,
    color_discrete_sequence=[PALETTE[0]],
)
fig_line.update_layout(
    xaxis_title="Año",
    yaxis_title="Siniestros (defunciones)",
    height=380,
)
st.plotly_chart(fig_line, use_container_width=True)

# --- Top causas ---
st.subheader("Concentración de riesgo por causa")
st.caption(
    "Capítulos CIE-10 que más siniestros generan — referencia directa para "
    "el diseño de coberturas y la ponderación de primas por línea de producto."
)
fig_bar = px.bar(
    causas.sort_values("total"),
    x="total",
    y="supracategoria",
    orientation="h",
    color="supracategoria",
    color_discrete_sequence=PALETTE,
)
fig_bar.update_layout(showlegend=False, height=420,
                     xaxis_title="Siniestros (defunciones)",
                     yaxis_title="Capítulo / causa")
st.plotly_chart(fig_bar, use_container_width=True)

with st.expander("📝 Lectura ejecutiva"):
    st.markdown(
        f"""
        - La base histórica abarca **{ultimo['anio'] - serie.iloc[0]['anio'] + 1}**
          años con **{total:,.0f}** siniestros (defunciones) registrados —
          la muestra mínima recomendable para calibrar una tabla de
          mortalidad propia en vez de depender de tablas genéricas de mercado.
        - La siniestralidad interanual varió **{yoy:+.1f}%** en el último
          período — una señal a vigilar antes de fijar primas o reservas
          para el próximo ciclo.
        - El riesgo se concentra en **{top_causa}**: las líneas de producto
          (vida, salud, accidentes personales) deberían ponderar su
          exposición a esta causa de forma diferenciada en vez de aplicar
          una prima plana.
        """.replace(",", ".")
    )

st.divider()

# --- Valor de negocio de los modelos predictivos ---
st.subheader("Capacidad predictiva del modelo actuarial")
try:
    meta_sup = api_client.ml_metadata_supervisado()
except Exception:  # noqa: BLE001
    meta_sup = None

if meta_sup:
    clf_acc = meta_sup["clasificador_grupo_edad"]["metrics"]["test_accuracy"]
    reg_r2 = meta_sup["regresor_cantidad"]["metrics"]["test_r2_orig"]
    b1, b2 = st.columns(2)
    b1.metric("Precisión al clasificar el grupo etario de riesgo", f"{clf_acc*100:.0f}%")
    b2.metric("Capacidad explicativa de la siniestralidad esperada (R²)", f"{reg_r2:.2f}")
else:
    st.info(
        "Los modelos predictivos aún no están disponibles "
        "(ejecuta `python -m etl.train_supervised_models`)."
    )
