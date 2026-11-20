"""Offline tests for eval/judges.py and eval/calibrate.py: no API key, the judge model is faked."""

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "eval"))  # eval/ isn't a package; calibrate.py imports judges and score

judges = importlib.import_module("judges")
_spec = importlib.util.spec_from_file_location("calibrate", ROOT / "eval" / "calibrate.py")
calibrate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(calibrate)

DOC = {"id": "r:1", "title": "Academic Calendar", "source_url": "https://registrar.tamu.edu/academic-calendar",
       "text": "Fall 2026 classes begin August 24."}


class FakeModel:
    def __init__(self, verdict):
        self.verdict, self.prompts = verdict, []

    def invoke(self, prompt):
        self.prompts.append(prompt)
        return judges.Verdict(reasoning="because", verdict=self.verdict)


@pytest.fixture
def fake(monkeypatch):
    def use(verdict):
        model = FakeModel(verdict)
        monkeypatch.setattr(judges, "judge_model", lambda: model)
        return model
    return use


@pytest.mark.parametrize("verdict, score", [("yes", 1), ("no", 0), ("unknown", None)])
def test_verdict_becomes_score(fake, verdict, score):
    fake(verdict)
    result = judges.relevance({"question": "when do classes start"}, {"answer": "August 24."})
    assert result == {"key": "relevance", "score": score, "comment": "because"}


def test_judges_see_the_passages_and_reference(fake):
    model = fake("yes")
    outputs = {"answer": "August 24.", "documents": [DOC]}
    judges.groundedness({"question": "q"}, outputs)
    judges.correctness({"question": "q"}, outputs, {"answer": "Classes begin August 24."})
    assert DOC["text"] in model.prompts[0] and DOC["source_url"] in model.prompts[0]
    assert "Classes begin August 24." in model.prompts[1]


def test_not_sure_reference_tells_the_judge_to_expect_declining(fake):
    model = fake("yes")
    judges.correctness({"question": "best dining hall"}, {"answer": "I'm not sure."}, {"answer": "NOT_SURE"})
    assert "should say it is not sure" in model.prompts[0]
    assert "NOT_SURE" not in model.prompts[0]


def test_no_passages_skips_the_model(fake):
    model = fake("yes")
    q = {"question": "best dining hall"}
    assert judges.groundedness(q, {"answer": judges.DECLINE, "documents": []})["score"] == 1
    assert judges.groundedness(q, {"answer": "Sbisa.", "documents": []})["score"] == 0
    assert judges.retrieval_relevance(q, {"answer": "Sbisa.", "documents": []})["score"] is None
    assert model.prompts == []


def test_declining_is_grounded_without_the_model(fake):
    model = fake("no")
    result = judges.groundedness({"question": "q"}, {"answer": judges.DECLINE, "documents": [DOC]})
    assert result["score"] == 1 and model.prompts == []


def test_hedged_answer_is_still_judged(fake):
    model = fake("no")
    hedged = "Not sure about summer, but in fall classes begin August 20."
    result = judges.groundedness({"question": "q"}, {"answer": hedged, "documents": [DOC]})
    assert result["score"] == 0 and len(model.prompts) == 1


def test_compare_counts_agreement_and_skips_unknown_and_unlabeled():
    lines = [
        {"id": "a", "labels": {"correctness": "yes", "relevance": "unknown", "groundedness": None, "retrieval_relevance": "no"}},
        {"id": "b", "labels": {"correctness": "no", "relevance": "yes", "groundedness": "yes", "retrieval_relevance": "yes"}},
    ]
    r = lambda score: {"score": score, "comment": "c"}  # noqa: E731
    results = [  # judge_line doesn't run a judge for an "unknown" label, so "a" has no relevance
        {"correctness": r(1), "retrieval_relevance": r(None)},
        {"correctness": r(1), "relevance": r(1), "groundedness": r(1), "retrieval_relevance": r(1)},
    ]
    report = calibrate.compare(lines, results)
    assert (report["correctness"]["agreed"], report["correctness"]["counted"]) == (1, 2)
    assert report["correctness"]["disagreements"] == [("b", "no", 1, "c")]
    assert (report["relevance"]["agreed"], report["relevance"]["counted"]) == (1, 1)  # your "unknown" isn't counted
    assert report["groundedness"]["missing"] == 1
    assert report["retrieval_relevance"]["counted"] == 1  # the judge's "unknown" isn't counted
    assert not calibrate.print_report(report)  # correctness at 50%, groundedness unlabeled


def test_pick_is_repeatable_and_mixes_in_not_sure():
    first, second = calibrate.pick_questions(), calibrate.pick_questions()
    assert [q["id"] for q in first] == [q["id"] for q in second]
    assert len(first) == calibrate.SIZE and len({q["id"] for q in first}) == calibrate.SIZE
    assert sum(q["answer"] == "NOT_SURE" for q in first) == calibrate.NOT_SURE_COUNT
    assert not any(calibrate.score.is_known_gap(q) for q in first)


def test_flaky_groq_json_error_is_retried(monkeypatch):
    calls = []

    class Flaky:
        def invoke(self, prompt):
            calls.append(prompt)
            if len(calls) == 1:
                raise RuntimeError("Error code: 400 - {'code': 'json_validate_failed'}")
            return judges.Verdict(reasoning="ok", verdict="yes")

    monkeypatch.setattr(judges, "judge_model", lambda: Flaky())
    assert judges.relevance({"question": "q"}, {"answer": "a"})["score"] == 1
    assert len(calls) == 2


def test_other_errors_are_not_retried(monkeypatch):
    calls = []

    class Broken:
        def invoke(self, prompt):
            calls.append(prompt)
            raise RuntimeError("invalid api key")

    monkeypatch.setattr(judges, "judge_model", lambda: Broken())
    with pytest.raises(RuntimeError):
        judges.relevance({"question": "q"}, {"answer": "a"})
    assert len(calls) == 1
