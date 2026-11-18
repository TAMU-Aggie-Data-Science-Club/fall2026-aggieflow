"""Point the agent's tools at small sample passages in tests/fixtures/processed."""

from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "processed"


@pytest.fixture(autouse=True)
def sample_data(monkeypatch):
    monkeypatch.setenv("AGGIEFLOW_DATA_DIR", str(FIXTURES))
