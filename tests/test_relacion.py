import pytest

from src.relacion import cointegration, fit_constrained, fit_ols, lag_analysis, residual_sd, participacion_costo, rolling_weights


def test_pesos_equipo1(monthly):
    w = fit_constrained(monthly, "Equipo1")
    assert w["Y"] == pytest.approx(0.80, abs=0.03) and w["X"] == pytest.approx(0.20, abs=0.03) and w["Z"] < 0.03


def test_pesos_equipo2(monthly):
    w = fit_constrained(monthly, "Equipo2")
    for m in "XYZ":
        assert w[m] == pytest.approx(1 / 3, abs=0.03)


def test_z_no_significativa_equipo1(monthly):
    assert fit_ols(monthly, "Equipo1")["pvalues"]["Z"] > 0.05


def test_cointegracion(monthly):
    for e in ("Equipo1", "Equipo2"):
        assert cointegration(monthly, e, fit_constrained(monthly, e))["pvalue"] < 0.05


def test_pesos_estables(monthly):
    rw = rolling_weights(monthly, "Equipo1")
    assert (rw["Y"] - 0.8).abs().max() < 0.15


def test_pesos_restringidos_invariantes(monthly):
    for e in ("Equipo1", "Equipo2"):
        w = fit_constrained(monthly, e)
        assert list(w.index) == ["X", "Y", "Z"]
        assert w.sum() == pytest.approx(1.0, abs=1e-6)
        assert (w >= -1e-9).all()


def test_lag_analysis(monthly):
    la = lag_analysis(monthly, "Equipo1", max_lag=3)
    assert list(la.columns) == ["lag", "r2"]
    assert list(la["lag"]) == [0, 1, 2, 3]
    assert la["r2"].iloc[0] >= la["r2"].iloc[-1]


def test_residual_sd(monthly):
    sd = residual_sd(monthly, "Equipo1", fit_constrained(monthly, "Equipo1"))
    assert 0 < sd < 0.02


def test_participacion_costo(monthly):
    p1 = participacion_costo(monthly, fit_constrained(monthly, "Equipo1"))
    p2 = participacion_costo(monthly, fit_constrained(monthly, "Equipo2"))
    assert p1["Y"] > 0.9 and p2["Z"] > 0.7
    for p in (p1, p2):
        assert list(p.index) == ["X", "Y", "Z"] and p.sum() == pytest.approx(1.0)
