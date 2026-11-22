"""Tests for api/main.py. The agent is replaced with a fake, so no model calls."""

import pytest
from fastapi.testclient import TestClient

import api.main

URL = "https://student-rules.tamu.edu/rule01/"
PASSAGE = {"id": "student-rules:rule01:0", "source": "student-rules", "title": "Rule 1",
           "text": "...", "source_url": URL}


def fake_answer(question, history=None, metadata=None):
    return {
        "answer": f"Four ({URL}).\n\nSources:\n- {URL}",
        "sources": [PASSAGE, PASSAGE],
        "documents": [PASSAGE],
        "trace": [["search_student_rules"]],
        "calls": [{"round": 1, "name": "search_student_rules", "args": {}, "error": None},
                  {"round": 2, "name": "search_student_rules", "args": {}, "error": None}],
    }


@pytest.fixture
def client():
    return TestClient(api.main.app)


def test_health(client):
    assert client.get("/health").json() == {"ok": True}


def test_chat(client, monkeypatch):
    monkeypatch.setattr(api.main, "answer", fake_answer)
    r = client.post("/chat", json={"question": "how many q drops do i get"})
    assert r.status_code == 200
    assert r.json() == {
        "answer": f"Four ({URL}).",
        "sources": [{"title": "Rule 1", "source_url": URL, "source": "student-rules"}],
        "tools": ["search_student_rules"],
    }


def test_chat_passes_history(client, monkeypatch):
    got = {}

    def spy(question, history=None, metadata=None):
        got["history"] = history
        return fake_answer(question)

    monkeypatch.setattr(api.main, "answer", spy)
    history = [{"role": "user", "content": "how many q drops do i get"},
               {"role": "assistant", "content": "Four."}]
    client.post("/chat", json={"question": "can i use one in summer?", "history": history})
    assert got["history"] == history


@pytest.mark.parametrize("body", [
    {"question": ""},
    {"question": "x" * 1001},
    {"question": "hi", "history": [{"role": "ai", "content": "hello"}]},
    {"question": "hi", "history": [{"role": "user", "content": "hi"}] * 21},
])
def test_chat_bad_request(client, body):
    assert client.post("/chat", json=body).status_code == 422


def test_chat_agent_error(client, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("rate limit")

    monkeypatch.setattr(api.main, "answer", boom)
    r = client.post("/chat", json={"question": "hi"})
    assert r.status_code == 503
    assert "rate limit" not in r.text
