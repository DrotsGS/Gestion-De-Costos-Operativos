"""Página 3: Qué mueve el precio."""
import pandas as pd
import streamlit as st

from app.estilo import aplicar_css, fmt_es, fmt_pct, tema_actual
from app.graficos import fig_pesos, fig_pesos_moviles
from app.layout import con_agente
from src.config import ETIQUETAS, MATERIAS
from src.contenido import HIPOTESIS_MATERIAS, NOTA_HIPOTESIS, NOTA_PESOS_VS_COSTO, formula_texto
from src.pipeline import Resultados

UMBRAL_ESTABLE = 0.15  # variación máxima de un peso entre ventanas para llamarlo estable
NOMBRE = {"Equipo1": "Equipo 1", "Equipo2": "Equipo 2"}


def _tabla_correlacion(res: Resultados, eq: str) -> pd.DataFrame:
    corr = res.monthly[list(MATERIAS)].corrwith(res.monthly[eq])
    return pd.DataFrame({"Materia prima": [ETIQUETAS[m] for m in MATERIAS],
                         "Correlación en niveles": [fmt_es(corr[m]) for m in MATERIAS],
                         "Peso de la fórmula": [fmt_pct(res.pesos[eq][m]) for m in MATERIAS],
                         "Parte del costo": [fmt_pct(res.participacion[eq][m]) for m in MATERIAS]})


def _ols(res: Resultados, eq: str) -> None:
    o = res.ols[eq]
    tabla = pd.DataFrame({
        "Coeficiente": [fmt_es(o["coef"][k], 4) for k in o["coef"].index],
        "p-valor": [f"{o['pvalues'][k]:.2e}".replace(".", ",") for k in o["coef"].index],
        "VIF": [fmt_es(o["vif"][k]) if k in o["vif"].index else "—" for k in o["coef"].index],
    }, index=["Constante" if k == "const" else ETIQUETAS[k] for k in o["coef"].index])
    st.dataframe(tabla, width="stretch")
    signif = [m for m in MATERIAS if o["pvalues"][m] < 0.05]
    ruido = [m for m in MATERIAS if m not in signif]
    lectura = f"Solo {', '.join(ETIQUETAS[m] for m in signif)} aportan información al costo (p < 0,05)"
    if ruido:
        lectura += f"; {', '.join(ETIQUETAS[m] for m in ruido)} no añade{'n' if len(ruido) > 1 else ''} nada una vez considerado el resto"
    st.caption(f"{lectura}. R² = {fmt_es(o['r2'], 4)}. VIF alto (> 5) indicaría materias que se "
               "mueven juntas y confunden la regresión.")


def render(res: Resultados) -> None:
    aplicar_css()
    st.title("🔗 Qué mueve el precio")
    eq = st.segmented_control("Equipo", list(NOMBRE), format_func=NOMBRE.get, default="Equipo1",
                              key="rel_equipo") or "Equipo1"
    tema = tema_actual()
    w = res.pesos[eq]
    part = res.participacion[eq]
    pal = part.idxmax()

    titulo = f"{ETIQUETAS[pal]} explica ≈{fmt_pct(part[pal], 0)} del costo del {NOMBRE[eq]}"
    st.plotly_chart(fig_pesos(part, titulo, tema=tema, eje="Parte del costo"), width="stretch")
    st.markdown(f"**Fórmula:** {formula_texto(w, part)}")
    st.info(NOTA_PESOS_VS_COSTO)
    with st.expander("Ver tabla"):
        st.dataframe(pd.DataFrame({"Materia prima": [ETIQUETAS[m] for m in w.index],
                                   "Peso de la fórmula (por unidad de precio)": [fmt_pct(v) for v in w.values],
                                   "Parte del costo": [fmt_pct(v) for v in part.values]}),
                     hide_index=True, width="stretch")

    st.subheader("Por qué la correlación engaña")
    st.markdown("Dos materias que suben y bajan juntas se parecen al equipo aunque no lo muevan: la "
                "correlación en niveles no separa causa de coincidencia. El peso de la fórmula sí lo hace.")
    st.dataframe(_tabla_correlacion(res, eq), hide_index=True, width="stretch")
    corr = res.monthly[list(MATERIAS)].corrwith(res.monthly[eq])
    eng = [m for m in MATERIAS if abs(corr[m]) >= 0.5 and res.pesos[eq][m] < 0.05]
    if eng:
        m = max(eng, key=lambda k: abs(corr[k]))
        st.warning(f"**{ETIQUETAS[m]}** tiene correlación {fmt_es(corr[m])} con el {NOMBRE[eq]}, pero su peso "
                   f"de la fórmula es {fmt_pct(res.pesos[eq][m])}: se mueve con el costo por coincidencia, no lo causa.",
                   icon="⚠️")

    st.subheader("Regresión OLS")
    _ols(res, eq)

    p = res.cointegracion[eq]["pvalue"]
    conclusion = ("la combinación de materias primas y el costo se mueven juntos a largo plazo "
                  "(cointegración), por lo que la relación no es espuria") if p < 0.05 else (
        "no hay evidencia de relación estable a largo plazo: la fórmula podría ser espuria")
    st.metric("p-valor de cointegración (Engle-Granger)", f"{p:.2e}".replace(".", ","))
    st.caption(f"Con p {'<' if p < 0.05 else '≥'} 0,05, {conclusion}.")

    roll = res.rolling[eq]
    ini, fin = roll.iloc[0], roll.iloc[-1]
    est = float((roll.max() - roll.min()).max()) < UMBRAL_ESTABLE
    tit = (f"Los pesos del {NOMBRE[eq]} se mantienen estables en ventanas de 36 meses" if est
           else f"Los pesos del {NOMBRE[eq]} cambian entre ventanas de 36 meses")
    st.plotly_chart(fig_pesos_moviles(roll, tit, tema=tema), width="stretch")
    with st.expander("Ver tabla"):
        st.dataframe(roll.map(fmt_pct).rename_axis("Mes final de ventana"), width="stretch")
    st.caption(f"Primera ventana: {', '.join(f'{m} {fmt_pct(ini[m], 0)}' for m in roll.columns)}. "
               f"Última: {', '.join(f'{m} {fmt_pct(fin[m], 0)}' for m in roll.columns)}.")

    with st.expander("Investigación propia: ¿qué son X, Y y Z?"):
        h = HIPOTESIS_MATERIAS.copy()
        h["serie"] = h["serie"].map(ETIQUETAS)
        st.dataframe(h.rename(columns={"serie": "Serie", "hipotesis": "Hipótesis", "confianza": "Confianza",
                                       "evidencia": "Evidencia"}), hide_index=True, width="stretch")
        st.info(NOTA_HIPOTESIS)


con_agente("relacion", render)
