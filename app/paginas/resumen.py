"""Página 1: Resumen ejecutivo."""
import streamlit as st

from app.estilo import aplicar_css, fmt_es, fmt_pct
from app.layout import con_agente
from src.config import COBERTURA_NOMINAL, ETIQUETAS
from src.contenido import formula_texto
from src.pipeline import Resultados

NOMBRE = {"Equipo1": "Equipo 1", "Equipo2": "Equipo 2"}
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def _cobertura(res: Resultados, equipo: str, h: int) -> float:
    """Cobertura empírica del rango P10–P90 al horizonte disponible más cercano a `h`."""
    c = res.cobertura[equipo]
    return float(c.iloc[(c["horizonte"] - h).abs().argmin()]["cobertura"])


def _mes(ts) -> str:
    return f"{MESES[ts.month - 1]} {ts.year}"


def render(res: Resultados) -> None:
    aplicar_css()
    st.title("📋 Resumen ejecutivo")
    h = res.horizonte
    pal = {e: res.participacion[e].idxmax() for e in res.participacion}  # mayor parte del COSTO, no mayor peso
    st.markdown(
        "**Idea central:** el costo de cada equipo depende de una combinación de materias primas. "
        + " ".join(f"La palanca principal del {NOMBRE[e]} es **{ETIQUETAS[m]}** "
                   f"(≈ {fmt_pct(res.participacion[e][m], 0)} de su costo)." for e, m in pal.items())
        + " Los rangos se muestran como P10–P90: el costo debería caer dentro en la mayoría de los casos, no siempre."
    )

    base = res.fans["base"]
    for col, (eq, fan) in zip(st.columns(len(base)), base.items()):
        m1, mh = fan.iloc[0], fan.iloc[h - 1]
        reserva = (mh["p90"] - mh["p50"]) / mh["p50"]
        with col, st.container(border=True):
            st.subheader(NOMBRE[eq])
            st.metric(f"Costo esperado (P50), {_mes(fan.index[0])}", f"{fmt_es(m1['p50'], 0)}")
            st.caption(f"Rango P10–P90: {fmt_es(m1['p10'], 0)} a {fmt_es(m1['p90'], 0)}. En la validación histórica el "
                       f"rango contuvo el costo real el {fmt_pct(_cobertura(res, eq, 1), 0)} de las veces "
                       f"(nominal {fmt_pct(COBERTURA_NOMINAL, 0)}).")
            st.metric(f"Costo esperado (P50) a {h} meses, {_mes(fan.index[h - 1])}", f"{fmt_es(mh['p50'], 0)}")
            st.caption(f"Rango P10–P90: {fmt_es(mh['p10'], 0)} a {fmt_es(mh['p90'], 0)}. Cobertura histórica a {h} "
                       f"meses: {fmt_pct(_cobertura(res, eq, h), 0)} (nominal {fmt_pct(COBERTURA_NOMINAL, 0)}).")
            st.metric(f"Reserva sugerida a {h} meses", fmt_pct(reserva),
                      help="(P90 − P50) / P50: colchón sobre el costo esperado para cubrir un mes adverso.")
            st.markdown(f"**Fórmula:** {formula_texto(res.pesos[eq], res.participacion[eq])}")

    st.info(
        "Palanca principal = la materia con mayor parte del costo (peso × precio), no la de mayor peso: "
        + "; ".join(f"{NOMBRE[e]}: **{ETIQUETAS[m]}** (≈ {fmt_pct(res.participacion[e][m], 0)})" for e, m in pal.items())
        + f". Un alza en ella se traslada casi directo al costo. Más allá de {h} meses los pronósticos son "
        f"solo referenciales."
    )


con_agente("resumen", render)
