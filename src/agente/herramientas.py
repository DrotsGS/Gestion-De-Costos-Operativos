"""Herramientas del agente: esquemas para la API y su ejecución sobre los resultados (sin Streamlit)."""
import pandas as pd

from src.config import COBERTURA_NOMINAL, EQUIPOS, MATERIAS
from src.contenido import formula_texto
from src.negocio import evaluate_quote
from src.pipeline import Resultados
from src.pronostico import apply_shock, equipment_fan

TEMAS = ("formula", "pronostico", "validacion", "calidad")

_EQUIPO_PROP = {"type": "string", "enum": list(EQUIPOS),
                "description": "Opcional; si se omite se devuelven ambos equipos."}

TOOLS: list[dict] = [
    {
        "name": "consultar_resultados",
        "description": (
            "Consulta los resultados del análisis de la app: formula (pesos de la fórmula por unidad de precio y parte del costo de X, Y, Z por equipo), "
            "pronostico (rango P10/P50/P90 mensual y horizonte confiable), validacion (error del backtest y "
            "cobertura empírica de los rangos) o calidad (hallazgos de la auditoría de datos). "
            "Úsala para cualquier cifra del análisis."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"tema": {"type": "string", "enum": list(TEMAS)}, "equipo": _EQUIPO_PROP},
            "required": ["tema"],
            "additionalProperties": False,
        },
    },
    {
        "name": "simular_escenario",
        "description": (
            "Simula un choque porcentual sostenido en el precio de las materias primas (p. ej. Y = 0.2 es +20 %) "
            "y devuelve el costo P50 del equipo con y sin choque, en el mes 1 y en el horizonte confiable."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "shocks": {
                    "type": "object",
                    "description": "Variación fraccional por materia prima (0.2 = +20 %).",
                    "properties": {m: {"type": "number"} for m in MATERIAS},
                    "additionalProperties": False,
                },
                "equipo": _EQUIPO_PROP,
            },
            "required": ["shocks"],
            "additionalProperties": False,
        },
    },
    {
        "name": "evaluar_cotizacion",
        "description": (
            "Evalúa si el precio cotizado de un equipo en un mes (AAAA-MM) es razonable frente al rango "
            "pronosticado (precio justo P50 y umbral P90)."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "equipo": {"type": "string", "enum": list(EQUIPOS)},
                "mes": {"type": "string", "description": "Mes de la compra, formato AAAA-MM."},
                "precio": {"type": "number", "description": "Precio cotizado."},
            },
            "required": ["equipo", "mes", "precio"],
            "additionalProperties": False,
        },
    },
    {"type": "web_search_20260209", "name": "web_search", "max_uses": 3},
]


def _r(x: float, dec: int = 2) -> float:
    return round(float(x), dec)


def _equipos(equipo) -> list[str]:
    if equipo is None:
        return list(EQUIPOS)
    if equipo not in EQUIPOS:
        raise ValueError(f"Equipo desconocido: {equipo!r}. Válidos: {', '.join(EQUIPOS)}.")
    return [equipo]


def _formula(res: Resultados, eqs: list[str]) -> dict:
    return {eq: {"pesos": {m: _r(res.pesos[eq][m], 3) for m in MATERIAS},
                 "participacion_costo": {m: _r(res.participacion[eq][m], 3) for m in MATERIAS},
                 "nota": "pesos = coeficientes por unidad de precio (no son % del costo); "
                         "participacion_costo = parte del costo de cada materia (promedio últimos 12 meses)",
                 "formula": formula_texto(res.pesos[eq], res.participacion[eq]),
                 "sd_residual_relativa": _r(res.resid_sd[eq], 4)} for eq in eqs}


def _pronostico(res: Resultados, eqs: list[str]) -> dict:
    out = {"horizonte_confiable_meses": res.horizonte, "escenario": "base (caminata aleatoria sin deriva)"}
    for eq in eqs:
        fan = res.fans["base"][eq]
        out[eq] = [{"mes": f"{f:%Y-%m}", "p10": _r(r.p10), "p50": _r(r.p50), "p90": _r(r.p90),
                    "tipo": "confiable" if i < res.horizonte else "referencial"}
                   for i, (f, r) in enumerate(fan.iterrows())]
    return out


