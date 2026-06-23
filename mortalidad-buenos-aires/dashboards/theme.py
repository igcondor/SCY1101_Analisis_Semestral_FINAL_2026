"""Theming compartido entre páginas del dashboard."""
import streamlit as st

PRIMARY = "#0E4D92"   # Azul institucional
ACCENT = "#E63946"    # Rojo alerta
NEUTRAL = "#6C757D"

PALETTE = [
    "#0E4D92", "#1D7874", "#E63946", "#F4A261",
    "#2A9D8F", "#264653", "#9B5DE5", "#FFB703",
]


def set_page(title: str, icon: str = "📊") -> None:
    """Aplica config_page consistente a todas las vistas."""
    st.set_page_config(
        page_title=f"{title} · Mortalidad BA",
        page_icon=icon,
        layout="wide",
        initial_sidebar_state="expanded",
    )
