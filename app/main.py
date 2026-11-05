"""Punto de entrada de la app: navegación entre páginas."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st  # noqa: E402

st.set_page_config(page_title="Costos de equipos", page_icon="📋", layout="wide")

from app.layout import SECCIONES  # noqa: E402

pagina = st.navigation({
    seccion: [st.Page(archivo, title=titulo, icon=icono, default=(pid == "resumen"))
              for pid, archivo, titulo, icono in paginas]
    for seccion, paginas in SECCIONES.items()
})
pagina.run()
