import pandas as pd
import pytest

from src.utils import clean_series, detect_anomalies, load_clean_dataset, load_series, to_monthly


def test_atipico_z_se_corrige():
    clean, log = clean_series(load_series("Z"))
    assert len(log) == 1 and log.iloc[0]["date"] == pd.Timestamp("2014-03-25")
    assert log.iloc[0]["original"] == pytest.approx(1911.9672592592592)
    assert clean.loc["2014-03-25"] == pytest.approx(1696.75)


def test_x_y_sin_correcciones():
    for m in ("X", "Y"):
        assert clean_series(load_series(m))[1].empty


def test_eventos_reales_solo_advertencia():
    a = detect_anomalies(load_series("X"))
    fila = a[a["date"] == pd.Timestamp("2020-03-18")]
    assert len(fila) == 1 and fila.iloc[0]["accion"] == "advertir"


def test_dataset_limpio():
    d = load_clean_dataset()
    assert d.daily.loc["2014-03-25", "Z"] == pytest.approx(1696.75)
    assert len(d.correcciones) == 1 and d.x_full.index[-1] == pd.Timestamp("2024-04-04")


def test_mensual():
    m = to_monthly(load_clean_dataset().daily)
    assert m.index.freqstr == "MS" and m.index[0] == pd.Timestamp("2010-01-01") and m.index[-1] == pd.Timestamp("2023-08-01")
