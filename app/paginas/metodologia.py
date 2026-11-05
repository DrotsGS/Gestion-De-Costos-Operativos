"""Metodología."""
import streamlit as st

from app.estilo import aplicar_css
from app.layout import con_agente
from src.contenido import IA_VS_AGENTE, SUPUESTOS
from src.pipeline import Resultados

FLUJO = [
    ("Carga y limpieza", "`src/utils.py`", "unifica formatos, fechas y decimales; corrige el atípico de Z y deja registro."),
    ("Auditoría", "`src/auditoria.py`", "detecta duplicados, saltos, tramos planos y el texto oculto; produce los hallazgos."),
    ("Relación materias → equipos", "`src/relacion.py`", "estima los pesos con regresión restringida, cointegración y ventanas móviles."),
    ("Pronóstico", "`src/pronostico.py`", "backtesting de modelos contra la caminata aleatoria y simulación Monte Carlo."),
    ("Negocio", "`src/negocio.py`", "traduce los abanicos a presupuesto, reserva y veredicto de cotización."),
    ("Orquestación", "`src/pipeline.py`", "ejecuta todo y entrega un único objeto de resultados."),
    ("App y agente", "`app/` y `src/agente/`", "muestran los resultados y permiten preguntar a Claude sobre ellos."),
]

LOCAL = r"""```bash
python -m venv .venv
source .venv/bin/activate     # en Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app/main.py
```
La app funciona sin clave: el agente muestra conversaciones de ejemplo. Para activarlo, define
`ANTHROPIC_API_KEY` en `.streamlit/secrets.toml` (`ANTHROPIC_API_KEY = "..."`) o como variable de entorno.
"""


def render(res: Resultados) -> None:
    aplicar_css()
    st.title("🏗️ Metodología")

    st.subheader("Flujo de la solución")
    st.markdown("\n".join(f"{i}. **{t}** — {m}: {d}" for i, (t, m, d) in enumerate(FLUJO, 1)))

    st.subheader("IA convencional frente a agente de IA")
    st.markdown(IA_VS_AGENTE)

    st.subheader("Supuestos clave")
    st.markdown("\n".join(f"- {s}" for s in SUPUESTOS))

    st.subheader("Cómo correrlo en local")
    st.markdown(LOCAL)


con_agente("metodologia", render)
