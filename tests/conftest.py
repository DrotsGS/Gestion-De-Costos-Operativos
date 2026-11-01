import pytest

from src.utils import load_clean_dataset, to_monthly


@pytest.fixture(scope="session")
def monthly():
    return to_monthly(load_clean_dataset().daily)
