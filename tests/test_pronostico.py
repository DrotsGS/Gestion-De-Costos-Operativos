import numpy as np
import pandas as pd
import pytest

from src.pronostico import MODELOS, backtest, backtest_equipo, choose_horizon, fit_forecast


def test_naive_repite_ultimo():
    s = pd.Series([1.0, 2.0, 3.0], index=pd.date_range("2020-01-01", periods=3, freq="MS"))
    f = fit_forecast("naive", s, 2)
    assert list(f) == [3.0, 3.0] and f.index[0] == pd.Timestamp("2020-04-01")


def test_sma3():
    s = pd.Series([3.0, 6.0, 9.0], index=pd.date_range("2020-01-01", periods=3, freq="MS"))
    assert fit_forecast("sma3", s, 1).iloc[0] == pytest.approx(6.0)


def test_backtest_columnas_y_error_crece(monthly):
    bt = backtest(monthly["X"], step=3)
    assert set(bt.columns) == {"modelo", "horizonte", "mape", "rmse"} and set(bt["modelo"]) == set(MODELOS)
    n = bt[bt.modelo == "naive"].set_index("horizonte")["mape"]
    assert n[12] > n[1]


def test_arima_ets_indice_y_positivos(monthly):
    for m in ("arima", "ets"):
        f = fit_forecast(m, monthly["X"], 6)
        assert len(f) == 6 and (f > 0).all() and f.index[0] == pd.Timestamp("2023-09-01")


def test_choose_horizon():
    bt = pd.DataFrame({"modelo": ["naive"] * 3, "horizonte": [1, 6, 12], "mape": [0.03, 0.08, 0.15], "rmse": [1, 2, 3]})
    cov = pd.DataFrame({"horizonte": [1, 6, 12], "cobertura": [0.82, 0.78, 0.6]})
    assert choose_horizon(bt, cov) == 6


def test_choose_horizon_ninguno_devuelve_menor():
    bt = pd.DataFrame({"modelo": ["naive"] * 2, "horizonte": [3, 6], "mape": [0.2, 0.3], "rmse": [1, 2]})
    cov = pd.DataFrame({"horizonte": [3, 6], "cobertura": [0.9, 0.9]})
    assert choose_horizon(bt, cov) == 3


@pytest.mark.parametrize("col,w", [("X", [1, 0, 0]), ("Y", [0, 1, 0])])
def test_backtest_equipo_con_pesos_unitarios_igual_backtest(monthly, col, w):
    pesos = pd.Series(w, index=["X", "Y", "Z"], dtype=float)
    m2 = monthly.assign(T=monthly[col])
    a = backtest_equipo(m2, "T", pesos, step=3).set_index(["modelo", "horizonte"]).sort_index()
    b = backtest(monthly[col], step=3).set_index(["modelo", "horizonte"]).sort_index()
    pd.testing.assert_frame_equal(a, b, atol=1e-9, rtol=0)


def test_backtest_semantica_origen_rampa():
    # rampa 1..N: con datos < t, naive predice el valor de t-1; el real en t+h-1 supera en h
    n = 60
    s = pd.Series(np.arange(1.0, n + 1), index=pd.date_range("2020-01-01", periods=n, freq="MS"))
    hs = (1, 3, 6)
    bt = backtest(s, horizons=hs, start="2022-01-01").query("modelo == 'naive'").set_index("horizonte")
    for h in hs:
        assert bt.loc[h, "rmse"] == pytest.approx(h)
        # origenes t con posicion k (1-based) de 25 a n-h+1; real = k+h-1, pronostico = k-1
        ks = np.arange(25, n - h + 2)
        assert bt.loc[h, "mape"] == pytest.approx(np.mean(h / (ks + h - 1)))


def test_start_anterior_a_datos_falla():
    s = pd.Series(np.arange(1.0, 25), index=pd.date_range("2020-01-01", periods=24, freq="MS"))
    with pytest.raises(ValueError):
        backtest(s, start="2019-01-01")


def test_precios_no_positivos_fallan_en_log():
    s = pd.Series([1.0, 0.0, 2.0, 3.0], index=pd.date_range("2020-01-01", periods=4, freq="MS"))
    with pytest.raises(ValueError):
        fit_forecast("arima", s, 1)
