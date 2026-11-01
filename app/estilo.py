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


CSS = f"""<style>
html, body, [class*="css"], .stApp {{ font-family: {FUENTE}; }}
[data-testid="stDataFrame"] {{ font-variant-numeric: tabular-nums; }}
</style>"""


def aplicar_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
