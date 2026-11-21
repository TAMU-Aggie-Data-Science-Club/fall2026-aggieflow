"""Offline tests for eval/run_eval.py: fake agent and judges, LangSmith's evaluate() run locally."""

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("run_eval", ROOT / "eval" / "run_eval.py")
run_eval = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run_eval)

RULE01 = "https://student-rules.tamu.edu/rule01/"
CHEM = "https://anex.us/grades/?dept=CHEM&number=107"


def passage(url):
    return {"id": "x:y:1", "source": "x", "title": "T", "text": "t", "source_url": url,
            "fetched_at": "2026-11-21T00:00:00Z"}


def call(name, round_=1, error=False, **args):
    return {"round": round_, "name": name, "args": args, "error": error}


def judge(name, verdict):
    def fn(inputs, outputs, reference_outputs):
        return {"key": name, "score": verdict, "comment": f"{name} said {verdict}"}
    fn.__name__ = name
    return fn


YES_JUDGES = [judge(n, 1) for n in ("correctness", "relevance", "groundedness", "retrieval_relevance")]


# --- numbers_match ----------------------------------------------------------------

REFERENCE = ("ALTEMOSE A taught 9 CHEM 107 sections from Spring 2023 to Fall 2025: 2,434 students, "
             "average GPA 3.08, 38% A, 118 Q-drops.")
PASSAGES = [{"text": "CHEM 107 with ALTEMOSE A: 9 sections, 2434 students, average GPA 3.08, 38% A, "
                     "36% B, 21% C, 118 Q-drops. Fall 2025: 508 students, average GPA 3.01."}]


def test_a_short_correct_answer_passes_and_the_sources_list_is_ignored():
    answer = ("Altemose A averages a 3.08 GPA in CHEM 107. (https://anex.us/grades/?dept=CHEM&number=107)"
              "\n\nSources:\n- CHEM 107: https://anex.us/grades/?dept=CHEM&number=107 (as of 2026-11-21T19:19:09Z)")
    assert run_eval.numbers_match(answer, REFERENCE, PASSAGES) == (1, "all 2 numbers check out and it names ALTEMOSE")


def test_numbers_from_the_passages_count_and_rounding_is_allowed():
    answer = "ALTEMOSE A: 36% B's, and in Fall 2025 a 3.01 GPA across about 2,440 students, 38.4% A's."
    assert run_eval.numbers_match(answer, REFERENCE, PASSAGES)[0] == 1


@pytest.mark.parametrize("answer, problem", [
    ("ALTEMOSE A averages a 3.10 GPA.", "3.1 not in"),
    ("ALTEMOSE A gives 45% A's.", "45% not in"),
    ("ALTEMOSE A taught 2,600 students.", "2600 not in"),
    ("GOODEY J averages a 3.08 GPA.", "doesn't name ALTEMOSE"),
])
def test_a_wrong_number_or_professor_fails(answer, problem):
    result, comment = run_eval.numbers_match(answer, REFERENCE, PASSAGES)
    assert result == 0 and problem in comment


def test_an_answer_with_no_numbers_fails_when_numbers_were_expected():
    assert run_eval.numbers_match("It's a hard class.", "2.68 average GPA", []) == (0, "the answer states no numbers")


# --- path metrics -----------------------------------------------------------------

def test_path_metrics():
    calls = [call("get_professor_grades", 1, True, course="CHEM 107", professor="altemoss"),
             call("get_course_grades", 2, course="CHEM 107"),
             call("get_course_grades", 3, course="CHEM 107")]
    m = run_eval.path_metrics(calls, ["recovery"], max_rounds=4)
    assert m == {"rounds": 3, "tool_call_count": 3, "redundant_calls": 1,
                 "tool_error_rate": pytest.approx(1 / 3), "hit_round_limit": 0, "recovered": 1}
    assert run_eval.path_metrics([], [], 4) == {"rounds": 0, "tool_call_count": 0, "redundant_calls": 0,
                                                "tool_error_rate": None, "hit_round_limit": 0,
                                                "recovered": None}
    assert run_eval.path_metrics([call("x", 4)], [], 4)["hit_round_limit"] == 1


# --- grade ------------------------------------------------------------------------

RULES_META = {"id": "sr-01", "source": "student-rules", "tools": ["search_student_rules"], "tags": []}
RULES_REF = {"answer": "Four.", "source_url": RULE01}
RULES_OUT = {"answer": f"Four ({RULE01}).", "sources": [passage(RULE01)], "documents": [passage(RULE01)],
             "calls": [call("search_student_rules", query="q-drops")]}


def scores(graded):
    return {k: s for k, (s, _) in graded.items()}


