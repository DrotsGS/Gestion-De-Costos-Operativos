import pandas as pd
import pytest

from src.negocio import CANTIDADES_EJEMPLO, budget, evaluate_quote

FAN = {"Equipo1": pd.DataFrame({"p10":[90.0],"p25":[95.0],"p50":[100.0],"p75":[105.0],"p90":[110.0]}, index=pd.DatetimeIndex(["2023-09-01"]))}


def test_cotizacion_cara():
    v = evaluate_quote(FAN, "Equipo1", "2023-09", 115.0)
    assert v.ok and v.pct_vs_p50 == pytest.approx(0.15) and v.sobre_p90


def test_cotizacion_mes_fuera_de_horizonte():
    v = evaluate_quote(FAN, "Equipo1", "2030-01", 100.0)
    assert not v.ok and "horizonte" in v.mensaje


def test_cotizacion_precio_invalido_y_equipo_inexistente():
    assert not evaluate_quote(FAN, "Equipo1", "2023-09", 0).ok
    assert not evaluate_quote(FAN, "Equipo3", "2023-09", 100).ok


def test_cotizacion_entradas_raras_no_lanzan():
    for precio in (float("nan"), "abc", None, -5, float("inf")):
        assert not evaluate_quote(FAN, "Equipo1", "2023-09", precio).ok
    assert not evaluate_quote(FAN, "Equipo1", "basura", 100.0).ok


def test_cotizacion_barata_y_en_rango():
    v = evaluate_quote(FAN, "Equipo1", "2023-09", 90.0)
    assert v.ok and not v.sobre_p90 and v.pct_vs_p50 == pytest.approx(-0.10)
    v = evaluate_quote(FAN, "Equipo1", "2023-09", 105.0)
    assert v.ok and not v.sobre_p90 and v.precio_justo == 100.0


def test_presupuesto_reserva():
    cant = pd.DataFrame({"fase":["F1"],"mes":["2023-09"],"Equipo1":[10],"Equipo2":[0]})
    b = budget(FAN | {"Equipo2": FAN["Equipo1"]}, cant)
    assert b.loc["F1","p50"] == 1000 and b.loc["F1","reserva"] == 100 and b.loc["F1","total"] == 1100


def test_presupuesto_cantidades_cero():
    cant = pd.DataFrame({"fase":["F1"],"mes":["2023-09"],"Equipo1":[0],"Equipo2":[0]})
    assert budget(FAN | {"Equipo2": FAN["Equipo1"]}, cant).loc["F1","total"] == 0


def test_presupuesto_suma_filas_misma_fase_y_errores():
    fans = FAN | {"Equipo2": FAN["Equipo1"]}
    cant = pd.DataFrame({"fase":["F1","F1"],"mes":["2023-09","2023-09"],"Equipo1":[1,2],"Equipo2":[0,0]})
    b = budget(fans, cant)
    assert len(b) == 1 and b.index.name == "fase" and b.loc["F1","total"] == 330
    with pytest.raises(ValueError, match="horizonte"):
        budget(fans, cant.assign(mes="2030-01"))
    with pytest.raises(ValueError, match="Equipo3"):
        budget(fans, cant.assign(Equipo3=1))


def test_cantidades_ejemplo():
    assert list(CANTIDADES_EJEMPLO.columns) == ["fase", "mes", "Equipo1", "Equipo2"]
    assert len(CANTIDADES_EJEMPLO) == 3
