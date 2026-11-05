"""Pruebas del agente con un cliente falso (nunca se llama a la API real)."""
import json
from types import SimpleNamespace

import anthropic
import httpx2 as httpx
import pytest
from streamlit.testing.v1 import AppTest

from src.agente import agente as mod_agente
from src.agente.agente import responder
from src.agente.herramientas import TOOLS, ejecutar
from src.config import ROOT
from src.pipeline import build_results

MAIN = str(ROOT / "app" / "main.py")


@pytest.fixture(scope="module")
def res():
    return build_results(step=6, n_sims=300)


def tool_use(nombre, args, id="tu_1"):
    return SimpleNamespace(content=[SimpleNamespace(type="tool_use", name=nombre, id=id, input=args)],
                           stop_reason="tool_use")


def server_tool(nombre="web_search"):
    return SimpleNamespace(content=[SimpleNamespace(type="server_tool_use", name=nombre, id="st_1", input={})],
                           stop_reason="pause_turn")


def text(t, stop="end_turn"):
    return SimpleNamespace(content=[SimpleNamespace(type="text", text=t)], stop_reason=stop)


class FakeClient:
    """Imita client.beta.messages.create: devuelve las respuestas guardadas en orden."""

    def __init__(self, respuestas=(), raises=None):
        self.respuestas = list(respuestas)
        self.raises = raises
        self.llamadas = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.llamadas.append(json.loads(json.dumps(kwargs, default=lambda o: repr(o))))
        if self.raises:
            exc = self.raises
            if isinstance(exc, type):
                exc = exc(request=httpx.Request("POST", "http://x"))
            raise exc
        return self.respuestas.pop(0)


def test_herramienta_args_invalidos(res):
    assert "error" in ejecutar("evaluar_cotizacion", {"equipo": "Equipo3", "mes": "2023-09", "precio": 100}, res)
    assert "error" in ejecutar("simular_escenario", {"shocks": {"W": 0.1}}, res)
    assert "error" in ejecutar("consultar_resultados", {"tema": "otro"}, res)
    assert "error" in ejecutar("evaluar_cotizacion", {"equipo": "Equipo1", "mes": "2023-09", "precio": -5}, res)
    assert "error" in ejecutar("evaluar_cotizacion", {"equipo": "Equipo1", "mes": "1999-01", "precio": 100}, res)
    assert "error" in ejecutar("no_existe", {}, res)


def test_simular_escenario_sube(res):
    out = ejecutar("simular_escenario", {"shocks": {"Y": 0.2}, "equipo": "Equipo1"}, res)
    assert out["p50_escenario"] > out["p50_base"]
    assert out["cambio_pct"] > 0 and out["mes_1"]["p50_escenario"] > out["mes_1"]["p50_base"]


def test_consultar_resultados_temas(res):
    f = ejecutar("consultar_resultados", {"tema": "formula", "equipo": "Equipo1"}, res)
    assert "Y" in f["Equipo1"]["formula"] and "Equipo2" not in f
    assert f["Equipo1"]["participacion_costo"]["Y"] > 0.9 and "pesos" in f["Equipo1"]
    assert "no son % del costo" in f["Equipo1"]["nota"]
    p = ejecutar("consultar_resultados", {"tema": "pronostico"}, res)
    tipos = [r["tipo"] for r in p["Equipo1"]]
    assert tipos[0] == "confiable" and tipos[-1] == "referencial" and len(tipos) == 12
    v = ejecutar("consultar_resultados", {"tema": "validacion"}, res)
    assert v["Equipo2"][0]["cobertura_empirica"] is not None
    assert ejecutar("consultar_resultados", {"tema": "calidad"}, res)["hallazgos"]
    json.dumps([f, p, v])  # todo serializable


def test_evaluar_cotizacion_ok(res):
    mes = f"{res.fans['base']['Equipo1'].index[0]:%Y-%m}"
    out = ejecutar("evaluar_cotizacion", {"equipo": "Equipo1", "mes": mes, "precio": 100000}, res)
    assert out["sobre_p90"] is True and "error" not in out


def test_tools_incluyen_busqueda_web():
    assert [t["name"] for t in TOOLS] == ["consultar_resultados", "simular_escenario", "evaluar_cotizacion",
                                          "buscar_noticias", "web_search"]


def test_bucle_usa_herramienta(res):
    client = FakeClient([tool_use("consultar_resultados", {"tema": "formula", "equipo": "Equipo1"}),
                         text("Equipo 1 ≈ 80% Y")])
    r = responder([{"role": "user", "content": "¿De qué depende el Equipo 1?"}], "relacion", res, client)
    assert r.herramientas_usadas == ["consultar_resultados"] and not r.error
    assert r.texto == "Equipo 1 ≈ 80% Y"
    primera, segunda = client.llamadas
    assert primera["messages"][0]["content"].startswith("[Página: relacion]")
    resultado = segunda["messages"][-1]["content"][0]
    assert resultado["type"] == "tool_result" and resultado["tool_use_id"] == "tu_1" and not resultado["is_error"]


def test_bucle_buscar_noticias(res, monkeypatch):
    monkeypatch.setattr("src.agente.herramientas.buscar_noticias",
                        lambda c, m=5: {"consulta": c, "noticias": [{"titulo": "Acero sube"}],
                                        "fuente": "Google News (RSS)"})
    client = FakeClient([tool_use("buscar_noticias", {"consulta": "precio acero"}), text("Reuters dice")])
    r = responder([{"role": "user", "content": "noticias del acero"}], "resumen", res, client)
    assert r.herramientas_usadas == ["buscar_noticias"] and not r.error
    resultado = client.llamadas[1]["messages"][-1]["content"][0]
    assert not resultado["is_error"] and "Acero sube" in resultado["content"]
    assert "buscar_noticias" in client.llamadas[0]["system"]


