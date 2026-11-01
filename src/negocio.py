"""Negocio: presupuesto por fases con reserva y verificador de cotizaciones."""
from dataclasses import dataclass

import pandas as pd

from src.config import EQUIPOS

# Cantidades de EJEMPLO editables: el caso no entrega cantidades a comprar.
CANTIDADES_EJEMPLO = pd.DataFrame({
    "fase": ["Fase 1", "Fase 2", "Fase 3"],
    "mes": ["2023-10", "2024-01", "2024-04"],
    "Equipo1": [10, 15, 8],
    "Equipo2": [5, 6, 4],
})


@dataclass
class Veredicto:
    ok: bool
    mensaje: str
    precio_justo: float | None = None
    pct_vs_p50: float | None = None
    sobre_p90: bool | None = None


def _fila_mes(fan: pd.DataFrame, mes: str) -> pd.Series | None:
    """Fila del abanico cuyo mes (YYYY-MM) coincide, o None si no está."""
    try:
        periodo = pd.Period(str(mes), freq="M")
    except (ValueError, TypeError):
        return None
    idx = fan.index.to_period("M")
    pos = idx == periodo
    return fan[pos].iloc[0] if pos.any() else None


def _fmt(x: float, dec: int = 2) -> str:
    """Formato numérico español (coma decimal, punto de miles)."""
    s = f"{x:,.{dec}f}"
    return s.replace(",", "\0").replace(".", ",").replace("\0", ".")


def budget(fans: dict[str, pd.DataFrame], cantidades: pd.DataFrame) -> pd.DataFrame:
    """Presupuesto por fase: p50, reserva (Σ cant·(p90−p50)) y total."""
    equipos = [c for c in cantidades.columns if c not in ("fase", "mes")]
    for eq in equipos:
        if eq not in fans:
            raise ValueError(f"Equipo desconocido en cantidades: {eq}")
    filas = []
    for _, r in cantidades.iterrows():
        p50 = reserva = 0.0
        for eq in equipos:
            fila = _fila_mes(fans[eq], r["mes"])
            if fila is None:
                raise ValueError(f"El mes {r['mes']} está fuera del horizonte del pronóstico de {eq}.")
            p50 += r[eq] * fila["p50"]
            reserva += r[eq] * (fila["p90"] - fila["p50"])
        filas.append((r["fase"], p50, reserva))
    out = pd.DataFrame(filas, columns=["fase", "p50", "reserva"]).groupby("fase", sort=False).sum()
    out["total"] = out["p50"] + out["reserva"]
    return out


def evaluate_quote(fans: dict[str, pd.DataFrame], equipo: str, mes: str, precio: float) -> Veredicto:
    """Compara una cotización con el abanico del mes. Nunca lanza excepción.

    Nota: el abanico es un costo promedio mensual; una compra puntual suma además
    ≈1,8 % de ruido diario (según el análisis de datos).
    """
    try:
        precio = float(precio)
    except (TypeError, ValueError):
        return Veredicto(False, "El precio debe ser un número.")
    if not pd.notna(precio) or precio <= 0 or precio == float("inf"):
        return Veredicto(False, "El precio debe ser un número positivo.")
    if equipo not in fans:
        return Veredicto(False, f"Equipo desconocido: {equipo}.")
    fila = _fila_mes(fans[equipo], mes)
    if fila is None:
        return Veredicto(False, f"El mes {mes} está fuera del horizonte del pronóstico.")
    p50, p90 = float(fila["p50"]), float(fila["p90"])
    pct = precio / p50 - 1
    sobre = precio > p90
    base = f"{_fmt(abs(pct) * 100, 1)} % {'sobre' if pct >= 0 else 'bajo'} el precio justo (P50 = {_fmt(p50)})."
    if sobre:
        msg = base + " Supera el P90: negociar."
    elif pct > 0:
        msg = base + " Dentro del rango esperado (hasta P90)."
    else:
        msg = base + " Cotización favorable."
    return Veredicto(True, msg, p50, pct, sobre)


ETIQUETA_EQ = {"Equipo1": "Equipo 1", "Equipo2": "Equipo 2"}


def validar_cantidades(cant: pd.DataFrame, meses: set[str]) -> list[str]:
    """Errores de la tabla editada (vacía si es válida); budget lanzaría ValueError con estos casos."""
    if cant.empty:
        return ["La tabla está vacía: agrega al menos una fase."]
    errores = []
    for i, r in cant.reset_index(drop=True).iterrows():
        n = i + 1
        if pd.isna(r["fase"]) or not str(r["fase"]).strip():
            errores.append(f"Fila {n}: falta el nombre de la fase.")
        try:
            mes = str(pd.Period(str(r["mes"]).strip(), freq="M"))
        except (ValueError, TypeError):
            mes = None
        if mes not in meses:
            errores.append(f"Fila {n}: el mes '{r['mes']}' no existe en el pronóstico "
                           f"({min(meses)} a {max(meses)}, formato AAAA-MM).")
        for eq in EQUIPOS:
            if pd.isna(r[eq]) or r[eq] < 0:
                errores.append(f"Fila {n}: la cantidad de {ETIQUETA_EQ[eq]} debe ser un número no negativo.")
    return errores
