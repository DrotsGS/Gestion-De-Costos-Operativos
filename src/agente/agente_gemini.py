"""Bucle del agente con Gemini (Google AI Studio, plan gratuito): mismo contrato que `agente.responder`."""
from google.genai import errors, types

from src.agente.agente import MAX_VUELTAS, SYSTEM, Respuesta
from src.agente.herramientas import TOOLS, ejecutar
from src.config import MODELO_GEMINI, MODELOS_GEMINI_RESPALDO
from src.pipeline import Resultados

# Gemini no usa web_search de Anthropic: la búsqueda es la herramienta propia buscar_noticias
SYSTEM_GEMINI = SYSTEM.replace("web_search", "buscar_noticias")

MAX_BUSQUEDAS = 2  # búsquedas de noticias por respuesta
ERR_SIN_BUSQUEDA = ("La búsqueda de noticias no está disponible (plan gratuito sin búsqueda en Google). "
                    "Responde con los resultados del modelo y avisa que no hay noticias.")
ERR_TOPE_BUSQUEDA = "Ya se hicieron las búsquedas permitidas. Responde con lo que ya tienes."

DESC_NOTICIAS = ("Busca en la web contexto de mercado o noticias recientes (p. ej. precio del petróleo, acero o "
                 "aluminio) y devuelve un resumen con sus fuentes.")


def _sin_adicionales(schema):
    """Quita additionalProperties del esquema JSON (campo que no se envía a Gemini)."""
    if isinstance(schema, dict):
        return {k: _sin_adicionales(v) for k, v in schema.items() if k != "additionalProperties"}
    return schema


def _declaraciones() -> list[types.FunctionDeclaration]:
    """Herramientas custom de `herramientas.TOOLS` (sin la de Anthropic) más buscar_noticias."""
    decl = [types.FunctionDeclaration(name=t["name"], description=t["description"],
                                      parameters_json_schema=_sin_adicionales(t["input_schema"]))
            for t in TOOLS if "input_schema" in t]
    decl.append(types.FunctionDeclaration(
        name="buscar_noticias", description=DESC_NOTICIAS,
        parameters_json_schema={"type": "object", "required": ["consulta"],
                                "properties": {"consulta": {"type": "string",
                                                            "description": "Qué buscar en la web."}}}))
    return decl


def _config() -> types.GenerateContentConfig:
    return types.GenerateContentConfig(
        system_instruction=SYSTEM_GEMINI,
        tools=[types.Tool(function_declarations=_declaraciones())],
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),  # bucle manual
    )


MENSAJES_ESTADO = {
    429: "No pude responder: se alcanzó el límite gratuito de consultas, intenta en un minuto.",
    401: "No pude autenticarme: la API key de Gemini es inválida.",
    403: "No pude usar el modelo: la API key de Gemini no tiene permiso.",
    404: "No pude responder: el modelo de Gemini no existe o ya no está disponible. Cambia MODELO_GEMINI por otro modelo Flash.",
}


def _mensaje_error(exc: Exception) -> str:
    if isinstance(exc, errors.APIError):
        texto = f"{exc.status or ''} {exc.message or ''}".lower()
        if exc.code == 429 or "resource_exhausted" in texto:
            return MENSAJES_ESTADO[429]
        if "api key" in texto or "api_key" in texto:  # Gemini devuelve 400 INVALID_ARGUMENT para keys malas
            return MENSAJES_ESTADO[401]
        if exc.code in MENSAJES_ESTADO:
            return MENSAJES_ESTADO[exc.code]
        if exc.code >= 500:
            return "No pude responder: el servicio no está disponible por ahora."
        return "No pude procesar la consulta (solicitud rechazada por la API)."
    nombre = type(exc).__name__.lower()
    if isinstance(exc, TimeoutError) or "timeout" in nombre:
        return "No pude conectarme a tiempo con el servicio. Intenta de nuevo."
    if isinstance(exc, OSError) or "connect" in nombre:
        return "No pude conectarme con el servicio. Revisa tu conexión e intenta de nuevo."
    return "No pude responder por un error inesperado."


def _partes(resp) -> list:
    """Partes del primer candidato (vacío si la respuesta fue bloqueada)."""
    cands = getattr(resp, "candidates", None) or []
    contenido = getattr(cands[0], "content", None) if cands else None
    return list(getattr(contenido, "parts", None) or [])


def _texto(partes) -> str:
    return "".join(p.text for p in partes if getattr(p, "text", None) and not getattr(p, "thought", None)).strip()


