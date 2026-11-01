import pandas as pd

from src.auditoria import audit, flat_runs
from src.utils import load_historico


def test_tramos_planos_y():
    r = flat_runs(load_historico()["Y"])
    assert len(r) == 282 and r["largo"].max() == 35


def test_ids_hallazgos():
    ids = {h.id for h in audit()}
    assert ids == {"texto_oculto_pdf", "atipico_z", "tramos_planos_y", "formatos",
                   "fechas_desalineadas", "correlacion_enganosa", "integridad", "advertencias_eventos"}


def test_fechas_fin():
    h = next(h for h in audit() if h.id == "fechas_desalineadas")
    fines = dict(zip(h.evidencia["serie"], h.evidencia["fin"]))
    assert fines["X"] == pd.Timestamp("2024-04-04") and fines["Y"] == pd.Timestamp("2023-09-12")
