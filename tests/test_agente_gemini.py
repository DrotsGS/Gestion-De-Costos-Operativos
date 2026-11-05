"""Pruebas del agente Gemini con un cliente falso que devuelve objetos reales del SDK (nunca la API real)."""
import json

import pytest
from google.genai import errors, types
from streamlit.testing.v1 import AppTest

from src.agente import agente_gemini as mod
from src.agente.agente_gemini import responder_gemini
from src.config import MODELO_GEMINI, MODELOS_GEMINI_RESPALDO, ROOT
from src.pipeline import build_results

MAIN = str(ROOT / "app" / "main.py")


@pytest.fixture(scope="module")
def res():
    return build_results(step=6, n_sims=300)


def resp(*partes, grounding=None):
    return types.GenerateContentResponse(candidates=[types.Candidate(
        content=types.Content(role="model", parts=list(partes)), grounding_metadata=grounding)])


def llamada(nombre, args, firma=None):
    return types.Part(function_call=types.FunctionCall(name=nombre, args=args), thought_signature=firma)


def texto(t):
    return types.Part(text=t)


class FakeGeminiClient:
    """Imita client.models.generate_content: devuelve (o lanza) lo guardado, en orden."""

    def __init__(self, respuestas=(), raises=None, falla_modelo=None):
        self.respuestas = list(respuestas)
        self.raises = raises
        self.falla_modelo = falla_modelo or {}  # modelo -> excepción solo para ese modelo
        self.llamadas = []
        self.models = type("M", (), {"generate_content": self._gen})()

    def _gen(self, *, model, contents, config=None):
        if isinstance(contents, list):  # copia serializada: así se ve lo que se envió en ese momento
            contents = [c.model_dump(mode="json", exclude_none=True) for c in contents]
        self.llamadas.append({"model": model, "config": config, "contents": contents})
        if model in self.falla_modelo:
            raise self.falla_modelo[model]
        if self.raises:
            raise self.raises
        return self.respuestas.pop(0)


def err429():
    return errors.ClientError(429, {"error": {"code": 429, "message": "quota", "status": "RESOURCE_EXHAUSTED"}})


def test_declaraciones_desde_tools():
    decl = {d.name: d for d in mod._declaraciones()}
    assert list(decl) == ["consultar_resultados", "simular_escenario", "evaluar_cotizacion", "buscar_noticias"]
    dump = json.dumps(decl["simular_escenario"].parameters_json_schema)
    assert "additionalProperties" not in dump and "shocks" in dump
    cfg = mod._config()
    assert cfg.automatic_function_calling.disable is True and "buscar_noticias" in cfg.system_instruction
    assert "web_search" not in cfg.system_instruction


def test_usa_herramienta_y_responde(res):
    client = FakeGeminiClient([resp(llamada("consultar_resultados", {"tema": "formula", "equipo": "Equipo1"})),
                               resp(texto("Equipo 1 depende de Y"))])
    r = responder_gemini([{"role": "user", "content": "¿De qué depende el Equipo 1?"}], "relacion", res, client)
    assert r.herramientas_usadas == ["consultar_resultados"] and not r.error and r.texto == "Equipo 1 depende de Y"
    primera, segunda = client.llamadas
    assert primera["contents"][0]["parts"][0]["text"].startswith("[Página: relacion]")
    assert primera["config"].automatic_function_calling.disable is True
    fr = segunda["contents"][-1]["parts"][0]["function_response"]
    assert segunda["contents"][-1]["role"] == "user" and fr["name"] == "consultar_resultados"
    assert "Equipo1" in fr["response"]


def test_buscar_noticias_rss(res, monkeypatch):
    vistas = []

    def falso(consulta, max_items=5):
        vistas.append((consulta, max_items))
        return {"consulta": consulta, "noticias": [{"titulo": "Acero sube", "fuente": "Reuters",
                                                    "fecha": "2023-01-04", "enlace": "http://a"}],
                "fuente": "Google News (RSS)"}
    monkeypatch.setattr("src.agente.herramientas.buscar_noticias", falso)
    client = FakeGeminiClient([resp(llamada("buscar_noticias", {"consulta": "precio del acero"})),
                               resp(texto("Según Reuters (2023-01-04), sube."))])
    r = responder_gemini([{"role": "user", "content": "noticias"}], "resumen", res, client)
    assert r.herramientas_usadas == ["buscar_noticias"] and not r.error and vistas == [("precio del acero", 5)]
    fr = client.llamadas[1]["contents"][-1]["parts"][0]["function_response"]["response"]
    assert fr["noticias"][0]["titulo"] == "Acero sube" and fr["fuente"] == "Google News (RSS)"
    assert len(client.llamadas) == 2  # sin llamada aparte de búsqueda


