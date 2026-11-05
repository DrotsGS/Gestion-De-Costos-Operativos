"""Validación de modelos (sección análisis)."""
import streamlit as st

from app.estilo import fmt_es, fmt_pct, tema_actual, tokens
from app.graficos import fig_x_oos
from app.layout import con_agente, encabezado
from src.config import COBERTURA_NOMINAL, HORIZONTE_MAX_MAPE, HORIZONTE_MIN_COB
from src.pipeline import Resultados

NOMBRE = {"Equipo1": "Equipo 1", "Equipo2": "Equipo 2"}
UMBRAL_CERCA = 0.005  # 0,5 pp: diferencia de MAPE considerada equivalente
MODELOS = {"naive": "Caminata aleatoria", "sma3": "Promedio móvil 3 m", "arima": "ARIMA", "ets": "ETS"}


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


def _cobertura_texto() -> None:
    st.caption("La primera versión simulaba con distribución normal y la cobertura quedaba muy por debajo de la "
               "nominal; se eligió bootstrap por bloques.")


def render(res: Resultados) -> None:
    h = res.horizonte
    encabezado("validacion", f"Por qué confiamos en el pronóstico solo {h} meses.")
    eq = st.segmented_control("Equipo", list(NOMBRE), format_func=NOMBRE.get, default="Equipo1",
                              key="val_equipo") or "Equipo1"
    _backtest(res, eq)
    _cobertura_texto()

    st.subheader("Prueba fuera de muestra con X")
    ox = res.x_oos
    k = int(ox["dentro"].sum())
    st.plotly_chart(fig_x_oos(ox, f"{k} de {len(ox)} meses reales de X cayeron dentro del rango P10–P90",
                              tema=tema_actual()), width="stretch")
    with st.expander("Ver tabla"):
        st.dataframe(ox.rename(columns={"real": "Real", "dentro": "Dentro del rango"}), width="stretch")


con_agente("validacion", render)
