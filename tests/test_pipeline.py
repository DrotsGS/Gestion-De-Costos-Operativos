import pandas as pd

from src.contenido import tabla_texto_oculto
from src.pipeline import build_results


def test_build_results_completo():
    r = build_results(n_sims=300, step=6)
    assert set(r.pesos) == {"Equipo1", "Equipo2"} and r.horizonte in (1, 3, 6, 9, 12)
    assert set(r.fans) == {"base", "choque_2022"}
    assert len(r.fans["base"]["Equipo1"]) == 12 and r.horizonte <= 12
    assert set(r.cobertura) == {"Equipo1", "Equipo2"}
    assert set(r.participacion) == {"Equipo1", "Equipo2"}
    assert r.participacion["Equipo1"].idxmax() == "Y" and r.participacion["Equipo2"].idxmax() == "Z"


def test_tabla_texto_oculto():
    pesos = {
        "Equipo1": pd.Series({"X": 0.9, "Y": 0.1, "Z": 0.0}),
        "Equipo2": pd.Series({"X": 0.5, "Y": 0.3, "Z": 0.2}),
    }
    t = tabla_texto_oculto(pesos).set_index("aspecto")
    assert len(t) == 5 and list(t.columns) == ["dice_texto_oculto", "muestran_datos"]
    e1 = t.loc["Equipo 1", "muestran_datos"]
    assert "90 % X" in e1 and "10 % Y" in e1 and "Z ≈ 0 %" in e1
    e2 = t.loc["Equipo 2", "muestran_datos"]
    assert "50 % X" in e2 and "30 % Y" in e2 and "20 % Z" in e2
    y = t.loc["Materia prima Y", "muestran_datos"]
    assert "10 %" in y and "30 %" in y and "mayor peso" not in y
    pesos["Equipo1"] = pd.Series({"X": 0.2, "Y": 0.8, "Z": 0.0})
    assert "mayor peso" in tabla_texto_oculto(pesos).set_index("aspecto").loc["Materia prima Y", "muestran_datos"]
    part = {"Equipo1": pd.Series({"X": 0.04, "Y": 0.96, "Z": 0.0}), "Equipo2": pd.Series({"X": 0.03, "Y": 0.2, "Z": 0.77})}
    con = tabla_texto_oculto(pesos, part).set_index("aspecto")
    assert "Pesos de la fórmula" in con.loc["Equipo 1", "muestran_datos"]
    assert "parte del costo ≈ Y 96 %" in con.loc["Equipo 1", "muestran_datos"]
    tercios = {e: pd.Series({"X": 0.332, "Y": 0.335, "Z": 0.333}) for e in pesos}
    assert "⅓" in tabla_texto_oculto(tercios).set_index("aspecto").loc["Equipo 2", "muestran_datos"]
