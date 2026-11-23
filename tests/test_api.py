"""Tests for api/main.py. The agent is replaced with a fake, so no model calls."""

import uuid

import pytest
from fastapi.testclient import TestClient

import api.main

URL = "https://student-rules.tamu.edu/rule01/"
PASSAGE = {"id": "student-rules:rule01:0", "source": "student-rules", "title": "Rule 1",
           "text": "...", "source_url": URL}


def fake_answer(question, history=None, metadata=None, thread_id=None):
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
    body = r.json()
    assert uuid.UUID(body.pop("thread_id"))  # a new conversation gets an id
    assert body == {
        "answer": f"Four ({URL}).",
        "sources": [{"title": "Rule 1", "source_url": URL, "source": "student-rules"}],
        "tools": ["search_student_rules"],
        "steps": [{"name": "search_student_rules", "args": {}, "error": None}] * 2,
        "grades": [],
        "question": None,
    }


def test_chat_continues_the_thread_it_is_given(client, monkeypatch):
    seen = []
    monkeypatch.setattr(api.main, "answer", lambda q, **kw: seen.append(kw["thread_id"]) or fake_answer(q))
    thread = str(uuid.uuid4())
    assert client.post("/chat", json={"question": "and summer?", "thread_id": thread}).json()["thread_id"] == thread
    assert seen == [thread]


def test_chat_rejects_a_thread_id_that_is_not_a_uuid(client, monkeypatch):
    monkeypatch.setattr(api.main, "answer", fake_answer)
    assert client.post("/chat", json={"question": "hi", "thread_id": "../other"}).status_code == 422


def grade_answer(question, history=None, metadata=None, thread_id=None):
    calls = [
        {"round": 1, "name": "get_course_grades", "args": {"course": "CHEM 107"}, "error": False},
        {"round": 2, "name": "get_professor_grades", "args": {"course": "chem107", "professor": "hall"}, "error": False},
        {"round": 2, "name": "get_course_grades", "args": {"course": "MATH 151"}, "error": True},
        {"round": 2, "name": "get_course_grades", "args": {"course": "not a course"}, "error": False},
    ]
    return {**fake_answer(question), "calls": calls}


def test_chat_returns_a_grade_chart_per_course_looked_up(client, monkeypatch):
    monkeypatch.setattr(api.main, "answer", grade_answer)
    grades = client.post("/chat", json={"question": "who's easiest for chem 107"}).json()["grades"]
    # CHEM 107 once, nothing for the professor lookup, the failed call or the bad course code
    assert [g["course"] for g in grades] == ["CHEM 107"]
    chart = grades[0]
    assert (chart["since"], chart["min_students"]) == (2023, 30)
    assert chart["source_url"] == "https://anex.us/grades/?dept=CHEM&number=107"
    # the same professors, order and GPAs as get_course_grades' ranking: "MARTINEZ Z 3.20 ...; HALL M 3.09"
    assert [(p["name"], p["gpa"]) for p in chart["professors"]] == [("MARTINEZ Z", 3.2), ("HALL M", 3.09)]
    assert chart["professors"][0]["counts"] == {"A": 40, "B": 30, "C": 10, "D": 2, "F": 3, "Q": 2}


def test_a_professor_lookup_makes_no_grade_chart(client, monkeypatch):
    # get_professor_grades answers with all-time numbers; the chart is since 2023, so they'd disagree
    def professor_only(question, history=None, metadata=None, thread_id=None):
        calls = [{"round": 1, "name": "get_professor_grades", "args": {"course": "CHEM 107", "professor": "hall"}, "error": False}]
        return {**fake_answer(question), "calls": calls}

    monkeypatch.setattr(api.main, "answer", professor_only)
    assert client.post("/chat", json={"question": "hall's gpa in chem 107"}).json()["grades"] == []


def test_a_grade_chart_that_fails_does_not_fail_the_answer(client, monkeypatch):
    def broken(code):
        raise RuntimeError("anex.us down")

    monkeypatch.setattr(api.main, "answer", grade_answer)
    monkeypatch.setattr(api.main.data, "grade_chart", broken)
    r = client.post("/chat", json={"question": "who's easiest for chem 107"})
    assert r.status_code == 200 and r.json()["grades"] == []


def test_chat_passes_history(client, monkeypatch):
    got = {}

    def spy(question, history=None, metadata=None, thread_id=None):
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


def test_chat_returns_the_question_when_the_agent_asks(client, monkeypatch):
    asked = {"prompt": "Which Professor Leyk?", "options": ["Teresa Leyk (Computer Science)", "Zbigniew Leyk (Engineering)"]}
    monkeypatch.setattr(api.main, "answer", lambda q, **kw: {**fake_answer(q), "answer": "Which Professor Leyk?",
                                                              "sources": [], "calls": [], "question": asked})
    body = client.post("/chat", json={"question": "is professor leyk good"}).json()
    assert body["question"] == asked and body["sources"] == []


# --- /chat/stream (#142) ---------------------------------------------------------

def parse_sse(text):
    """[(event, data)] from a text/event-stream body."""
    import json

    events = []
    for block in text.strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines())
        events.append((fields["event"], json.loads(fields["data"])))
    return events


def fake_answer_stream(question, history=None, metadata=None, thread_id=None):
    yield "step", {"name": "search_student_rules", "args": {"query": "q drops"}}
    yield "step", {"name": "search_student_rules", "args": {"query": "q drop limit"}}
    yield "result", fake_answer(question)


def test_chat_stream_sends_each_step_then_the_same_reply_as_chat(client, monkeypatch):
    monkeypatch.setattr(api.main, "answer", fake_answer)
    monkeypatch.setattr(api.main, "answer_stream", fake_answer_stream)
    thread = str(uuid.uuid4())
    r = client.post("/chat/stream", json={"question": "how many q drops do i get", "thread_id": thread})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    events = parse_sse(r.text)
    assert [e for e, _ in events] == ["step", "step", "done"]
    assert events[0][1] == {"name": "search_student_rules", "args": {"query": "q drops"}}
    plain = client.post("/chat", json={"question": "how many q drops do i get", "thread_id": thread}).json()
    assert events[-1][1] == plain


def test_chat_stream_reports_a_failure_as_an_error_event(client, monkeypatch):
    def broken(question, **kwargs):
        yield "step", {"name": "search_student_rules", "args": {}}
        raise RuntimeError("model down")

    monkeypatch.setattr(api.main, "answer_stream", broken)
    events = parse_sse(client.post("/chat/stream", json={"question": "q drops?"}).text)
    assert [e for e, _ in events] == ["step", "error"]
    assert events[-1][1] == {"detail": "AggieFlow can't answer right now. Try again in a minute."}


def test_chat_stream_validates_like_chat(client):
    assert client.post("/chat/stream", json={"question": ""}).status_code == 422

