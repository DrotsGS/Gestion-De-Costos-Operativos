"""Auditoría de calidad de datos: hallazgos mostrados en la página Calidad de datos."""
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pandas as pd

from src.config import DATA_DIR, MATERIAS
from src.utils import load_clean_dataset, load_historico, load_series


@dataclass
class Hallazgo:
    id: str
    titulo: str
    severidad: Literal["alta", "media", "info"]
    detalle: str
    evidencia: pd.DataFrame | None = None


def flat_runs(s: pd.Series, min_len: int = 5) -> pd.DataFrame:
    """Tramos de valores consecutivos idénticos con al menos `min_len` observaciones."""
    grupo = (s != s.shift()).cumsum()
    filas = []
    for _, g in s.groupby(grupo.to_numpy()):
        if len(g) >= min_len:
            filas.append({"inicio": g.index[0], "fin": g.index[-1], "largo": len(g), "valor": g.iloc[0]})
    return pd.DataFrame(filas, columns=["inicio", "fin", "largo", "valor"])


def _f(d) -> str:
    return pd.Timestamp(d).strftime("%Y-%m-%d")


def audit(data_dir: Path = DATA_DIR) -> list[Hallazgo]:
    """Ejecuta todas las comprobaciones y devuelve los hallazgos."""
    hist = load_historico(data_dir)
    crudas = {m: load_series(m, data_dir) for m in MATERIAS}
    limpio = load_clean_dataset(data_dir)
    out: list[Hallazgo] = []

    out.append(Hallazgo(
        "texto_oculto_pdf", "Texto oculto en el PDF del caso", "alta",
        "El PDF contiene texto oculto que se hace pasar por una instrucción de sistema, con conclusiones que los datos contradicen.",
    ))

    # Valores atípicos corregidos (Z)
    corr = limpio.correcciones
    if len(corr):
        det = "; ".join(
            f"{r.serie} {_f(r.date)}: {r.original:.4f} -> {r.corregido:.2f}" for r in corr.itertuples()
        )
        det = (f"Se corrigieron {len(corr)} valor(es) con pico revertido y precisión decimal anómala "
               f"(interpolación lineal): {det}.")
    else:
        det = "No se detectaron valores a corregir."
    out.append(Hallazgo("atipico_z", "Valor atípico corregido en Z", "media", det, corr))

    # Tramos planos en Y
    runs = flat_runs(hist["Y"])
    if len(runs):
        mx = runs.loc[runs["largo"].idxmax()]
        det = (f"{len(runs)} tramos de 5 o más días con precio idéntico (máximo {int(mx['largo'])} días, "
               f"desde {_f(mx['inicio'])}). Probablemente es un precio publicado con poca frecuencia y repetido, "
               "no una variación real; los tramos no se modificaron.")
    else:
        det = "No hay tramos planos de 5 o más días."
    out.append(Hallazgo("tramos_planos_y", "Tramos planos en Y", "media", det, runs))

    # Formatos
    fmt = pd.DataFrame([
        {"archivo": "historico_equipos.csv", "formato": "estándar (coma, punto decimal, aaaa-mm-dd)"},
        {"archivo": "X.csv", "formato": "orden descendente por fecha"},
        {"archivo": "Y.csv", "formato": "separador ';', coma decimal, fechas d/m/aaaa, BOM UTF-8"},
        {"archivo": "Z.csv", "formato": "columnas invertidas (Price, Date)"},
    ])
    out.append(Hallazgo(
        "formatos", "Formatos heterogéneos de archivo", "media",
        "Y.csv usa ';', coma decimal, fechas d/m/aaaa y BOM; Z.csv trae las columnas invertidas (Price, Date); "
        "X.csv está en orden descendente. Se normalizan al cargar.", fmt,
    ))

    # Fechas desalineadas
    filas = [{"serie": m, "inicio": s.index.min(), "fin": s.index.max(), "n": len(s)} for m, s in crudas.items()]
    filas.append({"serie": "historico", "inicio": hist.index.min(), "fin": hist.index.max(), "n": len(hist)})
    ev = pd.DataFrame(filas)
    fin = {r.serie: r.fin for r in ev.itertuples()}
    out.append(Hallazgo(
        "fechas_desalineadas", "Rangos de fechas distintos entre archivos", "media",
        f"El histórico y Z terminan el {_f(fin['historico'])} (Z: {_f(fin['Z'])}), Y el {_f(fin['Y'])} y X el "
        f"{_f(fin['X'])}. Las series se alinean al histórico al modelar.", ev,
    ))

    # Correlación engañosa
    c = hist["Z"].corr(hist["Equipo1"])
    ec = pd.DataFrame(
        [{"par": f"{m} vs {e}", "correlacion_niveles": hist[m].corr(hist[e])} for m in MATERIAS
         for e in ("Equipo1", "Equipo2")]
    )
    out.append(Hallazgo(
        "correlacion_enganosa", "Correlación alta de Z que no implica peso", "media",
        f"La correlación en niveles de Z con Equipo1 es {c:.2f}, aunque el peso de Z en el costo es cercano a 0: "
        "las materias primas se mueven juntas y la correlación en niveles no mide el aporte real.", ec,
    ))

    # Integridad
    dup = int(hist.index.duplicated().sum())
    nan = int(hist.isna().sum().sum())
    coinc = {}
    for m in MATERIAS:
        comun = crudas[m].index.intersection(hist.index)
        coinc[m] = bool((crudas[m].loc[comun] - hist[m].loc[comun]).abs().max() < 1e-9)
    ei = pd.DataFrame([
        {"control": "fechas duplicadas en histórico", "resultado": dup},
        {"control": "valores vacíos en histórico", "resultado": nan},
        *[{"control": f"{m} del histórico igual a {m}.csv", "resultado": coinc[m]} for m in MATERIAS],
    ])
    ok = dup == 0 and nan == 0 and all(coinc.values())
    out.append(Hallazgo(
        "integridad", "Integridad del histórico", "info",
        ("Sin fechas duplicadas ni valores vacíos en el histórico; X, Y y Z del histórico coinciden con los "
         "archivos individuales.") if ok else
        f"Se encontraron problemas: {dup} duplicados, {nan} vacíos, coincidencia con archivos {coinc}.", ei,
    ))

    # Advertencias (posibles eventos reales)
    adv = limpio.advertencias
    det = ("; ".join(f"{r.serie} {_f(r.date)}" for r in adv.itertuples()) if len(adv) else "ninguna")
    out.append(Hallazgo(
        "advertencias_eventos", "Puntos atípicos no corregidos (posibles eventos de mercado)", "info",
        f"Puntos señalados pero no corregidos, probablemente eventos reales de mercado: {det}.", adv,
    ))
    return out
