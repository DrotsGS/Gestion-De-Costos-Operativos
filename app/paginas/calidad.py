"""Página: Datos y trampas (sección análisis)."""
import pandas as pd
import streamlit as st

from app.estilo import ESTADO, fmt_es, tema_actual
from app.graficos import fig_serie_con_atipico
from app.layout import con_agente, encabezado
from src.contenido import TEXTO_OCULTO_RESUMEN, tabla_texto_oculto
from src.pipeline import Resultados

ORDEN = {"alta": 0, "media": 1, "info": 2}
ESTILO = {"alta": st.error, "media": st.warning, "info": st.info}
NOMBRES_COL = {"aspecto": "Aspecto", "dice_texto_oculto": "Dice el texto oculto",
               "muestran_datos": "Muestran los datos"}


def _grafico_z(res: Resultados) -> None:
    corr = res.clean.correcciones
    corr_z = corr[corr["serie"] == "Z"]
    if not len(corr_z):
        return
    fila = corr_z.iloc[0]
    fecha = pd.Timestamp(fila["date"])
    cruda, limpia = res.z_crudo, res.clean.daily["Z"]
    if fecha not in cruda.index or fecha not in limpia.index:
        st.caption(f"No se puede graficar la corrección de Z del {fecha:%Y-%m-%d}: fecha fuera de la serie.")
        return
    ini, fin = fecha - pd.Timedelta(days=45), fecha + pd.Timedelta(days=45)
    c, z = cruda.loc[ini:fin], limpia.loc[ini:fin]
    titulo = (f"Z el {fecha:%Y-%m-%d}: {fmt_es(fila['original'])} → {fmt_es(fila['corregido'])} "
              f"({fila['regla']}), corregido por interpolación")
    st.plotly_chart(fig_serie_con_atipico(c, z, fecha, "Z", tema=tema_actual(), titulo=titulo), width="stretch")
    with st.expander("Ver tabla"):
        st.dataframe(pd.DataFrame({"Z original": c, "Z corregido": z}), width="stretch")


def _tarjeta(h, res: Resultados) -> None:
    icono, etiqueta, _ = ESTADO[h.severidad]  # estado siempre con ícono + texto
    ESTILO[h.severidad](f"**{h.titulo}** · {etiqueta}\n\n{h.detalle}", icon=icono)
    if h.id == "texto_oculto_pdf":
        st.markdown(TEXTO_OCULTO_RESUMEN)
        st.dataframe(tabla_texto_oculto(res.pesos, res.participacion).rename(columns=NOMBRES_COL), hide_index=True,
                     width="stretch")
    elif h.id == "atipico_z":
        _grafico_z(res)
    elif h.id == "tramos_planos_y" and h.evidencia is not None and len(h.evidencia):
        ev = h.evidencia.rename(columns={"inicio": "Inicio", "fin": "Fin", "largo": "Días", "valor": "Valor"})
        st.dataframe(ev, hide_index=True, width="stretch")
    elif h.evidencia is not None and len(h.evidencia):
        with st.expander("Ver evidencia"):
            st.dataframe(h.evidencia.astype(str) if h.id == "integridad" else h.evidencia, hide_index=True, width="stretch")


def render(res: Resultados) -> None:
    encabezado("calidad", "Hallazgos de la auditoría, de mayor a menor severidad.")
    for h in sorted(res.hallazgos, key=lambda x: ORDEN[x.severidad]):
        _tarjeta(h, res)


con_agente("calidad", render)
