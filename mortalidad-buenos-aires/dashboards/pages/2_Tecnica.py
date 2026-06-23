"""Página Técnica — clustering, PCA, modelos supervisados y diagnóstico
cuantitativo para audiencia de ciencia de datos.
"""
import pandas as pd
import plotly.express as px
import streamlit as st

from dashboards import api_client
from dashboards.theme import PALETTE, set_page

set_page("Técnica", icon="🔬")

st.title("Vista Técnica")
st.caption("Modelos no supervisados, supervisados y diagnóstico cuantitativo.")

ORDEN_EDAD = [
    "De a 0 a 14 anios",
    "De 15 a 34 anios",
    "De 35 a 54 anios",
    "De 55 a 74 anios",
    "De 75 anios y mas",
]

# ============================================================
# 1. NO SUPERVISADO — K-Means + PCA
# ============================================================
st.header("1. Aprendizaje no supervisado — K-Means y PCA")

try:
    meta = api_client.ml_metadata()
except Exception as exc:  # noqa: BLE001
    st.error(
        f"El servicio ML no está disponible: {exc}\n\n"
        "Ejecuta `python -m etl.train_models` para entrenar los modelos."
    )
    st.stop()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Filas entrenadas", f"{meta['rows_train']:,}".replace(",", "."))
c2.metric("Clusters K-Means", meta["kmeans"]["k"])
c3.metric("Silhouette (5k)", meta["kmeans"]["silhouette_5k"])
c4.metric("PCA varianza explicada",
          f"{meta['pca']['total_explained']*100:.1f}%")

st.caption(f"Modelo entrenado: {meta['trained_at']}")

# --- Perfiles de cluster reinterpretados como clases de riesgo ---
cluster_profiles = meta["kmeans"].get("cluster_profiles")
if cluster_profiles:
    st.subheader("Clases de riesgo (perfiles de cluster)")
    st.caption(
        "Cada cluster se reinterpreta como una clase de riesgo actuarial según "
        "el promedio de edad y el volumen relativo de casos en su centroide. "
        "El número de cluster es arbitrario (puede variar entre entrenamientos); "
        "la etiqueta se recalcula siempre a partir del centroide, no del índice."
    )
    perfiles_df = pd.DataFrame([
        {"Cluster": cid, "Clase de riesgo": p["label"]}
        for cid, p in sorted(cluster_profiles.items(), key=lambda kv: int(kv[0]))
    ])
    st.dataframe(perfiles_df, use_container_width=True, hide_index=True)

# --- Predicción interactiva de cluster ---
st.subheader("Asignación a cluster — predicción interactiva")
st.caption(
    "Los valores ingresados son los que produce el ETL antes del PCA/KMeans "
    "(CIE-10 codificado, sexo 0/1, grupo de edad ordinal 0-4, año y cantidad "
    "ya escalados 0-1 por MinMaxScaler). La API aplica internamente el mismo "
    "StandardScaler usado en entrenamiento antes de predecir."
)
with st.form("ml_form"):
    cols = st.columns(5)
    cie = cols[0].number_input("CIE-10 (encoded)", value=10.0, step=1.0)
    sexo = cols[1].selectbox("Sexo (0=mujer, 1=varón)", [0, 1])
    edad = cols[2].selectbox("Grupo edad ordinal", [0, 1, 2, 3, 4])
    anio = cols[3].slider("Año (escalado 0–1)", 0.0, 1.0, 0.5, step=0.05)
    cantidad = cols[4].slider("Cantidad (escalada 0–1)", 0.0, 1.0, 0.3, step=0.05)
    submitted = st.form_submit_button("Predecir")

if submitted:
    payload = {
        "cie10_clasificacion": cie,
        "sexo": float(sexo),
        "grupo_edad": float(edad),
        "anio": anio,
        "cantidad": cantidad,
    }
    cluster = api_client.ml_cluster(payload)
    pca_res = api_client.ml_pca(payload)
    cluster_id = str(cluster["cluster"])
    risk_label = (cluster_profiles or {}).get(cluster_id, {}).get("label", f"Cluster {cluster_id}")
    st.success(f"Clase de riesgo asignada: **{risk_label}**")
    cc1, cc2, cc3 = st.columns(3)
    cc1.metric("Cluster (índice interno)", cluster["cluster"])
    cc2.metric("Distancia al centroide", cluster["distance_to_centroid"])
    cc3.metric("PCA (PC1 / PC2)",
               f"{pca_res['pc1']:.2f} / {pca_res['pc2']:.2f}")

st.divider()

# --- Distribuciones para contexto técnico ---
st.subheader("Distribución de defunciones por grupo de edad y sexo")
try:
    df_edad = pd.DataFrame(api_client.por_grupo_edad())
except Exception as exc:  # noqa: BLE001
    st.warning(f"No se pudo cargar distribución por edad: {exc}")
    df_edad = pd.DataFrame()

