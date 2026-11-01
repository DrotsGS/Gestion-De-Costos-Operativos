"""Punto de entrada de la app: navegación entre páginas."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st  # noqa: E402

st.set_page_config(page_title="Costos de equipos", page_icon="📋", layout="wide")

pagina = st.navigation([
    st.Page("paginas/resumen.py", title="Resumen ejecutivo", icon="📋", default=True),
    st.Page("paginas/calidad.py", title="Calidad de datos y trampas", icon="🔍"),
    st.Page("paginas/relacion.py", title="Qué mueve el precio", icon="🔗"),
    st.Page("paginas/proyecciones.py", title="Proyecciones", icon="📈"),
    st.Page("paginas/presupuesto.py", title="Presupuesto", icon="💰"),
    st.Page("paginas/arquitectura.py", title="Arquitectura y metodología", icon="🏗️"),
])
pagina.run()
