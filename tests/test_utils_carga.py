import pandas as pd
import pytest

from src.utils import load_historico, load_series


def test_load_x_orden_y_rango():
    s = load_series("X")
    assert s.index.is_monotonic_increasing
    assert s.index[0] == pd.Timestamp("1988-06-27") and s.index[-1] == pd.Timestamp("2024-04-04")
    assert len(s) == 9144 and s.iloc[-1] == 89.18


def test_load_y_formato_europeo():  # ';', coma decimal, d/m/aaaa, BOM
    s = load_series("Y")
    assert s.loc["2023-09-12"] == 547.33
    assert s.index[0] == pd.Timestamp("2006-07-11") and len(s) == 4485


def test_load_z_columnas_invertidas():
    s = load_series("Z")
    assert s.loc["2010-01-04"] == 2225.25 and len(s) == 3565


def test_historico_columnas_y_largo():
    h = load_historico()
    assert list(h.columns) == ["X", "Y", "Z", "Equipo1", "Equipo2"] and len(h) == 3530


def test_series_coinciden_con_historico():
    h = load_historico()
    for m in ("X", "Y", "Z"):
        s = load_series(m).reindex(h.index)
        assert (s - h[m]).abs().max() < 1e-9


def test_carga_independiente_del_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert len(load_historico()) == 3530


def test_nombre_invalido():
    with pytest.raises(ValueError):
        load_series("W")
