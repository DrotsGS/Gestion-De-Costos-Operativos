"""Tokens de diseño (claro/oscuro) y plantilla Plotly. Única fuente de colores y tipografía."""
import streamlit as st

FUENTE = 'system-ui, -apple-system, "Segoe UI", sans-serif'

TOKENS = {
    "light": {
        "superficie": "#fcfcfb", "tinta": "#0b0b0b", "tinta2": "#52514e", "muted": "#898781",
        "grid": "#e1e0d9", "eje": "#c3c2b7",
        "X": "#2a78d6", "Y": "#eb6834", "Z": "#1baf7a",
        "resalte": "rgba(42,120,214,0.18)", "banda_80": "#cde2fb", "banda_50": "#9ec5f4", "p50": "#2a78d6",
        "critical": "#d03b3b", "warning": "#fab219", "info": "#52514e",
    },
    "dark": {
        "superficie": "#1a1a19", "tinta": "#f0efec", "tinta2": "#c3c2b7", "muted": "#898781",
        "grid": "#2c2c2a", "eje": "#383835",
        "X": "#3987e5", "Y": "#d95926", "Z": "#199e70",
        "resalte": "rgba(57,135,229,0.30)", "banda_80": "#184f95", "banda_50": "#1c5cab", "p50": "#3987e5",
        "critical": "#d03b3b", "warning": "#fab219", "info": "#c3c2b7",
    },
}

# Estado: siempre ícono + texto (nunca solo color)
ESTADO = {
    "alta": ("🔴", "Severidad alta", "critical"),
    "media": ("🟡", "Severidad media", "warning"),
    "info": ("🔵", "Informativo", "info"),
}


def fmt_es(x: float, dec: int = 2) -> str:
    """Número con formato es-ES: miles con punto y decimales con coma."""
    return f"{x:,.{dec}f}".replace(",", "§").replace(".", ",").replace("§", ".")


def fmt_pct(x: float, dec: int = 1) -> str:
    """Fracción como porcentaje es-ES, p. ej. 0.8 -> '80,0 %'."""
    return f"{fmt_es(x * 100, dec)} %"


def tema_actual() -> str:
    """'light' o 'dark' según el tema de Streamlit (por defecto 'light')."""
    try:
        t = st.context.theme.type
    except Exception:  # fuera de una sesión o versión sin soporte
        return "light"
    return t if t in TOKENS else "light"


def tokens(tema: str = "light") -> dict[str, str]:
    return TOKENS.get(tema, TOKENS["light"])


def layout(tema: str = "light", titulo: str = "", altura: int = 420) -> dict:
    """Layout base de Plotly: superficie, tipografía, rejilla hairline sólida, formato es-ES."""
    t = tokens(tema)
    ejes = dict(gridcolor=t["grid"], gridwidth=1, griddash="solid", linecolor=t["eje"],
                zerolinecolor=t["eje"], tickfont=dict(color=t["muted"]), title_font=dict(color=t["tinta2"]))
    return dict(
        title=dict(text=titulo, font=dict(color=t["tinta"], size=17), x=0, xanchor="left"),
        paper_bgcolor=t["superficie"], plot_bgcolor=t["superficie"],
        font=dict(family=FUENTE, color=t["tinta2"]),
        xaxis=dict(**ejes), yaxis=dict(**ejes),
        legend=dict(font=dict(color=t["tinta2"]), orientation="h", y=-0.18),
        separators=",.", height=altura, margin=dict(t=70, l=50, r=30, b=60),
        hoverlabel=dict(font=dict(family=FUENTE)),
    )


def _rgba(hex_: str, alfa: float) -> str:
    h = hex_.lstrip("#")
    return f"rgba({int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)},{alfa})"


# Líneas y fondos derivados del muted (igual en claro y oscuro), así sirven en ambos temas
_MUTED = TOKENS["light"]["muted"]
_LINEA = _rgba(_MUTED, 0.32)
_SUAVE = _rgba(_MUTED, 0.08)

