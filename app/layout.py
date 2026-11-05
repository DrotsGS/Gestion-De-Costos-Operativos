"""Piezas comunes de la app: resultados cacheados y diseño con panel del agente."""
import html
import json
import os
from collections.abc import Callable
from pathlib import Path

import streamlit as st

from src.agente.agente import responder
from src.agente.agente_gemini import responder_gemini
from src.config import MODELO_AGENTE, MODELO_GEMINI
from src.contenido import AGENTE_PANEL_INTRO, RASGOS_AGENTE
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
# id -> (sección sin ícono, título con ícono) para el encabezado de cada página
CABECERAS = {pid: (sec.split(" ", 1)[1], f"{icono} {titulo}")
             for sec, pags in SECCIONES.items() for pid, _, titulo, icono in pags}
EJEMPLOS = Path(__file__).resolve().parent / "ejemplos" / "conversaciones.json"
CLAVE_CHAT = "agente_chat"  # lista para mostrar
CLAVE_CRUDO = "agente_crudo"  # lista cruda para la API de Claude (append-only)
CLAVE_CRUDO_GEMINI = "agente_crudo_gemini"  # lista cruda para Gemini (formato distinto, no se mezcla)
ALTO_CHAT = 440  # alto fijo del historial: se desplaza dentro del panel
ALTO_CHAT_VACIO = 150  # alto del historial antes del primer mensaje (solo la pista)


def alto_chat(n_mensajes: int) -> int:
    """Alto del historial: pequeño sin mensajes, completo desde el primero."""
    return ALTO_CHAT if n_mensajes > 0 else ALTO_CHAT_VACIO


def html_encabezado(page_id: str, subtitulo: str) -> str:
    """HTML del encabezado: sección (eyebrow), título y una línea de subtítulo."""
    seccion, titulo = CABECERAS[page_id]
    e = html.escape
    return (f'<div class="eg-header"><div class="eg-eyebrow">{e(seccion)}</div>'
            f'<h1>{e(titulo)}</h1><p class="eg-sub">{e(subtitulo)}</p></div>')


def encabezado(page_id: str, subtitulo: str) -> None:
    st.markdown(html_encabezado(page_id, subtitulo), unsafe_allow_html=True)


def _borrar_chat() -> None:
    st.session_state[CLAVE_CHAT] = []
    st.session_state[CLAVE_CRUDO] = []
    st.session_state[CLAVE_CRUDO_GEMINI] = []


def _secreto(nombre: str) -> str | None:
    """Valor de un secreto: st.secrets primero (puede no existir el archivo) y luego el entorno."""
    try:
        valor = st.secrets[nombre]
    except Exception:  # sin archivo de secretos o sin la clave
        valor = None
    return valor or os.environ.get(nombre) or None


def elegir_proveedor() -> tuple[str, str] | None:
    """(proveedor, key): Gemini si hay key de Gemini, si no Claude; PROVEEDOR_AGENTE fuerza uno. None sin key."""
    keys = {"gemini": _secreto("GEMINI_API_KEY") or _secreto("GOOGLE_API_KEY"),
            "claude": _secreto("ANTHROPIC_API_KEY")}
    forzado = (_secreto("PROVEEDOR_AGENTE") or "").strip().lower()
    orden = [forzado] if forzado in keys else ["gemini", "claude"]
    for prov in orden:
        if keys[prov]:
            return prov, keys[prov]
    return None


def _crear_cliente(key: str):
    import anthropic
    return anthropic.Anthropic(api_key=key, max_retries=2, timeout=60.0)


def _crear_cliente_gemini(key: str):
    from google import genai
    from google.genai import types
    return genai.Client(api_key=key, http_options=types.HttpOptions(timeout=60_000))


def _chips(herramientas: list[str], modelo: str = "") -> None:
    iconos = {"web_search": "🔎", "buscar_noticias": "🔎"}
    chips = [f'{iconos.get(h, "🔧")} {h}' for h in dict.fromkeys(herramientas)]
    if modelo:
        chips.append(f"modelo: {modelo}")
    if chips:
        st.caption("".join(f'<span class="eg-chip">{html.escape(c)}</span>' for c in chips),
                   unsafe_allow_html=True)


