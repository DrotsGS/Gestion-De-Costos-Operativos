"""Modelos de pronóstico puntual y validación histórica (origen móvil)."""
import warnings

import numpy as np
import pandas as pd
from statsmodels.tools.sm_exceptions import ConvergenceWarning, ValueWarning
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.holtwinters import ExponentialSmoothing

from src.config import FECHA_CASO, MATERIAS, SEED
from src.relacion import residual_sd
from src.utils import to_monthly

MODELOS = ("naive", "sma3", "arima", "ets")


def fit_forecast(model: str, s: pd.Series, h: int) -> pd.Series:
    """Pronóstico puntual a h meses. ARIMA/ETS trabajan en log y vuelven a precio."""
    if model not in MODELOS:
        raise ValueError(f"modelo desconocido: {model}")
    idx = pd.date_range(s.index[-1] + pd.offsets.MonthBegin(1), periods=h, freq="MS")
    if model == "naive":
        vals = np.full(h, s.iloc[-1], dtype=float)
    elif model == "sma3":
        vals = np.full(h, s.iloc[-3:].mean(), dtype=float)
    else:
        if (s <= 0).any():
            raise ValueError("los precios deben ser positivos para trabajar en log")
        y = np.log(s.to_numpy(dtype=float))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", ConvergenceWarning)
            warnings.simplefilter("ignore", ValueWarning)
            if model == "arima":
                res = ARIMA(y, order=(1, 1, 0)).fit()
                f = res.forecast(h)
            else:
                res = ExponentialSmoothing(y, trend="add", damped_trend=True).fit()
                f = res.forecast(h)
        vals = np.exp(np.asarray(f))
    return pd.Series(vals, index=idx)


def _metricas(errs: dict) -> pd.DataFrame:
    """errs[(modelo, h)] = lista de (pronóstico, real) -> mape (fracción) y rmse."""
    filas = []
    for (m, h), pares in errs.items():
        a = np.array(pares, dtype=float)
        f, r = a[:, 0], a[:, 1]
        filas.append(
            {
                "modelo": m,
                "horizonte": h,
                "mape": float(np.mean(np.abs((r - f) / r))),
                "rmse": float(np.sqrt(np.mean((r - f) ** 2))),
            }
        )
    return pd.DataFrame(filas, columns=["modelo", "horizonte", "mape", "rmse"])


def _backtest_core(forecaster, actual: pd.Series, index, horizons, start, step):
    """Para cada origen t (>= start, cada `step` meses) ajusta con datos < t y
    compara el paso h con el real en t + (h-1) meses. forecaster(model, t) -> Series."""
    if pd.Timestamp(start) <= index[0]:
        raise ValueError(f"start={start} debe ser posterior al primer dato ({index[0].date()})")
    hmax = max(horizons)
    origenes = [t for t in index if t >= pd.Timestamp(start)][::step]
    errs = {(m, h): [] for m in MODELOS for h in horizons}
    for t in origenes:
        for m in MODELOS:
            f = None
            for h in horizons:
                fecha = t + pd.DateOffset(months=h - 1)
                if fecha not in actual.index:
                    continue
                if f is None:
                    f = forecaster(m, t, hmax)
                errs[(m, h)].append((f.loc[fecha], actual.loc[fecha]))
    errs = {k: v for k, v in errs.items() if v}
    return _metricas(errs)


def backtest(s: pd.Series, horizons=(1, 3, 6, 9, 12), start="2016-01-01", step: int = 1) -> pd.DataFrame:
    """Backtest de origen móvil: origen mensual desde `start` (cada `step` meses),
    ajuste con datos anteriores al origen. MAPE como fracción (0.05 = 5%)."""
    return _backtest_core(
        lambda m, t, hmax: fit_forecast(m, s[s.index < t], hmax),
        s, s.index, horizons, start, step,
    )


def backtest_equipo(monthly: pd.DataFrame, target: str, weights: pd.Series, horizons=(1, 3, 6, 9, 12),
                    start="2016-01-01", step: int = 1) -> pd.DataFrame:
    """Backtest del equipo: pronostica X, Y, Z con cada modelo y aplica los pesos.
    Los pesos se toman como dados (ajustados con toda la muestra: leve look-ahead)."""
    cols = list(MATERIAS)
    w = weights[cols]

    def forecaster(m, t, hmax):
        previo = monthly[monthly.index < t]
        fs = pd.concat({c: fit_forecast(m, previo[c], hmax) for c in cols}, axis=1)
        return fs @ w

    return _backtest_core(forecaster, monthly[target], monthly.index, horizons, start, step)


def choose_horizon(bt: pd.DataFrame, cobertura: pd.DataFrame, max_mape: float = 0.10, min_cov: float = 0.70) -> int:
    """Mayor horizonte cuyo mejor modelo (menor mape) cumple mape <= max_mape y
    cobertura P10-P90 >= min_cov; si ninguno, el menor horizonte de bt."""
    mejor = bt.groupby("horizonte")["mape"].min()
    cov = cobertura.set_index("horizonte")["cobertura"]
    ok = [h for h in mejor.index if mejor[h] <= max_mape and h in cov.index and cov[h] >= min_cov]
    return int(max(ok)) if ok else int(bt["horizonte"].min())


ESCENARIOS = {"base": {}, "choque_2022": {"X": 0.35, "Y": 0.25, "Z": 0.30}}
BLOCK = 6
_PCTS = {"p10": 10, "p25": 25, "p50": 50, "p75": 75, "p90": 90}


