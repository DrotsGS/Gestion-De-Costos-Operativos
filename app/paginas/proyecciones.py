"""Página 4: Proyecciones."""
import pandas as pd
import streamlit as st

from app.estilo import aplicar_css, fmt_es, fmt_pct, tema_actual, tokens
from app.graficos import fig_abanico, fig_x_oos
from app.layout import con_agente
from src.config import COBERTURA_NOMINAL, HORIZONTE_MAX_MAPE, HORIZONTE_MIN_COB
from src.pipeline import Resultados

NOMBRE = {"Equipo1": "Equipo 1", "Equipo2": "Equipo 2"}
ESCENARIO = {"base": "Base", "choque_2022": "Choque 2022"}
EXPLICA = {
    "base": "Escenario base: los precios futuros se simulan remuestreando la variación histórica de X, Y y Z.",
    "choque_2022": "Choque 2022: parte de la base y aplica un alza tipo 2022 (X +35 %, Y +25 %, Z +30 %) "
                   "para ver qué pasaría con otro episodio de estrés.",
}
UMBRAL_CERCA = 0.005  # 0,5 pp: diferencia de MAPE considerada equivalente
MODELOS = {"naive": "Caminata aleatoria", "sma3": "Promedio móvil 3 m", "arima": "ARIMA", "ets": "ETS"}


def _cobertura_en(res: Resultados, eq: str, h: int) -> float:
    c = res.cobertura[eq]
    return float(c.iloc[(c["horizonte"] - h).abs().argmin()]["cobertura"])


def _backtest(res: Resultados, eq: str) -> None:
    h = res.horizonte
    piv = res.backtest[eq].pivot(index="modelo", columns="horizonte", values="mape")
    piv.index = [MODELOS.get(m, m) for m in piv.index]
    cols = list(piv.columns)
    elegido = min(cols, key=lambda c: abs(c - h))
    texto = piv.map(fmt_pct).rename(columns=lambda c: f"{c} m")
    st.dataframe(texto.style.map(lambda _: f"font-weight: 700; background-color: {tokens(tema_actual())['resalte']}",
                                 subset=[f"{elegido} m"]), width="stretch")
    mejor = piv.idxmin()
    st.caption(f"MAPE (error porcentual medio) por modelo y horizonte; resaltado el horizonte confiable "
               f"({h} meses). Mejor modelo por horizonte: "
               + ", ".join(f"{c} m: {mejor[c]}" for c in cols) + ".")
    naive = MODELOS["naive"]
    cerca = [c for c in cols if piv.loc[naive, c] - piv[c].min() <= UMBRAL_CERCA]
    if len(cerca) == len(cols):
        rw = (f"ningún modelo supera de forma material a la caminata aleatoria (diferencia ≤ "
              f"{fmt_es(UMBRAL_CERCA * 100, 1)} pp en los {len(cols)} horizontes)")
    else:
        rw = (f"la caminata aleatoria queda a ≤ {fmt_es(UMBRAL_CERCA * 100, 1)} pp del mejor modelo en "
              f"{len(cerca)} de {len(cols)} horizontes")
    st.markdown(f"**Por qué {h} meses:** hasta {h} meses el error medio del mejor modelo es ≤ "
                f"{fmt_pct(HORIZONTE_MAX_MAPE, 0)} y los rangos aciertan ≥ {fmt_pct(HORIZONTE_MIN_COB, 0)}; "
                f"{rw}, por eso el pronóstico se apoya en simulación con rangos y no en un modelo puntual.")
    cob = res.cobertura[eq].copy()
    cob["Nominal"] = fmt_pct(COBERTURA_NOMINAL, 0)
    cob["Empírica"] = cob["cobertura"].map(lambda v: fmt_pct(v, 0))
    cob["Brecha"] = (cob["cobertura"] - COBERTURA_NOMINAL).map(lambda v: f"{fmt_es(v * 100, 0)} pp")
    st.markdown("**Cobertura del rango P10–P90** (qué tan seguido el costo real cayó dentro):")
    st.dataframe(cob.rename(columns={"horizonte": "Horizonte (m)"})[["Horizonte (m)", "Nominal", "Empírica", "Brecha"]],
                 hide_index=True, width="stretch")


def render(res: Resultados) -> None:
    aplicar_css()
    st.title("📈 Proyecciones")
    c1, c2, c3 = st.columns(3)
    eq = c1.segmented_control("Equipo", list(NOMBRE), format_func=NOMBRE.get, default="Equipo1",
                              key="proy_equipo") or "Equipo1"
    esc = c2.segmented_control("Escenario", list(ESCENARIO), format_func=ESCENARIO.get, default="base",
                               key="proy_esc") or "base"
    h = res.horizonte
    mes = c3.selectbox("Horizonte a detallar (meses)", range(1, 13), index=h - 1,
                       format_func=lambda m: f"{m}" + ("" if m <= h else " (referencial)"), key="proy_mes")
    st.caption(EXPLICA[esc])

    tema = tema_actual()
    fan = res.fans[esc][eq]
    tit = (f"El {NOMBRE[eq]} costaría ≈ {fmt_es(fan['p50'].iloc[h - 1], 0)} en {h} meses "
           f"(rango {fmt_es(fan['p10'].iloc[h - 1], 0)}–{fmt_es(fan['p90'].iloc[h - 1], 0)})")
    hist = res.monthly[eq].iloc[-24:]
    fig = fig_abanico(fan, h, tit, _cobertura_en(res, eq, h), nombre=NOMBRE[eq], tema=tema)
    fig.add_scatter(x=hist.index, y=hist.values, mode="lines", name="Histórico",
                    line=dict(color=tokens(tema)["tinta"], width=2), hoverinfo="skip")
    st.plotly_chart(fig, width="stretch")
    f = fan.iloc[mes - 1]
    marca = "" if mes <= h else " Mes referencial: más allá del horizonte confiable."
    st.metric(f"{NOMBRE[eq]}, mes {mes} ({fan.index[mes - 1]:%Y-%m})", fmt_es(f["p50"], 0),
              help="Mediana (P50) del costo simulado.")
    st.caption(f"Rango P10–P90: {fmt_es(f['p10'], 0)} a {fmt_es(f['p90'], 0)}; cobertura histórica del rango a "
               f"{mes} meses ≈ {fmt_pct(_cobertura_en(res, eq, mes), 0)} (nominal {fmt_pct(COBERTURA_NOMINAL, 0)}).{marca}")
    with st.expander("Ver tabla"):
        st.dataframe(pd.concat([hist.rename("Histórico"), fan.rename(columns=str.upper)], axis=1), width="stretch")

    st.subheader("Validación histórica")
    _backtest(res, eq)

    st.subheader("Prueba fuera de muestra con X")
    ox = res.x_oos
    k = int(ox["dentro"].sum())
    st.plotly_chart(fig_x_oos(ox, f"{k} de {len(ox)} meses reales de X cayeron dentro del rango P10–P90",
                              tema=tema), width="stretch")
    with st.expander("Ver tabla"):
        st.dataframe(ox.rename(columns={"real": "Real", "dentro": "Dentro del rango"}), width="stretch")


con_agente("proyecciones", render)