if not df_edad.empty:
    fig = px.bar(
        df_edad,
        x="grupo_edad",
        y="total",
        color="sexo",
        barmode="group",
        color_discrete_sequence=[PALETTE[0], PALETTE[2]],
    )
    fig.update_layout(xaxis_title="Grupo de edad", yaxis_title="Defunciones",
                     height=420)
    st.plotly_chart(fig, use_container_width=True)

with st.expander("📐 Loadings PCA (peso de cada variable en cada componente)"):
    loadings = meta["pca"].get("loadings")
    if loadings:
        loadings_data = {
            "feature": list(loadings.keys()),
            "PC1": [v[0] for v in loadings.values()],
            "PC2": [v[1] for v in loadings.values()],
        }
        st.dataframe(pd.DataFrame(loadings_data), use_container_width=True, hide_index=True)
    else:
        st.info(
            "Este modelo fue entrenado antes de que se guardaran los loadings. "
            "Vuelve a ejecutar `python -m etl.train_models` para regenerarlos."
        )
    st.caption(
        "Los componentes principales fueron ajustados sobre las features "
        f"{meta['features']}. Varianza explicada por componente: "
        f"{meta['pca']['explained_variance_ratio']}."
    )

st.divider()

# ============================================================
# 2. SUPERVISADO — Clasificación + Regresión
# ============================================================
st.header("2. Aprendizaje supervisado")

try:
    meta_sup = api_client.ml_metadata_supervisado()
except Exception as exc:  # noqa: BLE001
    meta_sup = None
    st.warning(
        f"El servicio de modelos supervisados no está disponible: {exc}\n\n"
        "Ejecuta `python -m etl.train_supervised_models` para entrenarlos."
    )

