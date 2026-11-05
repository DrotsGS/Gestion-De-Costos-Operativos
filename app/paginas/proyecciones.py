"""Proyección de costos (sección cliente)."""
import pandas as pd
import streamlit as st

from app.estilo import aplicar_css, fmt_es, tema_actual, tokens
from app.graficos import fig_abanico
from app.layout import con_agente
from src.config import COBERTURA_NOMINAL
from src.pipeline import Resultados
from src.pronostico import ESCENARIOS

NOMBRE = {"Equipo1": "Equipo 1", "Equipo2": "Equipo 2"}
SIMPLE = {"X": "petróleo (X)", "Y": "acero (Y)", "Z": "aluminio (Z)"}
ESCENARIO = {"base": "Escenario normal", "choque_2022": "Escenario de crisis (tipo 2022)"}


def _explica(esc: str) -> str:
    if esc == "base":
        return "Los precios futuros se simulan con la variación histórica de las materias primas."
    ch = ESCENARIOS[esc]
    alzas = ", ".join(f"{SIMPLE[m]} +{fmt_es(v * 100, 0)} %" for m, v in ch.items())
    return f"Supone un alza como la de 2022 en las materias primas ({alzas}) sobre el escenario normal."


def render(res: Resultados) -> None:
    aplicar_css()
    st.title("📈 Proyección de costos")
    c1, c2 = st.columns(2)
    eq = c1.segmented_control("Equipo", list(NOMBRE), format_func=NOMBRE.get, default="Equipo1",
                              key="proy_equipo") or "Equipo1"
    esc = c2.segmented_control("Escenario", list(ESCENARIO), format_func=ESCENARIO.get, default="base",
                               key="proy_esc") or "base"
    st.caption(_explica(esc))

    h = res.horizonte
    tema = tema_actual()
    fan = res.fans[esc][eq]
    f1 = fan.iloc[0]
    n = round(COBERTURA_NOMINAL * 10)
    tit = (f"El {NOMBRE[eq]} costaría ≈ {fmt_es(fan['p50'].iloc[h - 1], 0)} en {h} meses "
           f"(entre {fmt_es(fan['p10'].iloc[h - 1], 0)} y {fmt_es(fan['p90'].iloc[h - 1], 0)})")
    hist = res.monthly[eq].iloc[-24:]
    fig = fig_abanico(fan, h, tit, nombre=NOMBRE[eq], tema=tema)
    fig.add_scatter(x=hist.index, y=hist.values, mode="lines", name="Histórico",
                    line=dict(color=tokens(tema)["tinta"], width=2), hoverinfo="skip")
    st.plotly_chart(fig, width="stretch")
    st.markdown(f"Lo más probable es que el {NOMBRE[eq]} cueste cerca de **{fmt_es(f1['p50'], 0)}**. "
                f"En {n} de cada 10 escenarios simulados queda entre **{fmt_es(f1['p10'], 0)}** y "
                f"**{fmt_es(f1['p90'], 0)}** el próximo mes.")
    st.caption(f"Zona confiable: los primeros {h} meses. Después las bandas se atenúan: son solo referenciales.")
    with st.expander("Ver tabla"):
        st.dataframe(pd.concat([hist.rename("Histórico"), fan.rename(columns=str.upper)], axis=1), width="stretch")


con_agente("proyecciones", render)
