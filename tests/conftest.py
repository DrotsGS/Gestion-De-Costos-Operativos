import os

import pytest

from src.utils import load_clean_dataset, to_monthly


@pytest.fixture(scope="session")
def monthly():
    return to_monthly(load_clean_dataset().daily)


@pytest.fixture(autouse=True)
def _sin_secretos_reales(monkeypatch):
    """Las claves salen solo del entorno: nunca de un .streamlit/secrets.toml real."""
    from app import layout
    monkeypatch.setattr(layout, "_secreto", lambda nombre: os.environ.get(nombre) or None)
