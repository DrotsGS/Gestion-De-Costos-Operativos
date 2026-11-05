"""Bucle del agente: Claude con herramientas sobre los resultados del análisis (sin Streamlit)."""
import json
from dataclasses import dataclass, field

import anthropic

from src.agente.herramientas import TOOLS, ejecutar
from src.config import MODELO_AGENTE
from src.pipeline import Resultados

MAX_VUELTAS = 6

SYSTEM = """\
Eres un analista que explica a un evaluador los resultados de una app de costos de equipos de construcción \
(Equipo 1 y Equipo 2, que dependen de las materias primas X, Y y Z).

Contexto fijo:
- La fecha del caso es septiembre de 2023: los datos llegan hasta 2023-08 (X llega hasta 2024-04 y sirve \
solo para validar fuera de muestra).
- La identificación de X, Y y Z (petróleo Brent, acero, aluminio) es una hipótesis que no afecta al modelo; \
preséntala siempre como hipótesis.
- Tu mensaje de usuario indica la página de la app que el usuario está viendo: úsala para orientar la respuesta.

Reglas:
- Los "pesos" de la fórmula multiplican precios de escalas muy distintas: NO son porcentaje del costo. Para hablar de cuánto del costo explica una materia usa `participacion_costo` (parte del costo); nunca llames a los pesos "porcentaje del costo".
- Nunca inventes cifras: toda cifra del análisis debe salir de las herramientas \
(consultar_resultados, simular_escenario, evaluar_cotizacion). Si una herramienta devuelve un error, \
corrige los argumentos o explica el problema.
- Usa web_search solo para contexto de mercado o noticias, y cita la fuente.
- En páginas de la sección análisis, al hablar de rangos P10-P90 menciona la cobertura empírica (cercana al 70 %, menor a la nominal del 80 %) y distingue los meses confiables de los referenciales; responde con detalle técnico.
- En páginas de la sección cliente responde en lenguaje de negocio, sin jerga estadística (MAPE, p-valor, cobertura, VIF), salvo que el usuario la pida. Explica los rangos en palabras ("en la historia los rangos aciertan cerca de 7 de cada 10 veces, no 8") y distingue los meses confiables de los referenciales.
- Responde en español, breve, con conclusiones de negocio.
"""

MENSAJES_ERROR = [
    (anthropic.AuthenticationError, "No pude autenticarme: la API key es inválida."),
    (anthropic.PermissionDeniedError, "No pude usar el modelo: la API key no tiene permiso."),
    (anthropic.RateLimitError, "No pude responder: se alcanzó el límite de uso. Intenta en un minuto."),
    (anthropic.BadRequestError, "No pude procesar la consulta (solicitud rechazada por la API)."),
    (anthropic.APITimeoutError, "No pude conectarme a tiempo con el servicio. Intenta de nuevo."),
    (anthropic.APIConnectionError, "No pude conectarme con el servicio. Revisa tu conexión e intenta de nuevo."),
]


@dataclass
class Respuesta:
    texto: str
    herramientas_usadas: list[str] = field(default_factory=list)
    error: bool = False
    modelo: str = ""  # modelo que respondió (solo Gemini)


def _mensaje_error(exc: Exception) -> str:
    for tipo, msg in MENSAJES_ERROR:
        if isinstance(exc, tipo):
            return msg
    if isinstance(exc, anthropic.APIStatusError):
        if exc.status_code >= 500:
            return "No pude responder: el servicio no está disponible por ahora."
        if exc.status_code == 404:
            return "No pude responder: modelo no encontrado, revisa MODELO_AGENTE."
        return "No pude responder: la API devolvió un error."
    return "No pude responder por un error inesperado."


def _a_dict(b) -> dict:
    """Bloque de contenido como dict para guardarlo tal cual en el historial (también bloques de prueba)."""
    if hasattr(b, "model_dump"):
        return b.model_dump(exclude_none=True)
    return {k: v for k, v in vars(b).items() if v is not None}


def responder(historial: list[dict], pagina: str, res: Resultados, client) -> Respuesta:
    """Bucle de tool use manual. `historial` es la lista cruda de mensajes (append-only) y su último
    elemento es la nueva pregunta del usuario: se le antepone la página y la lista se extiende en
    el sitio con cada turno del asistente y cada tool_result. Si el turno falla, la lista vuelve
    a su estado anterior a la pregunta. Nunca lanza excepción."""
    n0 = len(historial)
    ultimo = historial[-1]
    if isinstance(ultimo.get("content"), str):
        historial[-1] = {**ultimo, "content": f"[Página: {pagina}] {ultimo['content']}"}
    usadas: list[str] = []
    resp = None

    def fallo(texto: str) -> Respuesta:
        del historial[n0 - 1:]  # descarta la pregunta fallida y los turnos parciales
        return Respuesta(texto, usadas, error=True)

    try:
        for _ in range(MAX_VUELTAS):
            resp = client.beta.messages.create(
                model=MODELO_AGENTE, max_tokens=16000, system=SYSTEM, tools=TOOLS, messages=historial,
                output_config={"effort": "medium"},
                betas=["server-side-fallback-2026-07-01"], fallbacks="default",
            )
            if resp.stop_reason == "refusal":
                return fallo("No puedo responder esa consulta.")
            historial.append({"role": "assistant", "content": [_a_dict(b) for b in resp.content]})
            llamadas = [b for b in resp.content if b.type == "tool_use"]
            usadas += [b.name for b in resp.content if b.type in ("tool_use", "server_tool_use")]
            if resp.stop_reason == "tool_use" and llamadas:
                resultados = []
                for b in llamadas:
                    out = ejecutar(b.name, b.input, res)
                    resultados.append({"type": "tool_result", "tool_use_id": b.id, "is_error": "error" in out,
                                       "content": json.dumps(out, ensure_ascii=False)})
                historial.append({"role": "user", "content": resultados})  # todos los resultados en un mensaje
                continue
            if resp.stop_reason == "pause_turn":  # el servidor pausó su bucle: se reanuda sin mensaje extra
                continue
            break
        else:
            return fallo("No pude completar la consulta: se superó el máximo de pasos.")
    except Exception as e:  # noqa: BLE001 - el panel nunca debe romperse
        return fallo(_mensaje_error(e))
    texto = "".join(b.text for b in resp.content if b.type == "text").strip()
    if not texto:
        return fallo("No pude generar una respuesta. Reformula la pregunta.")
    return Respuesta(texto, usadas)
