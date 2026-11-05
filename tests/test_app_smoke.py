"""Pruebas de humo de la app Streamlit y de las funciones de gráficos."""
import json

import pandas as pd
import plotly.graph_objects as go
import pytest
from streamlit.testing.v1 import AppTest

from app import graficos
from app.estilo import fmt_es, fmt_pct
from src.config import ROOT
from src.contenido import TEXTO_OCULTO_RESUMEN

MAIN = str(ROOT / "app" / "main.py")


@pytest.fixture
def rapido(monkeypatch):
    monkeypatch.setenv("APP_RAPIDO", "1")


def _texto(at) -> str:
    return "\n".join([m.value for m in at.markdown] + [c.value for c in at.caption]
                     + [e.value for e in at.error] + [w.value for w in at.warning] + [i.value for i in at.info])


def _pagina(at) -> str:
    """Texto de la columna de contenido (sin el panel del agente)."""
    c = at.columns[0]
    return "\n".join([m.value for m in c.markdown] + [x.value for x in c.caption] + [i.value for i in c.info])


def test_app_arranca_sin_errores(rapido):
    at = AppTest.from_file(MAIN, default_timeout=120).run()
    assert not at.exception


def test_resumen_lenguaje_de_negocio(rapido):
    at = AppTest.from_file(MAIN, default_timeout=120).run()
    assert not at.exception
    etiquetas = [m.label for m in at.metric]
    assert sum(e.startswith("Costo esperado") for e in etiquetas) == 4
    assert "Reserva recomendada" in etiquetas
    assert all(m.value and m.value != "nan" for m in at.metric)
    txt = _pagina(at)
    for jerga in ("cobertura", "p-value", "p-valor", "mape"):
        assert jerga not in txt.lower()
    assert "de cada 10 veces" in txt and "Un alza de 10 %" in txt
    assert "8 de cada 10" in txt and "cada trimestre" in txt and "acero" in txt and "aluminio" in txt


def test_navegacion_dos_secciones():
    from app.layout import PAGINAS, SECCIONES
    assert list(SECCIONES) == ["🏢 Para el cliente", "🔧 Detrás del análisis"]
    assert [p[0] for p in SECCIONES["🏢 Para el cliente"]] == ["resumen", "proyecciones", "presupuesto"]
    assert "validacion" in [p[0] for p in SECCIONES["🔧 Detrás del análisis"]]
    assert PAGINAS["resumen"] == "Resumen ejecutivo · sección cliente"
    assert PAGINAS["validacion"] == "Validación de modelos · sección análisis"


def test_pagina_calidad_contenido(rapido):
    at = AppTest.from_file(MAIN, default_timeout=120).run()
    at.switch_page("paginas/calidad.py").run()
    assert not at.exception
    assert len(at.error) >= 1  # hallazgo de severidad alta
    assert TEXTO_OCULTO_RESUMEN in _texto(at)
    cols = [tuple(d.value.columns) for d in at.dataframe]
    assert ("Aspecto", "Dice el texto oculto", "Muestran los datos") in cols  # tabla texto oculto
    assert ("Inicio", "Fin", "Días", "Valor") in cols  # tramos planos de Y
    assert ("Z original", "Z corregido") in cols  # tabla gemela del gráfico de Z
    assert any(e.label == "Ver tabla" for e in at.expander)


def test_grafico_z_en_pagina_calidad(rapido):
    at = AppTest.from_file(MAIN, default_timeout=120).run()
    at.switch_page("paginas/calidad.py").run()
    graficos_z = at.get("plotly_chart")
    assert len(graficos_z) == 1
    spec = json.loads(graficos_z[0].proto.spec)["layout"]["title"]["text"]
    assert "→" in spec and "corregido por interpolación" in spec  # título derivado del log de correcciones


def _abanico():
    idx = pd.date_range("2023-09-01", periods=12, freq="MS")
    return pd.DataFrame({c: range(12) for c in ("p10", "p25", "p50", "p75", "p90")}, index=idx)


def test_fig_serie_con_atipico():
    idx = pd.date_range("2014-02-01", periods=60, freq="D")
    crudo = pd.Series(range(60), index=idx, dtype=float)
    fig = graficos.fig_serie_con_atipico(crudo, crudo + 1, idx[10], "Z", tema="dark")
    assert isinstance(fig, go.Figure) and len(fig.data) == 3
    assert "Dato corregido: 10,00 → 11,00" in fig.layout.annotations[0].text


def test_fig_abanico():
    fig = graficos.fig_abanico(_abanico(), horizonte=3, titulo="t", cobertura=0.7)
    # 2 bandas x (confiable + referencial) x 2 trazas + P50 + P50 punteado + traza de tooltip
    assert isinstance(fig, go.Figure) and len(fig.data) == 11
    assert any("70 %" in (tr.name or "") for tr in fig.data)
    assert len(graficos.fig_abanico(_abanico(), horizonte=12, titulo="t", cobertura=0.7, tema="dark").data) == 6


def test_fig_pesos():
    fig = graficos.fig_pesos(pd.Series({"X": .1, "Y": .8, "Z": .1}), "t")
    assert isinstance(fig, go.Figure) and len(fig.data) == 1
    assert len(fig.data[0].x) == 3
    assert list(fig.data[0].text) == ["10,0 %", "80,0 %", "10,0 %"]


