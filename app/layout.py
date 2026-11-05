"""Piezas comunes de la app: resultados cacheados y diseño con panel del agente."""
import json
import os
from collections.abc import Callable
from pathlib import Path

import streamlit as st

from src.agente.agente import responder
from src.contenido import IA_VS_AGENTE
from src.pipeline import Resultados, build_results


@st.cache_resource(show_spinner="Calculando modelos… (~40 s la primera vez)")
def get_results() -> Resultados:
    """Resultados del análisis completo, calculados una sola vez por proceso."""
    if os.environ.get("APP_RAPIDO") == "1":  # modo rápido para pruebas de humo
        return build_results(step=6, n_sims=300)
    return build_results()


# Navegación: sección -> páginas (id, archivo, título, ícono)
SECCIONES = {
    "🏢 Para el cliente": [
        ("resumen", "paginas/resumen.py", "Resumen ejecutivo", "📋"),
        ("proyecciones", "paginas/proyecciones.py", "Proyección de costos", "📈"),
        ("presupuesto", "paginas/presupuesto.py", "Presupuesto y proveedores", "💰"),
    ],
    "🔧 Detrás del análisis": [
        ("calidad", "paginas/calidad.py", "Datos y trampas", "🔍"),
        ("relacion", "paginas/relacion.py", "Qué mueve el precio", "🔗"),
        ("validacion", "paginas/validacion.py", "Validación de modelos", "✅"),
        ("metodologia", "paginas/metodologia.py", "Metodología", "🏗️"),
    ],
}
SECCION_CLIENTE = "🏢 Para el cliente"
# id -> "Título · sección cliente|análisis" (se antepone a la pregunta del agente)
PAGINAS = {pid: f"{titulo} · sección {'cliente' if sec == SECCION_CLIENTE else 'análisis'}"
           for sec, pags in SECCIONES.items() for pid, _, titulo, _ in pags}
EJEMPLOS = Path(__file__).resolve().parent / "ejemplos" / "conversaciones.json"
CLAVE_CHAT = "agente_chat"  # lista para mostrar
CLAVE_CRUDO = "agente_crudo"  # lista cruda para la API (append-only)


def _borrar_chat() -> None:
    st.session_state[CLAVE_CHAT] = []
    st.session_state[CLAVE_CRUDO] = []


def _api_key() -> str | None:
    """Key de Anthropic: st.secrets primero (puede no existir el archivo) y luego el entorno."""
    try:
        key = st.secrets["ANTHROPIC_API_KEY"]
    except Exception:  # sin archivo de secretos o sin la clave
        key = None
    return key or os.environ.get("ANTHROPIC_API_KEY") or None


def _crear_cliente(key: str):
    import anthropic
    return anthropic.Anthropic(api_key=key, max_retries=2, timeout=60.0)


def _chips(herramientas: list[str]) -> None:
    iconos = {"web_search": "🔎"}
    if herramientas:
        st.caption(" · ".join(f"{iconos.get(h, '🔧')} {h}" for h in dict.fromkeys(herramientas)))


def _mostrar(msg: dict) -> None:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant":
            _chips(msg.get("herramientas", []))


def _ejemplos_guardados() -> None:
    """Sin key: aviso y conversaciones de ejemplo guardadas."""
    st.info("Agente desactivado: falta la API key de Anthropic (ANTHROPIC_API_KEY en secretos o en el entorno). "
            "Así se vería una conversación:")
    try:
        ejemplos = json.loads(EJEMPLOS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        ejemplos = []
    for ej in ejemplos:
        with st.chat_message("user"):
            st.markdown(ej["pregunta"])
        with st.chat_message("assistant"):
            st.markdown(ej["respuesta"])
            _chips(ej.get("herramientas", []))
            if ej.get("ilustrativo"):
                st.caption("Ejemplo ilustrativo (aún no es una conversación real grabada).")


def panel_agente(page_id: str, res: Resultados) -> None:
    """Panel del agente Claude: conversación compartida entre páginas, con herramientas sobre los resultados."""
    with st.container(border=True):
        st.subheader("🤖 Agente IA")
        with st.expander("¿Qué hace este agente?"):
            st.markdown(IA_VS_AGENTE)
        key = _api_key()
        if not key:
            _ejemplos_guardados()
            return
        chat = st.session_state.setdefault(CLAVE_CHAT, [])
        zona = st.container()
        with zona:
            for m in chat:
                _mostrar(m)
        pregunta = st.chat_input("Pregunta sobre los resultados…", key="agente_entrada")
        if pregunta:
            usuario = {"role": "user", "content": pregunta}
            with zona:
                _mostrar(usuario)
                with st.chat_message("assistant"), st.spinner("Pensando…"):
                    crudo = st.session_state.setdefault(CLAVE_CRUDO, [])  # mensajes tal como van a la API
                    crudo.append({"role": "user", "content": pregunta})
                    r = responder(crudo, PAGINAS.get(page_id, page_id), res, _crear_cliente(key))
                chat += [usuario, {"role": "assistant", "content": r.texto, "herramientas": r.herramientas_usadas,
                                   "error": r.error}]
                _mostrar(chat[-1])
        if chat:
            st.button("Borrar conversación", key="agente_borrar", on_click=_borrar_chat)


def con_agente(page_id: str, render: Callable[[Resultados], None]) -> None:
    """Contenido de la página a la izquierda y panel del agente a la derecha."""
    res = get_results()
    izq, der = st.columns([3, 1.3])
    with izq:
        render(res)
    with der:
        panel_agente(page_id, res)
