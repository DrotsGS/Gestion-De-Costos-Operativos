"""Pruebas de noticias con un fetch falso (sin red)."""
import pytest

from src import noticias
from src.noticias import buscar_noticias

RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>x</title>
<item><title>Acero sube en China - Reuters</title><link>http://a/1</link>
<pubDate>Mon, 02 Jan 2023 10:00:00 GMT</pubDate><source url="http://r">Reuters</source></item>
<item><title>Aluminio cae - Otra fuente</title><link>http://a/2</link>
<pubDate>Wed, 04 Jan 2023 08:00:00 GMT</pubDate><source url="http://b">Bloomberg</source></item>
<item><title>Hierro estable</title><link>http://a/3</link>
<pubDate>Tue, 03 Jan 2023 09:00:00 GMT</pubDate><source url="http://c">La República</source></item>
</channel></rss>"""


@pytest.fixture(autouse=True)
def _limpia_cache():
    noticias._cache.clear()
    yield
    noticias._cache.clear()


def fake(contenido=RSS):
    llamadas = []

    def f(url):
        llamadas.append(url)
        return contenido
    f.llamadas = llamadas
    return f


def test_parseo_orden_y_limpieza():
    f = fake()
    out = buscar_noticias("precio acero", fetch=f)
    assert out["fuente"] == "Google News (RSS)" and out["consulta"] == "precio acero"
    assert [n["fecha"] for n in out["noticias"]] == ["2023-01-04", "2023-01-03", "2023-01-02"]
    t = {n["fuente"]: n for n in out["noticias"]}
    assert t["Reuters"]["titulo"] == "Acero sube en China" and t["Reuters"]["enlace"] == "http://a/1"
    assert t["Bloomberg"]["titulo"] == "Aluminio cae - Otra fuente"  # el sufijo no coincide con la fuente
    assert "q=precio+acero" in f.llamadas[0] and "hl=es-419" in f.llamadas[0]


def test_max_items():
    assert len(buscar_noticias("a", max_items=2, fetch=fake())["noticias"]) == 2
    assert len(buscar_noticias("b", max_items=99, fetch=fake())["noticias"]) == 3
    assert len(buscar_noticias("c", max_items=0, fetch=fake())["noticias"]) == 1


def test_errores_nunca_lanza():
    assert "error" in buscar_noticias("x", fetch=fake("no es xml"))

    def cae(url):
        raise OSError("sin red")
    assert "error" in buscar_noticias("y", fetch=cae)
    for vacia in ("", "   ", None):
        assert "error" in buscar_noticias(vacia, fetch=fake())


def test_cache_reutiliza_y_expira(monkeypatch):
    f = fake()
    a = buscar_noticias("acero", fetch=f)
    b = buscar_noticias("Acero", fetch=f)
    assert a == b and len(f.llamadas) == 1
    t0 = noticias.time.monotonic()
    monkeypatch.setattr(noticias.time, "monotonic", lambda: t0 + noticias.TTL_SEGUNDOS + 1)
    buscar_noticias("acero", fetch=f)
    assert len(f.llamadas) == 2


def test_error_no_se_cachea():
    f = fake("roto")
    buscar_noticias("z", fetch=f)
    buscar_noticias("z", fetch=f)
    assert len(f.llamadas) == 2