def test_fig_pesos_moviles():
    idx = pd.date_range("2010-01-01", periods=10, freq="MS")
    df = pd.DataFrame({"X": .2, "Y": .5, "Z": .3}, index=idx)
    fig = graficos.fig_pesos_moviles(df, "t")
    assert isinstance(fig, go.Figure) and len(fig.data) == 3


def test_formato_es():
    assert fmt_es(1911.97) == "1.911,97"
    assert fmt_pct(0.8) == "80,0 %"


def _ir(pagina: str):
    at = AppTest.from_file(MAIN, default_timeout=120).run()
    at.switch_page(f"paginas/{pagina}.py").run()
    assert not at.exception
    return at


def test_pagina_relacion(rapido):
    at = _ir("relacion")
    assert len(at.get("plotly_chart")) == 2  # pesos y pesos móviles
    assert sum(e.label == "Ver tabla" for e in at.expander) == 2
    assert any(e.label.startswith("Investigación propia") for e in at.expander)
    cols = [tuple(d.value.columns) for d in at.dataframe]
    assert ("Materia prima", "Correlación en niveles", "Peso de la fórmula", "Parte del costo") in cols
    assert any("Coeficiente" in c and "VIF" in c for c in cols)  # tabla OLS
    assert "escalas muy distintas" in _texto(at)
    assert any(m.label.startswith("p-valor de cointegración") for m in at.metric)


def test_pagina_proyecciones_cliente(rapido):
    at = _ir("proyecciones")
    assert len(at.get("plotly_chart")) == 1  # solo el abanico
    assert sum(e.label == "Ver tabla" for e in at.expander) == 1
    assert not [d for d in at.dataframe if "Nominal" in getattr(d.value, "columns", [])]
    txt = _pagina(at)
    assert "MAPE" not in txt and "cobertura" not in txt.lower()
    assert "Lo más probable" in txt and "8 de cada 10" in txt


def test_pagina_validacion(rapido):
    at = _ir("validacion")
    assert len(at.get("plotly_chart")) == 1  # X fuera de muestra
    cols = [tuple(d.value.columns) for d in at.dataframe if hasattr(d.value, "columns")]
    assert ("Horizonte (m)", "Nominal", "Empírica", "Brecha") in cols
    txt = _texto(at)
    assert "MAPE" in txt and "Por qué" in txt and "caminata aleatoria" in txt and "pp" in txt
    assert "bootstrap por bloques" in txt
    titulo = json.loads(at.get("plotly_chart")[0].proto.spec)["layout"]["title"]["text"]
    assert " de 7 meses" in titulo


def test_pagina_presupuesto_veredicto(rapido):
    at = _ir("presupuesto")
    assert any(m.label == "Total a aprobar" for m in at.metric)
    assert len(at.dataframe) >= 1
    at.number_input[0].set_value(100000.0)
    at.button[0].click().run()
    assert not at.exception
    txt = _texto(at)
    assert "precio justo" in txt and "1,8 %" in txt
    assert "Sobre el P90" in txt  # 100.000 supera cualquier P90 del Equipo 1


def test_validacion_presupuesto():
    from src.negocio import validar_cantidades as validar
    from src.negocio import CANTIDADES_EJEMPLO
    meses = {"2023-10", "2024-01", "2024-04"}
    assert validar(CANTIDADES_EJEMPLO, meses) == []
    malo = CANTIDADES_EJEMPLO.copy()
    malo.loc[0, "mes"] = "2030-01"
    malo.loc[1, "Equipo1"] = -3
    assert len(validar(malo, meses)) == 2


def test_fig_x_oos():
    idx = pd.date_range("2023-09-01", periods=7, freq="MS")
    df = pd.DataFrame({"real": 1.0, "p10": 0.5, "p50": 1.0, "p90": 1.5, "dentro": True}, index=idx)
    assert len(graficos.fig_x_oos(df, "t").data) == 4
    df.loc[idx[0], ["real", "dentro"]] = [9.0, False]
    assert len(graficos.fig_x_oos(df, "t", tema="dark").data) == 5


@pytest.mark.parametrize("factor,esperado", [(1.001, "Sobre el P50"), (0.9, "Cotización favorable")])
def test_veredicto_ramas_warning_y_favorable(rapido, factor, esperado):
    from src.pipeline import build_results
    fan = build_results(step=6, n_sims=300).fans["base"]["Equipo1"]
    at = _ir("presupuesto")
    at.selectbox[1].select(f"{fan.index[0]:%Y-%m}")
    at.number_input[0].set_value(float(fan["p50"].iloc[0] * factor))
    at.button[0].click().run()
    assert not at.exception and esperado in _texto(at)


def test_relacion_advierte_correlacion_enganosa(rapido):
    txt = _texto(_ir("relacion"))
    assert "por coincidencia" in txt and "Z (probable: aluminio)" in txt


def test_pagina_metodologia(rapido):
    from src.contenido import IA_VS_AGENTE
    at = _ir("metodologia")
    assert len(at.get("image")) == 0 and len(at.dataframe) == 0
    txt = _texto(at)
    assert IA_VS_AGENTE.splitlines()[0] in txt
    assert "streamlit run app/main.py" in txt
    assert "AWS" not in txt


def test_metodologia_local_sin_barra_suelta():
    from app.paginas.metodologia import LOCAL
    assert LOCAL.startswith("```bash") and not LOCAL.startswith("\\")
    assert "\n\\n" not in LOCAL
