"""Point the agent's tools at small sample data, so tests need no network.

- Searches and course lookups read tests/fixtures/processed/<source>.jsonl.
- anex.us grades, normally fetched live, come from tests/fixtures/anex/<DEPT>-<NUM>.json.
- RateMyProfessors searches, normally fetched live, come from tests/fixtures/ratemyprofessors/<name>.json.
- Library hours and Tech Bar equipment, normally fetched live from LibCal, come from
  tests/fixtures/libcal/, and "today" is Sunday, Nov 22, 2026, the day they were recorded.
"""

import json
from datetime import date
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


def _fake_libcal(url, params):
    if url == data.LIBCAL_HOURS_URL:
        return json.loads((FIXTURES / "libcal" / "hours.json").read_text(encoding="utf-8"))
    name = f"{params['lid']}-{params['gid']}" + (f"-{params['q'].lower()}" if params.get("q") else "")
    path = FIXTURES / "libcal" / "equipment" / f"{name}.json"
    feed = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"results": [], "total_results": 0}
    start = (params["page"] - 1) * params["perpage"]  # LibCal's paging
    return {**feed, "results": feed["results"][start:start + params["perpage"]], "perpage": params["perpage"]}


@pytest.fixture(autouse=True)
def sample_data(monkeypatch):
    monkeypatch.setenv("AGGIEFLOW_DATA_DIR", str(FIXTURES / "processed"))  # files, never Atlas
    monkeypatch.setattr(data, "_fetch_anex", _fake_anex)
    data._anex_cache.clear()
    monkeypatch.setattr(data, "_fetch_rmp", _fake_rmp)
    data._rmp_cache.clear()
    monkeypatch.setattr(data, "_fetch_libcal", _fake_libcal)
    monkeypatch.setattr(data, "campus_today", lambda: date(2026, 11, 22))
    data._libcal_cache.clear()
