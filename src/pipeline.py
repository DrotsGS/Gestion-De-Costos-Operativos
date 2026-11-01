"""Pipeline de resultados: punto de entrada único para la app y el agente."""
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from src.auditoria import Hallazgo, audit
from src.config import DATA_DIR, EQUIPOS, HORIZONTE_MAX_MAPE, HORIZONTE_MIN_COB, MATERIAS
from src.pronostico import (ESCENARIOS, apply_shock, backtest_equipo, choose_horizon, equipment_fan,
                            interval_coverage, simulate_paths, x_out_of_sample)
from src.relacion import (cointegration, fit_constrained, fit_ols, participacion_costo, residual_sd,
                          rolling_weights)
from src.utils import CleanData, load_clean_dataset, load_series, to_monthly

H_FAN = 12  # los abanicos siempre cubren 12 meses; `horizonte` marca la zona confiable


@dataclass
class Resultados:
    clean: CleanData
    monthly: pd.DataFrame
    hallazgos: list[Hallazgo]
    pesos: dict[str, pd.Series]  # pesos de la fórmula (por unidad de precio), NO participación en el costo
    participacion: dict[str, pd.Series]  # parte del costo de cada materia (peso·precio / costo)
    ols: dict[str, dict]
    cointegracion: dict[str, dict]
    rolling: dict[str, pd.DataFrame]
    resid_sd: dict[str, float]
    backtest: dict[str, pd.DataFrame]
    cobertura: dict[str, pd.DataFrame]
    horizonte: int
    paths: np.ndarray
    fans: dict[str, dict[str, pd.DataFrame]]  # fans[escenario][equipo]
    x_oos: pd.DataFrame
    z_crudo: pd.Series  # Z sin limpiar (para mostrar antes/después de la corrección)


def build_results(data_dir: Path = DATA_DIR, n_sims: int = 5000, step: int = 1) -> Resultados:
    """Ejecuta todo el análisis. `step` = paso entre orígenes de backtest y cobertura."""
    clean = load_clean_dataset(data_dir)
    monthly = to_monthly(clean.daily)
    pesos = {e: fit_constrained(monthly, e) for e in EQUIPOS}
    sd = {e: residual_sd(monthly, e, pesos[e]) for e in EQUIPOS}
    bt = {e: backtest_equipo(monthly, e, pesos[e], step=step) for e in EQUIPOS}
    cob = {e: interval_coverage(monthly, e, pesos[e], step=step) for e in EQUIPOS}
    horizonte = min(choose_horizon(bt[e], cob[e], max_mape=HORIZONTE_MAX_MAPE, min_cov=HORIZONTE_MIN_COB) for e in EQUIPOS)
    paths = simulate_paths(monthly[list(MATERIAS)], H_FAN, n_sims=n_sims)
    fans = {
        esc: {e: equipment_fan(apply_shock(paths, shock), pesos[e], sd[e]) for e in EQUIPOS}
        for esc, shock in ESCENARIOS.items()
    }
    return Resultados(
        clean=clean,
        monthly=monthly,
        hallazgos=audit(data_dir),
        pesos=pesos,
        participacion={e: participacion_costo(monthly, pesos[e]) for e in EQUIPOS},
        ols={e: fit_ols(monthly, e) for e in EQUIPOS},
        cointegracion={e: cointegration(monthly, e, pesos[e]) for e in EQUIPOS},
        rolling={e: rolling_weights(monthly, e) for e in EQUIPOS},
        resid_sd=sd,
        backtest=bt,
        cobertura=cob,
        horizonte=horizonte,
        paths=paths,
        fans=fans,
        x_oos=x_out_of_sample(clean.x_full, monthly, n_sims=n_sims),
        z_crudo=load_series("Z", data_dir),
    )
