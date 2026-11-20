"""Point the agent's tools at small sample data, so tests need no network.

- Searches and course lookups read tests/fixtures/processed/<source>.jsonl.
- anex.us grades, normally fetched live, come from tests/fixtures/anex/<DEPT>-<NUM>.json.
- RateMyProfessors searches, normally fetched live, come from tests/fixtures/ratemyprofessors/<name>.json.
"""

import json
from pathlib import Path

import pytest

from agent import data

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _fake_anex(dept, number):
    path = FIXTURES / "anex" / f"{dept}-{number}.json"
    return path.read_text(encoding="utf-8") if path.exists() else '{"classes":]}'


def _fake_rmp(name):
    path = FIXTURES / "ratemyprofessors" / f"{name}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"data": {"newSearch": {"teachers": {"edges": []}}}}


@pytest.fixture(autouse=True)
def sample_data(monkeypatch):
    monkeypatch.setenv("AGGIEFLOW_DATA_DIR", str(FIXTURES / "processed"))  # files, never Atlas
    monkeypatch.setattr(data, "_fetch_anex", _fake_anex)
    data._anex_cache.clear()
    monkeypatch.setattr(data, "_fetch_rmp", _fake_rmp)
    data._rmp_cache.clear()
