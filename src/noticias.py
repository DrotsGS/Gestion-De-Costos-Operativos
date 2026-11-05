"""Noticias de mercado gratis vía RSS de Google News (sin key, sin Streamlit)."""
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

URL = "https://news.google.com/rss/search?q={q}&hl=es-419&gl=CO&ceid=CO:es-419"
FUENTE = "Google News (RSS)"
TTL_SEGUNDOS = 600  # misma consulta en 10 minutos reutiliza el resultado
MAX_ITEMS = 8

_cache: dict[tuple, tuple[float, dict]] = {}


def _fetch_http(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:  # noqa: S310 - URL fija de Google News
        return r.read()


def _limpiar_titulo(titulo: str, fuente: str) -> str:
    """Quita el sufijo ' - Fuente' que Google agrega al título cuando repite la fuente."""
    sufijo = f" - {fuente}"
    if fuente and titulo.endswith(sufijo):
        return titulo[: -len(sufijo)].rstrip()
    return titulo


def _fecha_iso(texto: str) -> str:
    try:
        return parsedate_to_datetime(texto).date().isoformat()
    except (TypeError, ValueError):
        return ""


def _parsear(xml: bytes | str) -> list[dict]:
    raiz = ET.fromstring(xml)
    out = []
    for it in raiz.iter("item"):
        fuente = (it.findtext("source") or "").strip()
        titulo = _limpiar_titulo((it.findtext("title") or "").strip(), fuente)
        if not titulo:
            continue
        out.append({"titulo": titulo, "fuente": fuente, "fecha": _fecha_iso(it.findtext("pubDate") or ""),
                    "enlace": (it.findtext("link") or "").strip()})
    out.sort(key=lambda n: n["fecha"], reverse=True)
    return out


def buscar_noticias(consulta: str, max_items: int = 5, fetch=None) -> dict:
    """Titulares recientes de Google News para la consulta. Nunca lanza: ante fallo devuelve {"error": ...}."""
    if not isinstance(consulta, str) or not consulta.strip():
        return {"error": "Indica la consulta a buscar."}
    consulta = consulta.strip()
    try:
        n = max(1, min(MAX_ITEMS, int(max_items)))
    except (TypeError, ValueError):
        n = 5
    clave = (consulta.lower(), n)
    hit = _cache.get(clave)
    if hit and time.monotonic() - hit[0] < TTL_SEGUNDOS:
        return hit[1]
    try:
        xml = (fetch or _fetch_http)(URL.format(q=urllib.parse.quote_plus(consulta)))
        noticias = _parsear(xml)[:n]
    except Exception as e:  # noqa: BLE001 - red o XML inválido: el agente sigue sin noticias
        return {"error": f"No se pudieron obtener noticias ({type(e).__name__})."}
    out = {"consulta": consulta, "noticias": noticias, "fuente": FUENTE}
    _cache[clave] = (time.monotonic(), out)
    return out