def test_bucle_pause_turn_y_busqueda_web(res):
    client = FakeClient([server_tool(), text("Según la noticia…")])
    r = responder([{"role": "user", "content": "noticias del acero"}], "resumen", res, client)
    assert r.herramientas_usadas == ["web_search"] and not r.error and len(client.llamadas) == 2


def test_herramienta_con_error_marca_is_error(res):
    client = FakeClient([tool_use("simular_escenario", {"shocks": {"W": 1}}), text("ok")])
    responder([{"role": "user", "content": "x"}], "resumen", res, client)
    assert client.llamadas[1]["messages"][-1]["content"][0]["is_error"] is True


def thinking_y_tool(nombre, args):
    return SimpleNamespace(content=[SimpleNamespace(type="thinking", thinking="pienso", signature="sig"),
                                    SimpleNamespace(type="tool_use", name=nombre, id="tu_1", input=args)],
                           stop_reason="tool_use")


def test_historial_append_only_entre_preguntas(res):
    raw = [{"role": "user", "content": "pregunta 1"}]
    client = FakeClient([thinking_y_tool("consultar_resultados", {"tema": "calidad"}), text("r1"), text("r2")])
    responder(raw, "relacion", res, client)
    enviado = json.loads(json.dumps(raw))
    assert len(raw) == 4 and raw[0]["content"] == "[Página: relacion] pregunta 1"
    assert raw[1]["content"][0]["type"] == "thinking" and raw[2]["content"][0]["type"] == "tool_result"
    raw.append({"role": "user", "content": "pregunta 2"})
    responder(raw, "presupuesto", res, client)
    n = len(enviado)
    assert client.llamadas[-1]["messages"][:n] == enviado
    assert client.llamadas[-1]["messages"][n]["content"] == "[Página: presupuesto] pregunta 2"


def test_rollback_si_falla(res):
    raw = [{"role": "user", "content": "p1"}, {"role": "assistant", "content": [{"type": "text", "text": "r1"}]},
           {"role": "user", "content": "p2"}]
    previo = json.loads(json.dumps(raw[:2]))
    client = FakeClient([thinking_y_tool("consultar_resultados", {"tema": "calidad"}),
                         SimpleNamespace(content=[], stop_reason="refusal")])
    r = responder(raw, "resumen", res, client)
    assert r.error and raw == previo  # pregunta fallida y turnos parciales eliminados
    raw.append({"role": "user", "content": "p3"})
    assert responder(raw, "resumen", res, FakeClient(raises=anthropic.APIConnectionError)).error
    assert raw == previo


def test_status_error_mensajes():
    resp = httpx.Response(404, request=httpx.Request("POST", "http://x"))
    assert "MODELO_AGENTE" in mod_agente._mensaje_error(anthropic.NotFoundError("x", response=resp, body=None))
    resp = httpx.Response(503, request=httpx.Request("POST", "http://x"))
    assert "no está disponible" in mod_agente._mensaje_error(anthropic.InternalServerError("x", response=resp, body=None))


def test_refusal(res):
    client = FakeClient([SimpleNamespace(content=[], stop_reason="refusal")])
    r = responder([{"role": "user", "content": "x"}], "resumen", res, client)
    assert r.error and "No puedo" in r.texto


def test_maximo_de_vueltas(res):
    client = FakeClient([tool_use("consultar_resultados", {"tema": "calidad"})] * mod_agente.MAX_VUELTAS)
    r = responder([{"role": "user", "content": "x"}], "resumen", res, client)
    assert r.error and len(client.llamadas) == mod_agente.MAX_VUELTAS


def test_error_api_no_rompe(res):
    r = responder([{"role": "user", "content": "hola"}], "resumen", res, FakeClient(raises=anthropic.APIConnectionError))
    assert r.error and "no pude" in r.texto.lower()


def test_app_sin_key_muestra_ejemplos(monkeypatch):
    for k in ("ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "PROVEEDOR_AGENTE"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("APP_RAPIDO", "1")
    at = AppTest.from_file(MAIN, default_timeout=120).run()
    assert not at.exception and any("Agente desactivado" in str(m.value) for m in at.info)
    assert any("Ejemplo ilustrativo" in str(c.value) for c in at.caption)
    assert len(at.chat_message) >= 2


def test_app_con_key_responde_con_cliente_falso(monkeypatch):
    from app import layout
    client = FakeClient([tool_use("consultar_resultados", {"tema": "formula"}), text("Y domina el Equipo 1.")])
    for k in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "PROVEEDOR_AGENTE"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "clave-falsa")
    monkeypatch.setenv("APP_RAPIDO", "1")
    monkeypatch.setattr(layout, "_crear_cliente", lambda key: client)
    at = AppTest.from_file(MAIN, default_timeout=120).run()
    assert not at.exception and not any("Agente desactivado" in str(m.value) for m in at.info)
    at.chat_input[0].set_value("¿De qué depende el Equipo 1?").run()
    assert not at.exception
    assert any("Y domina el Equipo 1." in m.value for m in at.markdown)
    assert any("consultar_resultados" in c.value for c in at.caption)
    at.button(key="agente_borrar").click().run()
    assert not any("Y domina" in m.value for m in at.markdown)


def test_system_pide_respuestas_cortas_sin_tablas():
    assert "panel angosto" in mod_agente.SYSTEM and "tablas" in mod_agente.SYSTEM