# Selectores data-testid: dependen de la estructura interna de Streamlit (revisar al actualizar)
CSS = f"""<style>
:root {{ --eg-muted: {_MUTED}; --eg-linea: {_LINEA}; --eg-suave: {_SUAVE}; }}
html, body, [class*="css"], .stApp {{ font-family: {FUENTE}; }}

/* Contenedor principal: ancho máximo y aire */
[data-testid="stMainBlockContainer"] {{ max-width: 1440px; padding-top: 4.25rem; padding-bottom: 3rem; }}
/* en escritorio las columnas no se ensanchan con su contenido (en móvil Streamlit las apila) */
@media (min-width: 641px) {{ [data-testid="stColumn"] {{ min-width: 0; }} }}
footer, [data-testid="stAppDeployButton"] {{ display: none !important; }}

/* Encabezado de página */
.eg-header {{ margin: 0 0 .5rem 0; }}
.eg-eyebrow {{ font-size: .72rem; font-weight: 600; letter-spacing: .09em; text-transform: uppercase;
  color: var(--eg-muted); margin-bottom: .2rem; }}
.eg-header h1 {{ font-size: 2rem; font-weight: 700; line-height: 1.2; padding: 0 0 .3rem 0; margin: 0; }}
.eg-sub {{ margin: 0; font-size: 1rem; line-height: 1.45; opacity: .78; }}

/* Ritmo vertical entre secciones (fuera de las tarjetas) */
[data-testid="stMainBlockContainer"] [data-testid="stHeading"] h2 {{ font-size: 1.55rem; padding-top: 1.4rem; }}
[data-testid="stMainBlockContainer"] [data-testid="stHeading"] h3 {{ font-size: 1.2rem; padding-top: .9rem; }}
[class*="st-key-eg_kpi"] [data-testid="stHeading"] h3 {{ padding-top: 0; font-size: 1.1rem; }}

/* Tarjetas KPI */
[class*="st-key-eg_kpi"] {{ border: 1px solid var(--eg-linea) !important; border-radius: .75rem;
  padding: 1rem 1.1rem; }}
[data-testid="stLayoutWrapper"]:has(> [class*="st-key-eg_kpi"]) {{ flex-grow: 1; }}  /* misma altura en la fila */
[data-testid="stMetricLabel"] p {{ font-size: .82rem; opacity: .8; }}
[data-testid="stMetricValue"] {{ font-size: 1.75rem; font-weight: 600; line-height: 1.2; }}

/* Tablas: el desborde se resuelve dentro de su contenedor, nunca en la página */
[data-testid="stDataFrame"] {{ font-variant-numeric: tabular-nums; max-width: 100%; }}
[data-testid="stMarkdownContainer"] table {{ display: block; overflow-x: auto; max-width: 100%;
  font-variant-numeric: tabular-nums; }}
[data-testid="stExpander"] details {{ border-color: var(--eg-linea); border-radius: .6rem; }}

/* Barra lateral: encabezados de sección */
[data-testid="stNavSectionHeader"] {{ font-size: .7rem; font-weight: 600; letter-spacing: .09em;
  text-transform: uppercase; color: var(--eg-muted); margin-top: .9rem; }}

/* Panel del agente */
.st-key-panel_agente [data-testid="stHeading"] h3 {{ padding-top: 0; font-size: 1.15rem; }}
.st-key-panel_agente [data-testid="stExpander"] p,
.st-key-panel_agente [data-testid="stAlert"] p {{ font-size: .88rem; line-height: 1.45; }}
.eg-rasgos {{ display: flex; flex-direction: column; gap: .4rem; margin: .4rem 0 .2rem 0; }}
.eg-rasgo {{ border: 1px solid var(--eg-linea); border-radius: .5rem; padding: .4rem .6rem;
  font-size: .84rem; line-height: 1.35; overflow-wrap: anywhere; }}
.eg-rasgo b {{ display: block; font-size: .68rem; font-weight: 600; letter-spacing: .08em;
  text-transform: uppercase; color: var(--eg-muted); }}
.eg-chip {{ display: inline-block; padding: .05rem .55rem; margin: .2rem .3rem 0 0; font-size: .72rem;
  line-height: 1.5; border: 1px solid var(--eg-linea); border-radius: 999px; background: var(--eg-suave);
  white-space: nowrap; }}

/* Mensajes del chat: todo queda dentro de la burbuja */
[data-testid="stChatMessage"] {{ padding: .45rem .2rem; gap: .5rem; }}
[data-testid="stChatMessageContent"] {{ min-width: 0; overflow-wrap: anywhere; word-break: break-word; }}
[data-testid="stChatMessage"] p, [data-testid="stChatMessage"] li {{ font-size: .9rem; line-height: 1.5; }}
[data-testid="stChatMessage"] table {{ display: block; overflow-x: auto; max-width: 100%; font-size: .8rem; }}
[data-testid="stChatMessage"] th, [data-testid="stChatMessage"] td {{ min-width: 5.5rem; padding: .25rem .5rem;
  word-break: normal; overflow-wrap: normal; }}  /* celdas legibles; la tabla se desplaza */
[data-testid="stChatMessage"] pre {{ white-space: pre-wrap; word-break: break-word; max-width: 100%; }}
[data-testid="stChatMessage"] code {{ white-space: pre-wrap; word-break: break-word; }}
[data-testid="stChatMessage"] img {{ max-width: 100%; }}

/* Pantallas angostas */
@media (max-width: 640px) {{
  [data-testid="stMainBlockContainer"] {{ padding-left: 1rem; padding-right: 1rem; padding-top: 3.75rem; }}
  .eg-header h1 {{ font-size: 1.6rem; }}
  [data-testid="stMetricValue"] {{ font-size: 1.5rem; }}
}}
</style>"""


def aplicar_css() -> None:
    """Inyecta el CSS de la app; se llama una sola vez por ejecución, desde main.py."""
    st.html(CSS)  # solo estilos: Streamlit lo envía al contenedor de eventos y no ocupa espacio