def simulate_paths(monthly_xyz: pd.DataFrame, h: int, n_sims: int = 5000, seed: int = SEED,
                   lookback_years: int | None = None, method: str = "bootstrap",
                   block: int = BLOCK) -> np.ndarray:
    """Caminata aleatoria en log sin deriva desde el último valor mensual observado.
    method="bootstrap": bloques móviles de retornos log mensuales (filas X,Y,Z juntas, conserva
    correlación y autocorrelación; retornos centrados para no tener deriva).
    method="normal": shocks normales multivariados con la covarianza histórica.
    `lookback_years` limita la historia usada (None = toda). Forma (n_sims, h, k)."""
    if method not in ("bootstrap", "normal"):
        raise ValueError(f"método desconocido: {method}")
    d = monthly_xyz
    if (d <= 0).any().any():
        raise ValueError("los precios deben ser positivos para trabajar en log")
    ret = np.log(d).diff().dropna()
    if lookback_years is not None:
        ret = ret.iloc[-lookback_years * 12:]
    rng = np.random.default_rng(seed)
    if method == "normal":
        cov = np.atleast_2d(ret.cov().to_numpy())
        shocks = rng.multivariate_normal(np.zeros(d.shape[1]), cov, size=(n_sims, h))
    else:
        r = ret.to_numpy() - ret.to_numpy().mean(axis=0)
        b = min(block, len(r))
        nb = -(-h // b)
        inicios = rng.integers(0, len(r) - b + 1, size=(n_sims, nb))
        idx = inicios[:, :, None] + np.arange(b)
        shocks = r[idx].reshape(n_sims, nb * b, -1)[:, :h]
    return d.iloc[-1].to_numpy(dtype=float) * np.exp(np.cumsum(shocks, axis=1))


def apply_shock(paths: np.ndarray, shock: dict[str, float]) -> np.ndarray:
    """Multiplica la trayectoria de cada materia prima por (1 + shock[m]) desde el mes 1."""
    desconocidas = set(shock) - set(MATERIAS)
    if desconocidas:
        raise ValueError(f"materias desconocidas: {sorted(desconocidas)}")
    factor = np.array([1 + shock.get(m, 0.0) for m in MATERIAS])
    return paths * factor


def equipment_fan(paths: np.ndarray, weights: pd.Series, resid_sd: float, start: str = FECHA_CASO,
                  seed: int = SEED) -> pd.DataFrame:
    """Abanico de costo del equipo: paths @ pesos con ruido relativo N(0, resid_sd)."""
    n, h, _ = paths.shape
    base = paths @ weights[list(MATERIAS)].to_numpy(dtype=float)
    eps = np.random.default_rng(seed).normal(0.0, resid_sd, size=(n, h))
    q = np.percentile(base * (1 + eps), list(_PCTS.values()), axis=0)
    idx = pd.date_range(start, periods=h, freq="MS")
    return pd.DataFrame(q.T, index=idx, columns=list(_PCTS))


def interval_coverage(monthly: pd.DataFrame, target: str, weights: pd.Series, horizons=(1, 3, 6, 9, 12),
                      start="2016-01-01", step: int = 1, n_sims: int = 1000, **sim_kw) -> pd.DataFrame:
    """Fracción de reales dentro de [P10, P90] del abanico, con origen móvil (datos < origen).
    Los pesos se toman como dados (leve look-ahead); la dispersión residual se recalcula con datos previos."""
    if pd.Timestamp(start) <= monthly.index[0]:
        raise ValueError(f"start={start} debe ser posterior al primer dato ({monthly.index[0].date()})")
    cols = list(MATERIAS)
    hmax = max(horizons)
    actual = monthly[target]
    dentro = {h: [] for h in horizons}
    for t in [t for t in monthly.index if t >= pd.Timestamp(start)][::step]:
        previo = monthly[monthly.index < t]
        sd = residual_sd(previo, target, weights)
        fan = equipment_fan(simulate_paths(previo[cols], hmax, n_sims=n_sims, **sim_kw), weights, sd, start=t)
        for h in horizons:
            fecha = t + pd.DateOffset(months=h - 1)
            if fecha in actual.index:
                dentro[h].append(bool(fan.loc[fecha, "p10"] <= actual.loc[fecha] <= fan.loc[fecha, "p90"]))
    filas = [{"horizonte": h, "cobertura": float(np.mean(v))} for h, v in dentro.items() if v]
    return pd.DataFrame(filas, columns=["horizonte", "cobertura"])


def x_out_of_sample(x_full: pd.Series, monthly: pd.DataFrame, n_sims: int = 5000) -> pd.DataFrame:
    """Simula X desde monthly (hasta 2023-08) y compara con el real 2023-09..2024-03
    (2024-04 es mes parcial y se excluye)."""
    real = to_monthly(x_full).loc["2023-09-01":"2024-03-01"]
    paths = simulate_paths(monthly[["X"]], len(real), n_sims=n_sims)[:, :, 0]
    q = np.percentile(paths, [10, 50, 90], axis=0)
    out = pd.DataFrame({"real": real.to_numpy(), "p10": q[0], "p50": q[1], "p90": q[2]}, index=real.index)
    out["dentro"] = (out["real"] >= out["p10"]) & (out["real"] <= out["p90"])
    return out