if meta_sup:
    st.caption(f"Modelos entrenados: {meta_sup['trained_at']}  ·  "
               f"{meta_sup['rows_train']:,} filas".replace(",", "."))

    clf_meta = meta_sup["clasificador_grupo_edad"]["metrics"]
    reg_meta = meta_sup["regresor_cantidad"]["metrics"]

    # --- 2.1 Clasificación ---
    st.subheader("2.1 Clasificación — grupo de edad")
    st.caption(
        f"Features: {', '.join(meta_sup['clasificador_grupo_edad']['features'])} "
        f"→ Target: {meta_sup['clasificador_grupo_edad']['target']} (5 clases) · Random Forest"
    )

    cf1, cf2, cf3 = st.columns(3)
    cf1.metric("Test Accuracy", clf_meta["test_accuracy"])
    cf2.metric("Test F1-macro", clf_meta["test_f1_macro"])
    cf3.metric("Mejores hiperparámetros", str(clf_meta["best_params"]))

    if "baseline_cv_f1_macro" in clf_meta:
        st.markdown("**Impacto del tuning (GridSearchCV) — F1-macro en validación cruzada:**")
        tuning_clf = pd.DataFrame({
            "Modelo": ["Random Forest (default)", "Random Forest (tuneado)"],
            "CV F1-macro": [clf_meta["baseline_cv_f1_macro"], clf_meta["cv_f1_macro"]],
        })
        fig_tune_clf = px.bar(
            tuning_clf, x="Modelo", y="CV F1-macro",
            color="Modelo", color_discrete_sequence=[PALETTE[5], PALETTE[0]],
            text="CV F1-macro",
        )
        fig_tune_clf.update_layout(showlegend=False, height=320, yaxis_range=[0, 1])
        st.plotly_chart(fig_tune_clf, use_container_width=True)
        st.caption(f"Mejora por tuning: {clf_meta['tuning_delta_f1_macro']:+.4f}")

    st.markdown("**Predicción interactiva**")
    try:
        causas_df = pd.DataFrame(api_client.top_causas(n=20))
        supracategorias = sorted(causas_df["supracategoria"].unique().tolist()) if not causas_df.empty else []
    except Exception:  # noqa: BLE001
        supracategorias = []

    with st.form("clf_form"):
        ccols = st.columns(4)
        supracat_clf = ccols[0].selectbox("Supracategoría (causa)", supracategorias) if supracategorias \
            else ccols[0].text_input("Supracategoría (causa)", value="Aparato circulatorio")
        sexo_clf = ccols[1].selectbox("Sexo", ["varon", "mujer"])
        anio_clf = ccols[2].slider("Año", 2005, 2022, 2020)
        cantidad_clf = ccols[3].number_input("Cantidad de casos de esa combinación", min_value=0, value=50)
        submitted_clf = st.form_submit_button("Predecir grupo de edad")

    if submitted_clf:
        try:
            res_clf = api_client.ml_predict_grupo_edad({
                "supracategoria": supracat_clf,
                "sexo": sexo_clf,
                "anio": anio_clf,
                "cantidad": cantidad_clf,
            })
            st.success(f"Grupo de edad más probable: **{res_clf['grupo_edad_predicho']}**")
            proba_df = pd.DataFrame(
                {"grupo_edad": list(res_clf["probabilidades"].keys()),
                 "probabilidad": list(res_clf["probabilidades"].values())}
            )
            proba_df["grupo_edad"] = pd.Categorical(proba_df["grupo_edad"], categories=ORDEN_EDAD, ordered=True)
            proba_df = proba_df.sort_values("grupo_edad")
            fig_proba = px.bar(proba_df, x="grupo_edad", y="probabilidad",
                                color_discrete_sequence=[PALETTE[0]])
            fig_proba.update_layout(height=320, yaxis_range=[0, 1],
                                     xaxis_title="Grupo de edad", yaxis_title="Probabilidad")
            st.plotly_chart(fig_proba, use_container_width=True)
        except Exception as exc:  # noqa: BLE001
            st.error(f"No se pudo predecir: {exc}")

    st.divider()

    # --- 2.2 Regresión ---
    st.subheader("2.2 Regresión — cantidad de defunciones esperada")
    st.caption(
        f"Features: {', '.join(meta_sup['regresor_cantidad']['features'])} "
        f"→ Target: {meta_sup['regresor_cantidad']['target']} (transformado con log1p) · Random Forest"
    )

    rf1, rf2, rf3 = st.columns(3)
    rf1.metric("Test R² (escala original)", reg_meta["test_r2_orig"])
    rf2.metric("Test MAE (escala original)", reg_meta["test_mae_orig"])
    rf3.metric("Mejores hiperparámetros", str(reg_meta["best_params"]))

    if "baseline_cv_r2_log" in reg_meta:
        st.markdown("**Impacto del tuning (GridSearchCV) — R² en validación cruzada (escala log):**")
        tuning_reg = pd.DataFrame({
            "Modelo": ["Random Forest (default)", "Random Forest (tuneado)"],
            "CV R² (log)": [reg_meta["baseline_cv_r2_log"], reg_meta["cv_r2_log"]],
        })
        fig_tune_reg = px.bar(
            tuning_reg, x="Modelo", y="CV R² (log)",
            color="Modelo", color_discrete_sequence=[PALETTE[5], PALETTE[0]],
            text="CV R² (log)",
        )
        fig_tune_reg.update_layout(showlegend=False, height=320)
        st.plotly_chart(fig_tune_reg, use_container_width=True)
        st.caption(f"Mejora por tuning: {reg_meta['tuning_delta_r2_log']:+.4f}")

    st.warning(
        f"⚠️ El R² de este modelo es bajo (~{reg_meta['test_r2_orig']:.2f}). Con solo 4 variables "
        "categóricas/temporales de baja cardinalidad, el modelo no puede explicar la variabilidad "
        "real de `cantidad`, que depende de la causa exacta (no solo su capítulo CIE-10). "
        "Útil como orden de magnitud, no como predicción precisa — ver sección "
        "'Lectura técnica' más abajo para más detalle."
    )

    st.markdown("**Predicción interactiva**")
    with st.form("reg_form"):
        rcols = st.columns(4)
        anio_reg = rcols[0].slider("Año ", 2005, 2022, 2020, key="anio_reg")
        sexo_reg = rcols[1].selectbox("Sexo ", ["varon", "mujer"], key="sexo_reg")
        edad_reg = rcols[2].selectbox("Grupo de edad", ORDEN_EDAD, key="edad_reg")
        supracat_reg = rcols[3].selectbox("Supracategoría (causa) ", supracategorias, key="supracat_reg") if supracategorias \
            else rcols[3].text_input("Supracategoría (causa) ", value="Aparato circulatorio", key="supracat_reg")
        submitted_reg = st.form_submit_button("Predecir cantidad esperada")

    if submitted_reg:
        try:
            res_reg = api_client.ml_predict_cantidad({
                "anio": anio_reg,
                "sexo": sexo_reg,
                "grupo_edad": edad_reg,
                "supracategoria": supracat_reg,
            })
            st.metric("Cantidad de defunciones estimada", f"{res_reg['cantidad_predicha']:.1f}")
        except Exception as exc:  # noqa: BLE001
            st.error(f"No se pudo predecir: {exc}")

    st.divider()

    with st.expander("📝 Lectura técnica — TODO: personalizar con tu propio análisis"):
        st.markdown(
            """
            *Este texto es un borrador inicial. Antes de la defensa, reemplázalo por tu propia
            interpretación — en la presentación individual te van a preguntar directamente por
            estas decisiones, así que conviene que el argumento sea genuinamente tuyo.*

            - **Clasificación de `grupo_edad`**: ¿qué tan bien separa el modelo las 5 categorías?
              ¿Qué grupo identifica mejor y por qué (pista: causas perinatales muy específicas
              del grupo 0-14)? ¿Dónde se concentra el error?
            - **Regresión de `cantidad`**: el R² es bajo — explica *por qué* en tus propias
              palabras (¿qué información le falta al modelo para predecir mejor? ¿qué variable
              agregarías si tuvieras más tiempo?).
            - **Hiperparámetros**: compara el gráfico de tuning de arriba. ¿La mejora fue grande
              o marginal? ¿Qué te dice eso sobre dónde está el cuello de botella del modelo —
              en la configuración del árbol o en las features disponibles?
            """
        )
