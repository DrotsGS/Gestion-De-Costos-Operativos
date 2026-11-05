"""Presupuesto y proveedores (sección cliente)."""
import pandas as pd
import streamlit as st

from app.estilo import fmt_es, tema_actual, tokens
from app.layout import con_agente, encabezado
from src.negocio import CANTIDADES_EJEMPLO, budget, evaluate_quote, validar_cantidades
from src.pipeline import Resultados

NOMBRE = {"Equipo1": "Equipo 1", "Equipo2": "Equipo 2"}


def _veredicto(fans: dict, tema: str) -> None:
    st.subheader("Verificador de cotizaciones")
    meses = [f"{d:%Y-%m}" for d in fans["Equipo1"].index]
    with st.form("cotizacion"):
        c1, c2, c3 = st.columns(3)
        eq = c1.selectbox("Equipo", list(NOMBRE), format_func=NOMBRE.get)
        mes = c2.selectbox("Mes", meses)
        precio = c3.number_input("Precio cotizado", min_value=0.0, value=0.0, step=10.0, format="%.2f")
        enviado = st.form_submit_button("Evaluar cotización")
    if not enviado:
        return
    v = evaluate_quote(fans, eq, mes, precio)
    if not v.ok:
        st.error(f"❌ {v.mensaje}")
        return
    # estado: ícono + texto + color
    if v.sobre_p90:
        icono, etiqueta, color = "🔴", "Sobre el P90: negociar", tokens(tema)["critical"]
    elif v.pct_vs_p50 > 0:
        icono, etiqueta, color = "🟡", "Sobre el P50, dentro del rango", tokens(tema)["warning"]
    else:
        icono, etiqueta, color = "🟢", "Cotización favorable", tokens(tema)["Z"]
    st.markdown(f"<div style='border-left:4px solid {color};padding:8px 12px'>"
                f"<b>{icono} {etiqueta}</b><br>{v.mensaje}</div>", unsafe_allow_html=True)
    st.caption(f"Precio justo (P50) de {NOMBRE[eq]} en {mes}: {fmt_es(v.precio_justo)}. El abanico es un costo "
               "promedio mensual; una compra puntual suma además ≈ 1,8 % de ruido diario.")


def render(res: Resultados) -> None:
    encabezado("presupuesto", "Presupuesto con reserva para cantidades de ejemplo y verificador de cotizaciones.")
    fans = res.fans["base"]
    meses = {f"{d:%Y-%m}" for d in fans["Equipo1"].index}
    st.markdown("Las cantidades son **de ejemplo** (el caso no las entrega): edítalas, agrega o quita filas. "
                "Usa meses en formato AAAA-MM dentro del pronóstico; el cálculo parte del escenario normal.")
    cant = st.data_editor(CANTIDADES_EJEMPLO, num_rows="dynamic", width="stretch", key="cantidades",
                          column_config={"Equipo1": st.column_config.NumberColumn("Equipo1", min_value=0),
                                         "Equipo2": st.column_config.NumberColumn("Equipo2", min_value=0)})
    errores = validar_cantidades(cant, meses)
    for e in errores:
        st.error(e)
    if not errores:
        try:
            b = budget(fans, cant)
        except ValueError as e:  # red de seguridad
            st.error(str(e))
        else:
            m1, m2, m3 = (c.container(border=True, key=f"eg_kpi_pres_{i}") for i, c in enumerate(st.columns(3)))
            m1.metric("Presupuesto esperado", fmt_es(b["p50"].sum(), 0), help="Σ cantidad × costo esperado.")
            m2.metric("Reserva", fmt_es(b["reserva"].sum(), 0),
                      help="Colchón para un escenario adverso: Σ cantidad × (P90 − P50).")
            m3.metric("Total a aprobar", fmt_es(b["total"].sum(), 0), help="Presupuesto esperado + reserva.")
            with st.expander("Ver tabla", expanded=True):
                st.dataframe(b.rename(columns={"p50": "Costo esperado (P50)", "reserva": "Reserva",
                                               "total": "Total"}).map(lambda v: fmt_es(v, 0))
                             .rename_axis("Fase"), width="stretch")
    _veredicto(fans, tema_actual())


con_agente("presupuesto", render)