def err(codigo, estado):
    return errors.ClientError(codigo, {"error": {"code": codigo, "message": "x", "status": estado}})         if codigo < 500 else errors.ServerError(codigo, {"error": {"code": codigo, "message": "x", "status": estado}})


@pytest.mark.parametrize("codigo,estado", [(404, "NOT_FOUND"), (503, "UNAVAILABLE")])
def test_respaldo_ante_404_o_503(res, codigo, estado):
    principal, respaldo = MODELO_GEMINI, MODELOS_GEMINI_RESPALDO[0]
    client = FakeGeminiClient([resp(texto("hola"))], falla_modelo={principal: err(codigo, estado)})
    r = responder_gemini([{"role": "user", "content": "x"}], "p", res, client)
    assert not r.error and r.texto == "hola" and r.modelo == respaldo
    assert [c["model"] for c in client.llamadas] == [principal, respaldo]


def test_reintenta_timeout_en_el_mismo_modelo(res):
    client = FakeGeminiClient([resp(texto("hola"))])
    original = client._gen
    fallos = [TimeoutError("lento")]

    def gen(*, model, contents, config=None):
        if fallos:
            client.llamadas.append({"model": model})
            raise fallos.pop()
        return original(model=model, contents=contents, config=config)
    client.models = type("M", (), {"generate_content": staticmethod(gen)})()
    r = responder_gemini([{"role": "user", "content": "x"}], "p", res, client)
    assert not r.error and r.texto == "hola" and r.modelo == MODELO_GEMINI
    assert [c["model"] for c in client.llamadas] == [MODELO_GEMINI, MODELO_GEMINI]


def test_timeout_persistente_prueba_respaldo_y_falla(res):
    client = FakeGeminiClient(raises=TimeoutError("lento"))
    r = responder_gemini([{"role": "user", "content": "x"}], "p", res, client)
    assert r.error and "a tiempo" in r.texto
    assert len(client.llamadas) == 2 * (1 + len(MODELOS_GEMINI_RESPALDO))


def test_sin_respaldo_si_todos_fallan(res):
    client = FakeGeminiClient(raises=err(404, "NOT_FOUND"))
    r = responder_gemini([{"role": "user", "content": "x"}], "p", res, client)
    assert r.error and "MODELO_GEMINI" in r.texto
    assert len(client.llamadas) == 1 + len(MODELOS_GEMINI_RESPALDO)


def test_tope_de_busquedas(res, monkeypatch):
    llamadas = []
    monkeypatch.setattr("src.agente.herramientas.buscar_noticias",
                        lambda c, m=5: llamadas.append(c) or {"consulta": c, "noticias": [], "fuente": "x"})
    pasos = [resp(llamada("buscar_noticias", {"consulta": "acero"}))] * 3 + [resp(texto("Listo."))]
    client = FakeGeminiClient(pasos)
    r = responder_gemini([{"role": "user", "content": "noticias"}], "p", res, client)
    assert not r.error and r.texto == "Listo." and r.herramientas_usadas == ["buscar_noticias"] * 3
    assert len(llamadas) == mod.MAX_BUSQUEDAS
    fr = client.llamadas[-1]["contents"][-1]["parts"][0]["function_response"]["response"]
    assert fr["error"] == mod.ERR_TOPE_BUSQUEDA


def test_noticias_con_error_llega_al_modelo(res):
    client = FakeGeminiClient([resp(llamada("buscar_noticias", {"consulta": ""})), resp(texto("Sin noticias."))])
    r = responder_gemini([{"role": "user", "content": "noticias"}], "p", res, client)
    assert not r.error
    assert "error" in client.llamadas[1]["contents"][-1]["parts"][0]["function_response"]["response"]


def test_error_429_cuota_y_rollback(res):
    raw = [{"role": "user", "parts": [{"text": "p1"}]}, {"role": "model", "parts": [{"text": "r1"}]},
           {"role": "user", "content": "p2"}]
    previo = json.loads(json.dumps(raw[:2]))
    r = responder_gemini(raw, "resumen", res, FakeGeminiClient(raises=err429()))
    assert r.error and "límite gratuito" in r.texto and r.texto.startswith("No pude") and raw == previo


def test_rollback_con_turnos_parciales(res):
    raw = [{"role": "user", "content": "p1"}]
    client = FakeGeminiClient([resp(llamada("consultar_resultados", {"tema": "calidad"})), None])
    r = responder_gemini(raw, "resumen", res, client)  # la 2.ª respuesta no tiene la forma esperada
    assert r.error and raw == []


def test_mensajes_de_error():
    m = mod._mensaje_error
    assert "límite gratuito" in m(err429())
    clave = errors.ClientError(400, {"error": {"message": "API key not valid.", "status": "INVALID_ARGUMENT"}})
    assert "inválida" in m(clave)
    assert "MODELO_GEMINI" in m(errors.ClientError(404, {"error": {"message": "x", "status": "NOT_FOUND"}}))
    assert "no está disponible" in m(errors.ServerError(503, {"error": {"message": "x", "status": "UNAVAILABLE"}}))
    assert "conectarme" in m(ConnectionError("x"))
    assert "inesperado" in m(ValueError("x"))


