"""Resumen ejecutivo (sección cliente, sin jerga estadística)."""
import streamlit as st

from app.estilo import fmt_es, fmt_pct
from app.layout import con_agente, encabezado
from src.config import COBERTURA_NOMINAL, ETIQUETAS
from src.negocio import CANTIDADES_EJEMPLO, budget
from src.pipeline import Resultados

NOMBRE = {"Equipo1": "Equipo 1", "Equipo2": "Equipo 2"}
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
SIMPLE = {"X": "el precio del petróleo (X)", "Y": "el precio del acero (Y)", "Z": "el precio del aluminio (Z)"}


def _mes(ts) -> str:
    return f"{MESES[ts.month - 1]} {ts.year}"


def _reserva_pct(res: Resultados) -> float:
    """Reserva / costo esperado del presupuesto de ejemplo."""
    b = budget(res.fans["base"], CANTIDADES_EJEMPLO)
    return float(b["reserva"].sum() / b["p50"].sum())


def _aciertos(res: Resultados, eq: str, h: int) -> int:
    """Veces de cada 10 que el rango contuvo el precio real en la historia, al horizonte más cercano a `h`."""
    c = res.cobertura[eq]
    return round(float(c.iloc[(c["horizonte"] - h).abs().argmin()]["cobertura"]) * 10)


def _frecuencia(h: int) -> str:
    return "cada trimestre" if h == 3 else f"cada {h} meses"


def render(res: Resultados) -> None:
    encabezado("resumen", "Costo esperado de cada equipo, reserva recomendada y hasta cuándo confiar en las cifras.")
    h = res.horizonte
    base = res.fans["base"]
    pal = {e: res.participacion[e].idxmax() for e in res.participacion}  # mayor parte del costo, no mayor peso
    escenarios = round(COBERTURA_NOMINAL * 10)

    cols = st.columns(len(base) + 1)
    for col, (eq, fan) in zip(cols, base.items()):
        f1 = fan.iloc[0]
        with col, st.container(border=True, key=f"eg_kpi_{eq}"):
            st.subheader(NOMBRE[eq])
            st.metric(f"Costo esperado, {_mes(fan.index[0])}", f"≈ {fmt_es(f1['p50'], 0)}")
            st.caption(f"Entre {fmt_es(f1['p10'], 0)} y {fmt_es(f1['p90'], 0)} en {escenarios} de cada 10 "
                       f"escenarios simulados. En la historia, a {h} meses, el rango contuvo el precio real "
                       f"cerca de {_aciertos(res, eq, h)} de cada 10 veces.")
            st.metric(f"Costo esperado, {_mes(fan.index[h - 1])}", f"≈ {fmt_es(fan.iloc[h - 1]['p50'], 0)}")
    with cols[-1], st.container(border=True, key="eg_kpi_reserva"):
        st.subheader("Reserva")
        st.metric("Reserva recomendada", fmt_pct(_reserva_pct(res), 0),
                  help="Sobre el presupuesto esperado de ejemplo (cantidades editables en Presupuesto y proveedores).")
        st.caption("Colchón sobre el presupuesto esperado para cubrir un escenario adverso.")

    st.header("Qué vigilar")
    for eq, m in pal.items():
        parte = res.participacion[eq][m]
        st.markdown(f"- **{NOMBRE[eq]}:** {SIMPLE[m]} explica ≈ {fmt_pct(parte, 1)} de su costo. "
                    f"Un alza de 10 % en ese precio sube el costo ≈ {fmt_es(parte * 10, 1)} %.")
    st.caption("La identificación de las materias primas (petróleo, acero, aluminio) es una hipótesis: "
               + "; ".join(ETIQUETAS.values()) + ".")

    st.header("Hasta cuándo confiar")
    st.info(f"Las cifras son firmes para los próximos **{h} meses**. Más allá son solo referenciales: sirven para "
            f"dimensionar el riesgo, no para comprometer un precio. Recomendamos actualizar el pronóstico "
            f"**{_frecuencia(h)}**.")


con_agente("resumen", render)