def _validacion(res: Resultados, eqs: list[str]) -> dict:
    out = {"horizonte_confiable_meses": res.horizonte, "cobertura_nominal": COBERTURA_NOMINAL}
    for eq in eqs:
        bt = res.backtest[eq]
        mejor = bt.loc[bt.groupby("horizonte")["mape"].idxmin()]
        cob = res.cobertura[eq].set_index("horizonte")["cobertura"]
        out[eq] = [{"horizonte_meses": int(r.horizonte), "mejor_modelo": r.modelo,
                    "mape_pct": _r(r.mape * 100, 1),
                    "cobertura_empirica": _r(cob[r.horizonte]) if r.horizonte in cob.index else None}
                   for r in mejor.itertuples()]
    return out


def _consultar(args: dict, res: Resultados) -> dict:
    tema = args.get("tema")
    if tema not in TEMAS:
        raise ValueError(f"Tema desconocido: {tema!r}. Válidos: {', '.join(TEMAS)}.")
    if tema == "calidad":
        return {"hallazgos": [{"titulo": h.titulo, "severidad": h.severidad} for h in res.hallazgos]}
    eqs = _equipos(args.get("equipo"))
    return {"formula": _formula, "pronostico": _pronostico, "validacion": _validacion}[tema](res, eqs)


def _simular(args: dict, res: Resultados) -> dict:
    shocks = args.get("shocks")
    if not isinstance(shocks, dict) or not shocks:
        raise ValueError('Indica al menos un choque, p. ej. {"Y": 0.2}.')
    malas = [k for k in shocks if k not in MATERIAS]
    if malas:
        raise ValueError(f"Materias desconocidas: {malas}. Válidas: {', '.join(MATERIAS)}.")
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not pd.notna(v) or v <= -1
           for v in shocks.values()):
        raise ValueError("Cada choque debe ser un número mayor que -1 (0.2 = +20 %).")
    eqs = _equipos(args.get("equipo"))
    paths = apply_shock(res.paths, {k: float(v) for k, v in shocks.items()})
    h = max(1, min(res.horizonte, res.paths.shape[1]))
    por_equipo = {}
    for eq in eqs:
        base = res.fans["base"][eq]["p50"]
        esc = equipment_fan(paths, res.pesos[eq], res.resid_sd[eq])["p50"]

        def fila(i):
            return {"mes": f"{base.index[i]:%Y-%m}", "p50_base": _r(base.iloc[i]),
                    "p50_escenario": _r(esc.iloc[i]), "cambio_pct": _r((esc.iloc[i] / base.iloc[i] - 1) * 100, 1)}

        por_equipo[eq] = {**fila(h - 1), "mes_1": fila(0)}
    meta = {"shocks": {k: float(v) for k, v in shocks.items()}, "horizonte_confiable_meses": res.horizonte}
    if len(eqs) == 1:  # un solo equipo: cifras directamente en el nivel superior
        return {**meta, "equipo": eqs[0], **por_equipo[eqs[0]]}
    return {**meta, **por_equipo}


def _cotizacion(args: dict, res: Resultados) -> dict:
    v = evaluate_quote(res.fans["base"], args.get("equipo"), args.get("mes"), args.get("precio"))
    if not v.ok:
        return {"error": v.mensaje}
    return {"mensaje": v.mensaje, "precio_justo_p50": _r(v.precio_justo),
            "pct_vs_p50": _r(v.pct_vs_p50 * 100, 1), "sobre_p90": bool(v.sobre_p90)}


_EJECUTORES = {"consultar_resultados": _consultar, "simular_escenario": _simular, "evaluar_cotizacion": _cotizacion}


def ejecutar(nombre: str, args: dict, res: Resultados) -> dict:
    """Ejecuta una herramienta. Nunca lanza: ante argumentos inválidos devuelve {"error": ...}."""
    try:
        if nombre not in _EJECUTORES:
            return {"error": f"Herramienta desconocida: {nombre}."}
        return _EJECUTORES[nombre](dict(args or {}), res)
    except Exception as e:  # noqa: BLE001 - contrato: nunca lanzar
        return {"error": str(e) or f"No se pudo ejecutar {nombre}."}
