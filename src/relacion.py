"""Relación entre materias primas (X, Y, Z) y precios de equipos."""
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.optimize import minimize
from statsmodels.stats.outliers_influence import variance_inflation_factor
from statsmodels.tsa.stattools import coint

from src.config import MATERIAS

_COLS = list(MATERIAS)


def fit_ols(monthly: pd.DataFrame, target: str) -> dict:
    """OLS de target sobre const + X, Y, Z, con p-valores, R² y VIF."""
    Xd = sm.add_constant(monthly[_COLS])
    res = sm.OLS(monthly[target], Xd).fit()
    vif = pd.Series(
        [variance_inflation_factor(Xd.values, i + 1) for i in range(len(_COLS))],
        index=_COLS,
    )
    return {"coef": res.params, "pvalues": res.pvalues, "r2": float(res.rsquared), "vif": vif}


def _pesos_restringidos(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Mínimos cuadrados con w >= 0, sum(w) = 1, sin intercepto."""
    n = X.shape[1]
    # se escala por el precio medio (mismo minimizador) para que SLSQP converja
    esc = y.mean()
    X, y = X / esc, y / esc
    r = minimize(
        lambda w: np.sum((y - X @ w) ** 2),
        np.full(n, 1 / n),
        method="SLSQP",
        options={"ftol": 1e-12, "maxiter": 500},
        bounds=[(0, 1)] * n,
        constraints=[{"type": "eq", "fun": lambda w: w.sum() - 1}],
    )
    if not r.success:
        raise RuntimeError(f"SLSQP no convergió: {r.message}")
    return r.x


def fit_constrained(monthly: pd.DataFrame, target: str) -> pd.Series:
    w = _pesos_restringidos(monthly[_COLS].to_numpy(), monthly[target].to_numpy())
    return pd.Series(w, index=_COLS)


def residual_sd(monthly: pd.DataFrame, target: str, weights: pd.Series) -> float:
    """RMS del residuo relativo al precio (fracción); incluye sesgo y dispersión."""
    fitted = monthly[_COLS] @ weights[_COLS]
    rel = (monthly[target] - fitted) / monthly[target]
    return float(np.sqrt((rel**2).mean()))


def cointegration(monthly: pd.DataFrame, target: str, weights: pd.Series) -> dict:
    """Engle-Granger entre el equipo y su combinación lineal de materias primas."""
    fitted = monthly[_COLS] @ weights[_COLS]
    stat, p, _ = coint(monthly[target], fitted)
    return {"pvalue": float(p), "estadistico": float(stat)}


def rolling_weights(monthly: pd.DataFrame, target: str, window: int = 36) -> pd.DataFrame:
    """Pesos restringidos en ventanas móviles; índice = mes final de la ventana."""
    X = monthly[_COLS].to_numpy()
    y = monthly[target].to_numpy()
    idx = monthly.index[window - 1:]
    filas = [_pesos_restringidos(X[i - window + 1:i + 1], y[i - window + 1:i + 1])
             for i in range(window - 1, len(monthly))]
    return pd.DataFrame(filas, index=idx, columns=_COLS)


def lag_analysis(monthly: pd.DataFrame, target: str, max_lag: int = 3) -> pd.DataFrame:
    """R² de target_t sobre materias primas rezagadas 0..max_lag meses."""
    filas = []
    for lag in range(max_lag + 1):
        Xl = monthly[_COLS].shift(lag)
        d = pd.concat([monthly[target], Xl], axis=1, keys=["y", "x"]).dropna()
        res = sm.OLS(d["y"], sm.add_constant(d["x"])).fit()
        filas.append({"lag": lag, "r2": float(res.rsquared)})
    return pd.DataFrame(filas)


def participacion_costo(monthly: pd.DataFrame, pesos: pd.Series, meses: int = 12) -> pd.Series:
    """Parte del costo que aporta cada materia (peso·precio / costo), promedio de los últimos `meses`.

    Los pesos multiplican precios de escalas muy distintas, así que no son participaciones.
    """
    aporte = monthly[_COLS].tail(meses) * pesos[_COLS]
    part = aporte.div(aporte.sum(axis=1), axis=0).mean()
    return part / part.sum()