def _generar(client, modelo: str, contents, config):
    """generate_content con respaldo: ante 404 o 503 reintenta una vez con cada modelo de respaldo; ante
    timeout o error de conexión reintenta una vez el mismo modelo y luego los de respaldo.
    Devuelve (respuesta, modelo que respondió)."""
    candidatos = [modelo] + [m for m in MODELOS_GEMINI_RESPALDO if m != modelo]
    for i, m in enumerate(candidatos):
        for intento in range(2):
            try:
                return client.models.generate_content(model=m, contents=contents, config=config), m
            except errors.APIError as e:
                if e.code not in (404, 503) or i == len(candidatos) - 1:
                    raise
                break
            except Exception as e:  # noqa: BLE001 - solo se reintentan timeouts y conexión
                nombre = type(e).__name__.lower()
                transitorio = isinstance(e, (TimeoutError, OSError)) or "timeout" in nombre or "connect" in nombre
                if not transitorio:
                    raise
                if intento == 1 and i == len(candidatos) - 1:
                    raise


def _buscar_noticias(consulta, client, modelo: str = MODELO_GEMINI) -> dict:
    """Llamada aparte con solo Google Search: Gemini no permite mezclarlo con function calling."""
    if not isinstance(consulta, str) or not consulta.strip():
        return {"error": "Indica la consulta a buscar."}
    try:
        resp = client.models.generate_content(
            model=modelo, contents=consulta,
            config=types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())]))
    except Exception:  # noqa: BLE001 - sin búsqueda el agente igual responde
        return {"error": ERR_SIN_BUSQUEDA}
    cands = getattr(resp, "candidates", None) or []
    meta = getattr(cands[0], "grounding_metadata", None) if cands else None
    fuentes = []
    for ch in getattr(meta, "grounding_chunks", None) or []:
        web = getattr(ch, "web", None)
        if web and (web.uri or web.title):
            fuentes.append(f"{web.title} ({web.uri})" if web.title and web.uri else web.title or web.uri)
    resumen = _texto(_partes(resp))
    if not resumen:
        return {"error": "La búsqueda no devolvió resultados."}
    return {"resumen": resumen, "fuentes": fuentes}


def responder_gemini(historial: list[dict], pagina: str, res: Resultados, client) -> Respuesta:
    """Bucle de function calling manual con Gemini. `historial` es la lista cruda de Content (dicts
    serializables, append-only); su último elemento es la pregunta del usuario ({"role": "user",
    "content": texto} o con "parts"), a la que se antepone la página. Si el turno falla, la lista vuelve a
    su estado anterior a la pregunta. Nunca lanza excepción."""
    n0 = len(historial)
    ultimo = historial[-1]
    if isinstance(ultimo.get("content"), str):
        historial[-1] = {"role": "user", "parts": [{"text": f"[Página: {pagina}] {ultimo['content']}"}]}
    usadas: list[str] = []
    partes: list = []
    modelo = MODELO_GEMINI
    busquedas = 0

    def fallo(texto: str) -> Respuesta:
        del historial[n0 - 1:]  # descarta la pregunta fallida y los turnos parciales
        return Respuesta(texto, usadas, error=True, modelo=modelo)

    try:
        config = _config()
        for _ in range(MAX_VUELTAS):
            resp, modelo = _generar(client, modelo, [types.Content.model_validate(m) for m in historial], config)
            partes = _partes(resp)
            if not partes:
                return fallo("No puedo responder esa consulta.")
            historial.append(types.Content(role="model", parts=partes).model_dump(mode="json", exclude_none=True))
            llamadas = [p.function_call for p in partes if getattr(p, "function_call", None)]
            if not llamadas:
                break
            respuestas = []
            for fc in llamadas:
                usadas.append(fc.name)
                args = dict(fc.args or {})
                if fc.name == "buscar_noticias":
                    busquedas += 1
                    out = (_buscar_noticias(args.get("consulta"), client, modelo) if busquedas <= MAX_BUSQUEDAS
                           else {"error": ERR_TOPE_BUSQUEDA})
                else:
                    out = ejecutar(fc.name, args, res)
                respuestas.append(types.Part.from_function_response(name=fc.name, response=out))
            historial.append(types.Content(role="user", parts=respuestas).model_dump(mode="json", exclude_none=True))
        else:
            return fallo("No pude completar la consulta: se superó el máximo de pasos.")
    except Exception as e:  # noqa: BLE001 - el panel nunca debe romperse
        return fallo(_mensaje_error(e))
    texto = _texto(partes)
    if not texto:
        return fallo("No pude generar una respuesta. Reformula la pregunta.")
    return Respuesta(texto, usadas, modelo=modelo)