def test_args_invalidos_llegan_como_error_al_modelo(res):
    client = FakeGeminiClient([resp(llamada("simular_escenario", {"shocks": {"W": 1}})), resp(texto("ok"))])
    r = responder_gemini([{"role": "user", "content": "x"}], "resumen", res, client)
    assert not r.error
    out = client.llamadas[1]["contents"][-1]["parts"][0]["function_response"]["response"]
    assert "error" in out and "Materias desconocidas" in out["error"]


def test_bloqueada_y_maximo_de_vueltas(res):
    vacia = types.GenerateContentResponse(candidates=[types.Candidate(finish_reason="SAFETY")])
    r = responder_gemini([{"role": "user", "content": "x"}], "p", res, FakeGeminiClient([vacia]))
    assert r.error and "No puedo" in r.texto
    client = FakeGeminiClient([resp(llamada("consultar_resultados", {"tema": "calidad"}))] * mod.MAX_VUELTAS)
    r = responder_gemini([{"role": "user", "content": "x"}], "p", res, client)
    assert r.error and len(client.llamadas) == mod.MAX_VUELTAS


def test_historial_append_only_entre_preguntas(res):
    raw = [{"role": "user", "content": "pregunta 1"}]
    client = FakeGeminiClient([resp(llamada("consultar_resultados", {"tema": "calidad"}, firma=b"\x00\xffsig")),
                               resp(texto("r1")), resp(texto("r2"))])
    responder_gemini(raw, "relacion", res, client)
    assert len(raw) == 4 and raw[0]["parts"][0]["text"] == "[Página: relacion] pregunta 1"
    assert raw[1]["role"] == "model" and raw[2]["parts"][0]["function_response"]["name"] == "consultar_resultados"
    enviado = json.loads(json.dumps(raw))  # serializable, incluida la thought_signature
    assert raw[1]["parts"][0]["thought_signature"]
    raw.append({"role": "user", "content": "pregunta 2"})
    r = responder_gemini(raw, "presupuesto", res, client)
    assert r.texto == "r2"
    n = len(enviado)
    assert client.llamadas[-1]["contents"][:n] == enviado
    assert client.llamadas[-1]["contents"][n]["parts"][0]["text"] == "[Página: presupuesto] pregunta 2"


def _sin_keys(monkeypatch):
    for k in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "ANTHROPIC_API_KEY", "PROVEEDOR_AGENTE"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("APP_RAPIDO", "1")


def test_elegir_proveedor(monkeypatch):
    from app.layout import elegir_proveedor
    _sin_keys(monkeypatch)
    assert elegir_proveedor() is None
    monkeypatch.setenv("ANTHROPIC_API_KEY", "a")
    assert elegir_proveedor() == ("claude", "a")
    monkeypatch.setenv("GOOGLE_API_KEY", "g")
    assert elegir_proveedor() == ("gemini", "g")
    monkeypatch.setenv("GEMINI_API_KEY", "g2")
    assert elegir_proveedor() == ("gemini", "g2")
    monkeypatch.setenv("PROVEEDOR_AGENTE", "claude")
    assert elegir_proveedor() == ("claude", "a")


def test_app_sin_keys_muestra_ejemplos(monkeypatch):
    _sin_keys(monkeypatch)
    at = AppTest.from_file(MAIN, default_timeout=120).run()
    assert not at.exception and any("Agente desactivado" in str(m.value) for m in at.info)
    assert not any(str(c.value).startswith("Responde:") for c in at.caption)


def test_app_con_gemini_responde_con_cliente_falso(monkeypatch):
    from app import layout
    client = FakeGeminiClient([resp(llamada("consultar_resultados", {"tema": "formula"})),
                               resp(texto("Y domina el Equipo 1."))])
    _sin_keys(monkeypatch)
    monkeypatch.setenv("GEMINI_API_KEY", "clave-falsa")
    monkeypatch.setattr(layout, "_crear_cliente_gemini", lambda key: client)
    at = AppTest.from_file(MAIN, default_timeout=120).run()
    assert not at.exception and any("Responde: Gemini (" in str(c.value) for c in at.caption)
    at.chat_input[0].set_value("¿De qué depende el Equipo 1?").run()
    assert not at.exception
    assert any("Y domina el Equipo 1." in m.value for m in at.markdown)
    assert any("consultar_resultados" in c.value for c in at.caption)
    assert len(at.session_state[layout.CLAVE_CRUDO_GEMINI]) == 4
    at.button(key="agente_borrar").click().run()
    assert not any("Y domina" in m.value for m in at.markdown)
    assert at.session_state[layout.CLAVE_CRUDO_GEMINI] == []
