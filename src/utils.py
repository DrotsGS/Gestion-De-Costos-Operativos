"""Cargadores de datos y limpieza."""
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from src.config import DATA_DIR, MATERIAS

# Y.csv usa formato europeo (';', coma decimal, d/m/aaaa, BOM)
_OPCIONES_CSV = {"Y": {"sep": ";", "decimal": ",", "encoding": "utf-8-sig"}}


def load_series(name: str, data_dir: Path = DATA_DIR) -> pd.Series:
    """Serie de precios de una materia prima, índice `date` ascendente."""
    if name not in MATERIAS:
        raise ValueError(f"Materia prima inválida: {name!r}; use una de {MATERIAS}")
    df = pd.read_csv(Path(data_dir) / f"{name}.csv", **_OPCIONES_CSV.get(name, {}))
    fechas = pd.to_datetime(df["Date"], dayfirst=(name == "Y"))
    s = pd.Series(df["Price"].astype(float).to_numpy(), index=pd.DatetimeIndex(fechas, name="date"), name=name)
    return s.sort_index()


def load_historico(data_dir: Path = DATA_DIR) -> pd.DataFrame:
    """Histórico de equipos con columnas X, Y, Z, Equipo1, Equipo2."""
    df = pd.read_csv(Path(data_dir) / "historico_equipos.csv", parse_dates=["Date"])
    df = df.rename(columns=lambda c: c.removeprefix("Price_")).rename(columns={"Date": "date"})
    return df.set_index("date").sort_index().astype(float)


def _tiene_exceso_decimales(v: float, max_decimals: int) -> bool:
    """True si v tiene más de `max_decimals` decimales (con tolerancia numérica)."""
    return not np.isclose(v, round(v, max_decimals), rtol=0, atol=1e-9)


def detect_anomalies(s: pd.Series, jump: float = 0.08, max_decimals: int = 2) -> pd.DataFrame:
    """Detecta picos revertidos y precisión anómala.

    Ambas condiciones -> "corregir"; solo una -> "advertir" (posible evento real).
    """
    p = s.to_numpy(dtype=float)
    r = p[1:] / p[:-1] - 1  # r[i] = retorno de p[i] a p[i+1]
    filas = []
    for t in range(1, len(p) - 1):
        pico = (
            abs(r[t - 1]) > jump
            and abs(r[t]) > jump
            and r[t - 1] * r[t] < 0
            and abs(p[t + 1] / p[t - 1] - 1) < jump / 2
        )
        precision = _tiene_exceso_decimales(p[t], max_decimals)
        if not (pico or precision):
            continue
        if pico and precision:
            regla, accion = "pico revertido + precisión anómala", "corregir"
        elif pico:
            regla, accion = "pico revertido", "advertir"
        else:
            regla, accion = "precisión anómala", "advertir"
        filas.append({"date": s.index[t], "valor": p[t], "regla": regla, "accion": accion})
    return pd.DataFrame(filas, columns=["date", "valor", "regla", "accion"])


def clean_series(s: pd.Series) -> tuple[pd.Series, pd.DataFrame]:
    """Corrige por interpolación lineal en el tiempo los puntos con acción "corregir"."""
    anom = detect_anomalies(s)
    corr = anom[anom["accion"] == "corregir"]
    fechas = pd.DatetimeIndex(corr["date"])
    limpia = s.copy()
    limpia.loc[fechas] = np.nan
    limpia = limpia.interpolate(method="time")
    log = pd.DataFrame(
        {
            "date": fechas,
            "original": s.loc[fechas].to_numpy(),
            "corregido": limpia.loc[fechas].to_numpy(),
            "regla": corr["regla"].to_numpy(),
        },
        columns=["date", "original", "corregido", "regla"],
    )
    return limpia, log


@dataclass
class CleanData:
    daily: pd.DataFrame  # histórico limpio (X, Y, Z, Equipo1, Equipo2)
    x_full: pd.Series  # X limpio completo (hasta 2024-04)
    correcciones: pd.DataFrame
    advertencias: pd.DataFrame


def load_clean_dataset(data_dir: Path = DATA_DIR) -> CleanData:
    """Histórico con X, Y, Z limpios; los equipos no se tocan."""
    daily = load_historico(data_dir)
    correcciones, advertencias, x_full = [], [], None
    for m in MATERIAS:
        cruda = load_series(m, data_dir)
        limpia, log = clean_series(cruda)
        anom = detect_anomalies(cruda)
        correcciones.append(log.assign(serie=m))
        advertencias.append(anom[anom["accion"] == "advertir"].assign(serie=m))
        daily[m] = limpia.reindex(daily.index)
        if m == "X":
            x_full = limpia
    return CleanData(
        daily=daily,
        x_full=x_full,
        correcciones=pd.concat(correcciones, ignore_index=True),
        advertencias=pd.concat(advertencias, ignore_index=True),
    )


def to_monthly(df: pd.DataFrame | pd.Series) -> pd.DataFrame | pd.Series:
    """Promedio mensual con índice de inicio de mes (MS)."""
    return df.resample("MS").mean()
