"""Graba 3 conversaciones reales con el agente en app/ejemplos/conversaciones.json.

Uso (con tu key): GEMINI_API_KEY=... o ANTHROPIC_API_KEY=... python scripts/grabar_ejemplos.py
No lo ejecutan las pruebas.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.layout import PAGINAS, _crear_cliente, _crear_cliente_gemini, elegir_proveedor  # noqa: E402
from src.agente.agente import responder  # noqa: E402
from src.agente.agente_gemini import responder_gemini  # noqa: E402
from src.pipeline import build_results  # noqa: E402

SALIDA = Path(__file__).resolve().parents[1] / "app" / "ejemplos" / "conversaciones.json"
PREGUNTAS = [
    ("relacion", "¿De qué depende el costo del Equipo 1 y cuánto confío en esa fórmula?"),
    ("proyecciones", "¿Qué pasaría con el Equipo 1 y el Equipo 2 si Y sube 20 %?"),
    ("resumen", "¿Hay noticias recientes sobre el precio del acero que cambien el riesgo del presupuesto?"),
]


def main() -> None:
    elegido = elegir_proveedor()
    if not elegido:
        sys.exit("Define GEMINI_API_KEY o ANTHROPIC_API_KEY antes de ejecutar este script.")
    proveedor, key = elegido
    gemini = proveedor == "gemini"
    client = _crear_cliente_gemini(key) if gemini else _crear_cliente(key)
    responder_fn = responder_gemini if gemini else responder
    res = build_results()
    ejemplos = []
    for pagina, pregunta in PREGUNTAS:
        r = responder_fn([{"role": "user", "content": pregunta}], PAGINAS[pagina], res, client)
        print(f"- {pregunta}\n  herramientas: {r.herramientas_usadas}  error: {r.error}")
        if r.error:
            sys.exit(f"Falló la pregunta: {r.texto}")
        ejemplos.append({"ilustrativo": False, "pregunta": pregunta, "respuesta": r.texto,
                         "herramientas": r.herramientas_usadas})
    SALIDA.write_text(json.dumps(ejemplos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Guardado en {SALIDA}")


if __name__ == "__main__":
    main()
