import numpy as np
import pandas as pd
import pytest

from src.pronostico import (ESCENARIOS, apply_shock, equipment_fan, interval_coverage, simulate_paths,
                            x_out_of_sample)
from src.relacion import fit_constrained
from src.utils import load_clean_dataset


def test_forma_y_semilla(monthly):
    a = simulate_paths(monthly[["X", "Y", "Z"]], 6, n_sims=200)
    b = simulate_paths(monthly[["X", "Y", "Z"]], 6, n_sims=200)
    assert a.shape == (200, 6, 3) and np.array_equal(a, b)


def test_abanico_ordenado_y_se_abre(monthly):
    w = pd.Series({"X": 0.2, "Y": 0.8, "Z": 0.0})
    f = equipment_fan(simulate_paths(monthly[["X", "Y", "Z"]], 12), w, 0.018)
    assert f.index[0] == pd.Timestamp("2023-09-01") and len(f) == 12
    assert (f["p10"] <= f["p50"]).all() and (f["p50"] <= f["p90"]).all()
    assert (f["p90"] - f["p10"]).iloc[-1] > (f["p90"] - f["p10"]).iloc[0]


def test_choque_sube_p50(monthly):
    p = simulate_paths(monthly[["X", "Y", "Z"]], 6)
    w = pd.Series({"X": 0.2, "Y": 0.8, "Z": 0.0})
    assert equipment_fan(apply_shock(p, {"Y": 0.25}), w, 0.018)["p50"].iloc[0] > equipment_fan(p, w, 0.018)["p50"].iloc[0]


def test_fuera_de_muestra_x(monthly):
    d = load_clean_dataset()
    o = x_out_of_sample(d.x_full, monthly)
    assert o.index[0] == pd.Timestamp("2023-09-01") and o.index[-1] == pd.Timestamp("2024-03-01") and "dentro" in o
    assert len(o) == 7 and o["dentro"].dtype == bool


def test_choque_desconocido_falla(monthly):
    p = simulate_paths(monthly[["X", "Y", "Z"]], 2, n_sims=10)
    with pytest.raises(ValueError):
        apply_shock(p, {"W": 0.1})
    assert ESCENARIOS["base"] == {}


def test_cobertura_columnas(monthly):
    w = fit_constrained(monthly, "Equipo1")
    c = interval_coverage(monthly, "Equipo1", w, horizons=(1, 12), start="2016-01-01", step=3, n_sims=500)
    assert list(c.columns) == ["horizonte", "cobertura"] and list(c["horizonte"]) == [1, 12]
    assert c["cobertura"].between(0, 1).all()
    with pytest.raises(ValueError):
        interval_coverage(monthly, "Equipo1", w, start=str(monthly.index[0].date()))


def test_metodos_bootstrap_y_normal(monthly):
    m3 = monthly[["X", "Y", "Z"]]
    a = simulate_paths(m3, 12, n_sims=100, method="bootstrap", block=3)
    b = simulate_paths(m3, 12, n_sims=100, method="bootstrap", block=3)
    n = simulate_paths(m3, 12, n_sims=100, method="normal")
    assert a.shape == n.shape == (100, 12, 3) and np.array_equal(a, b)
    assert not np.array_equal(a, n)
    with pytest.raises(ValueError):
        simulate_paths(m3, 3, method="otro")