def test_a_correct_cited_answer_passes():
    s = scores(run_eval.grade(RULES_META, RULES_REF, RULES_OUT, YES_JUDGES))
    assert (s["cited_page"], s["tool_match"], s["correctness"], s["passed"]) == (1, 1, 1, 1)
    assert s["not_sure_correct"] is None and s["numbers_match"] is None


def test_a_wrong_answer_fails_even_when_cited():
    judges = [judge("correctness", 0), *YES_JUDGES[1:]]
    graded = run_eval.grade(RULES_META, RULES_REF, RULES_OUT, judges)
    assert graded["passed"] == (0, "failed ['correctness']")


def test_groundedness_is_recorded_but_does_not_gate():
    judges = [*YES_JUDGES[:2], judge("groundedness", 0), YES_JUDGES[3]]
    s = scores(run_eval.grade(RULES_META, RULES_REF, RULES_OUT, judges))
    assert (s["groundedness"], s["passed"]) == (0, 1)


def test_a_judge_that_cannot_tell_does_not_count():
    judges = [judge("correctness", None), *YES_JUDGES[1:]]
    assert scores(run_eval.grade(RULES_META, RULES_REF, RULES_OUT, judges))["passed"] == 1


def test_grade_tasks_use_numbers_match_instead_of_correctness():
    meta = {"id": "a-01", "source": "anex", "tools": ["get_course_grades", "get_professor_grades"], "tags": []}
    ref = {"answer": REFERENCE, "source_url": CHEM}
    out = {"answer": f"ALTEMOSE A: 9 sections, 2,434 students, GPA 3.08, 38% A, 118 Q-drops ({CHEM})",
           "sources": [passage(CHEM)], "documents": [], "calls": [call("get_professor_grades")]}
    graded = run_eval.grade(meta, ref, out, [judge("correctness", 0), *YES_JUDGES[1:]])
    assert graded["correctness"][0] is None
    assert scores(graded)["numbers_match"] == 1 and scores(graded)["passed"] == 1


def test_not_sure_task_with_no_tools():
    meta = {"id": "e-01", "source": "extra", "tools": [], "tags": ["no-tool"]}
    ref = {"answer": "NOT_SURE", "source_url": None}
    good = {"answer": "I'm not sure.", "sources": [], "documents": [], "calls": []}
    s = scores(run_eval.grade(meta, ref, good, None))
    assert (s["not_sure_correct"], s["tool_match"], s["cited_page"], s["passed"]) == (1, 1, None, 1)
    searched = {**good, "calls": [call("search_registrar", query="sbisa")]}
    assert scores(run_eval.grade(meta, ref, searched, None))["passed"] == 0  # tool_match fails


def test_a_failed_agent_run_fails_the_task():
    assert run_eval.grade(RULES_META, RULES_REF, None, YES_JUDGES) == {"passed": (0, "the agent run failed")}


# --- end to end, locally ----------------------------------------------------------

def test_main_runs_locally_and_prints_pass_rates(tmp_path, monkeypatch, capsys):
    rows = [{"id": "sr-01", "question": "how many q drops", "answer": "Four.", "source_url": RULE01},
            {"id": "sr-02", "question": "parking permit price", "answer": "NOT_SURE", "source_url": None,
             "tags": ["no-tool"], "tools": []},
            {"id": "sr-03", "question": "gap", "answer": "x", "source_url": RULE01, "tags": ["known-gap"]}]
    (tmp_path / "student-rules-test.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n",
                                                       encoding="utf-8")
    runs = {"sr-01": 0}

    def fake_answer(question, question_id):
        if question_id == "sr-02":
            return {"answer": "I'm not sure.", "sources": [], "documents": [], "calls": [], "trace": []}
        runs["sr-01"] += 1  # cites the page on the first run only
        cited = [passage(RULE01)] if runs["sr-01"] == 1 else []
        return {"answer": "Four.", "sources": cited, "documents": cited, "trace": [],
                "calls": [call("search_student_rules", query="q drops")]}

    monkeypatch.setattr(run_eval, "answer_fn", fake_answer)
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("AGGIEFLOW_SEARCH", "keyword")  # main sets it; monkeypatch restores it after
    assert run_eval.main(["--questions", str(tmp_path), "--repetitions", "2",
                          "--no-upload", "--no-judges"]) == 0
    out = capsys.readouterr().out
    assert "setup: " in out
    lines = {line.split()[0]: line.split()[1:] for line in out.splitlines() if line.strip()}
    assert lines["all"] == ["2", "75%", "50%"]  # sr-01 passed 1 of 2 runs, sr-02 both
    assert lines["source=student-rules"] == ["2", "75%", "50%"]
    assert lines["tag=no-tool"] == ["1", "100%", "100%"]