def _que_hace() -> None:
    """Explicación compacta del agente: tarjetas apiladas, sin tablas (la columna es angosta)."""
    with st.expander("¿Qué hace este agente?"):
        st.markdown(AGENTE_PANEL_INTRO)
        st.markdown('<div class="eg-rasgos">' + "".join(
            f'<div class="eg-rasgo"><b>{html.escape(a)}</b>{html.escape(g)}</div>' for a, _, g in RASGOS_AGENTE)
            + "</div>", unsafe_allow_html=True)


def _mostrar(msg: dict) -> None:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant":
            _chips(msg.get("herramientas", []), msg.get("modelo", ""))


def _ejemplos_guardados() -> None:
    """Sin key: aviso y conversaciones de ejemplo guardadas."""
    st.info("Agente desactivado: falta una API key (GEMINI_API_KEY de Google AI Studio, gratuita, o "
            "ANTHROPIC_API_KEY, en secretos o en el entorno). Así se vería una conversación:")
    try:
        ejemplos = json.loads(EJEMPLOS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        ejemplos = []
    with st.container(height=alto_chat(len(ejemplos))):
        for ej in ejemplos:
            with st.chat_message("user"):
                st.markdown(ej["pregunta"])
            with st.chat_message("assistant"):
                st.markdown(ej["respuesta"])
                _chips(ej.get("herramientas", []))
                if ej.get("ilustrativo"):
                    st.caption("Ejemplo ilustrativo (aún no es una conversación real grabada).")


def panel_agente(page_id: str, res: Resultados) -> None:
    """Panel del agente (Gemini o Claude): conversación compartida entre páginas, con herramientas sobre los resultados."""
    with st.container(border=True, key="panel_agente"):
        st.subheader("🤖 Agente IA")
        _que_hace()
        elegido = elegir_proveedor()
        if not elegido:
            _ejemplos_guardados()
            return
        proveedor, key = elegido
        gemini = proveedor == "gemini"
        st.caption(f"Responde: Gemini ({MODELO_GEMINI})" if gemini else f"Responde: Claude ({MODELO_AGENTE})")
        chat = st.session_state.setdefault(CLAVE_CHAT, [])
        zona = st.container(height=alto_chat(len(chat)))  # historial con alto fijo; la entrada queda debajo
        pregunta = st.chat_input("Pregunta sobre los resultados…", key="agente_entrada")
        with zona:
            if not chat and not pregunta:
                st.caption("Pregunta sobre lo que ves en la página: cifras, escenarios o una cotización.")
            for m in chat:
                _mostrar(m)
            if pregunta:
                usuario = {"role": "user", "content": pregunta}
                _mostrar(usuario)
                with st.chat_message("assistant"):
                    with st.spinner("Pensando…"):
                        # mensajes tal como van a la API (una lista por proveedor)
                        crudo = st.session_state.setdefault(CLAVE_CRUDO_GEMINI if gemini else CLAVE_CRUDO, [])
                        crudo.append({"role": "user", "content": pregunta})
                        pagina = PAGINAS.get(page_id, page_id)
                        if gemini:
                            r = responder_gemini(crudo, pagina, res, _crear_cliente_gemini(key))
                        else:
                            r = responder(crudo, pagina, res, _crear_cliente(key))
                    st.markdown(r.texto)
                    _chips(r.herramientas_usadas, r.modelo)
                chat += [usuario, {"role": "assistant", "content": r.texto, "herramientas": r.herramientas_usadas,
                                   "error": r.error, "modelo": r.modelo}]
        if chat:
            st.button("Borrar conversación", key="agente_borrar", on_click=_borrar_chat, type="secondary",
                      width="stretch")


def con_agente(page_id: str, render: Callable[[Resultados], None]) -> None:
    """Contenido de la página a la izquierda y panel del agente a la derecha."""
    res = get_results()
    izq, der = st.columns([3, 1.3])
    with izq:
        render(res)
    with der:
        panel_agente(page_id, res)
