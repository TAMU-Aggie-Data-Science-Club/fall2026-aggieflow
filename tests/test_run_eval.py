"""Offline tests for eval/run_eval.py, summarize.py and compare.py: fake agent and judges,
LangSmith's evaluate() run locally."""

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("run_eval", ROOT / "eval" / "run_eval.py")
run_eval = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run_eval)
import compare  # noqa: E402  (eval/ is on sys.path once run_eval loads)
import summarize  # noqa: E402

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


@pytest.mark.parametrize("answer", [
    "ALTEMOSE A: 36% B's, and in Fall 2025 a 3.01 GPA across about 2,440 students, 38.4% A's.",  # passages, rounding
    "Highest GPA:\n\n1. ALTEMOSE A - 3.08 GPA\n2. Another prof - 38% A's",  # list markers aren't claims
    "ALTEMOSE A: about 37–38% of students get an A.",  # a percent range within a point
])
def test_right_numbers_pass(answer):
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


@pytest.mark.parametrize("text, expected", [
    ("about 92–93% would take him again", [("percent", 92), ("percent", 93)]),
    ("92-93 %", [("percent", 92), ("percent", 93)]),
    ("37 to 38 percent", [("percent", 37), ("percent", 38)]),
    ("a 3.01–3.08 GPA", [("gpa", 3.01), ("gpa", 3.08)]),
    ("118 Q-drops, 38% A", [("count", 118), ("percent", 38)]),
])
def test_a_percent_range_makes_both_ends_percents(text, expected):
    assert run_eval.numbers_in(text) == expected


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
NOT_SURE_REF = {"answer": "NOT_SURE", "source_url": None}


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


def test_groundedness_and_unsure_judges_do_not_gate():
    judges = [*YES_JUDGES[:2], judge("groundedness", 0), YES_JUDGES[3]]
    s = scores(run_eval.grade(RULES_META, RULES_REF, RULES_OUT, judges))
    assert (s["groundedness"], s["passed"]) == (0, 1)
    judges = [judge("correctness", None), *YES_JUDGES[1:]]  # a judge that cannot tell
    assert scores(run_eval.grade(RULES_META, RULES_REF, RULES_OUT, judges))["passed"] == 1


def test_grade_tasks_use_numbers_match_instead_of_correctness():
    meta = {"id": "a-01", "source": "anex", "tools": ["get_course_grades", "get_professor_grades"], "tags": []}
    ref = {"answer": REFERENCE, "source_url": CHEM}
    out = {"answer": f"ALTEMOSE A: 9 sections, 2,434 students, GPA 3.08, 38% A, 118 Q-drops ({CHEM})",
           "sources": [passage(CHEM)], "documents": [], "calls": [call("get_professor_grades")]}
    graded = run_eval.grade(meta, ref, out, [judge("correctness", 0), *YES_JUDGES[1:]])
    assert graded["correctness"][0] is None
    assert scores(graded)["numbers_match"] == 1 and scores(graded)["passed"] == 1


def test_grade_and_ratings_tasks_need_numbers_match_and_correctness():
    meta = {"id": "r-05", "source": "ratemyprofessors", "tags": [],
            "tools": ["get_professor_ratings", "get_professor_grades"]}
    ref = {"answer": REFERENCE, "source_url": CHEM}
    out = {"answer": f"ALTEMOSE A: 9 sections, 2,434 students, GPA 3.08, 38% A, 118 Q-drops ({CHEM})",
           "sources": [passage(CHEM)], "documents": [], "calls": [call("get_professor_grades")]}
    right_numbers_wrong_verdict = run_eval.grade(meta, ref, out, [judge("correctness", 0), *YES_JUDGES[1:]])
    assert scores(right_numbers_wrong_verdict)["numbers_match"] == 1
    assert scores(right_numbers_wrong_verdict)["passed"] == 0
    assert scores(run_eval.grade(meta, ref, out, YES_JUDGES))["passed"] == 1


def test_not_sure_tasks_pass_on_declining_and_fail_on_answering():
    # declining with related links still counts
    meta = {"id": "t-10", "source": "transportation", "tools": ["search_transportation"]}
    out = {"answer": "I'm not sure; live counts aren't available.", "sources": [passage(RULE01)],
           "documents": [passage(RULE01)], "calls": [call("search_transportation", query="garage")]}
    s = scores(run_eval.grade(meta, NOT_SURE_REF, out, None))
    assert (s["not_sure_correct"], s["answered_out_of_scope"], s["passed"]) == (1, 0, 1)

    # with no tools expected, searching anyway is recorded but doesn't gate
    meta = {"id": "e-01", "source": "extra", "tools": [], "tags": ["no-tool"]}
    good = {"answer": "I'm not sure.", "sources": [], "documents": [], "calls": []}
    s = scores(run_eval.grade(meta, NOT_SURE_REF, good, None))
    assert (s["not_sure_correct"], s["tool_match"], s["cited_page"], s["passed"]) == (1, 1, None, 1)
    s = scores(run_eval.grade(meta, NOT_SURE_REF, {**good, "calls": [call("search_registrar", query="sbisa")]}, None))
    assert (s["tool_match"], s["passed"]) == (0, 1)

    answered = {**good, "answer": "Sbisa closes at 8."}
    s = scores(run_eval.grade(meta, NOT_SURE_REF, answered, None))
    assert (s["answered_out_of_scope"], s["wrongly_not_sure"], s["passed"]) == (1, None, 0)


def test_citing_an_also_accept_page_passes_cited_page():
    other = "https://student-rules.tamu.edu/rule02/"
    out = {**RULES_OUT, "sources": [passage(other)]}
    assert scores(run_eval.grade(RULES_META, RULES_REF, out, YES_JUDGES))["cited_page"] == 0
    ref = {**RULES_REF, "also_accept": [other]}
    assert scores(run_eval.grade(RULES_META, ref, out, YES_JUDGES))["cited_page"] == 1


def test_run_metrics_are_recorded_and_do_not_gate():
    out = {**RULES_OUT, "latency_s": 2.5, "fell_back": 1}
    s = scores(run_eval.grade(RULES_META, RULES_REF, out, YES_JUDGES))
    assert (s["latency_s"], s["fell_back"], s["wrongly_not_sure"], s["passed"]) == (2.5, 1, 0, 1)
    assert s["answered_out_of_scope"] is None
    refused = {**RULES_OUT, "answer": f"I'm not sure. ({RULE01})"}
    assert scores(run_eval.grade(RULES_META, RULES_REF, refused, YES_JUDGES))["wrongly_not_sure"] == 1


def test_a_failed_agent_run_fails_the_task():
    assert run_eval.grade(RULES_META, RULES_REF, None, YES_JUDGES) == {"passed": (0, "the agent run failed")}


def test_a_greeting_passes_with_the_intro_and_skips_the_judge():
    from agent.checks import INTRO

    intro = {"answer": INTRO, "sources": [], "documents": [], "calls": []}
    greeting = run_eval.grade({"tools": [], "tags": ["no-tool", "greeting"]}, NOT_SURE_REF, intro, [judge("correctness", 0)])
    assert greeting["passed"][0] == 1 and greeting["correctness"][0] is None
    assert greeting["answered_out_of_scope"][0] == 0
    # without the tag, the intro still isn't a decline
    other = run_eval.grade({"tools": [], "tags": ["no-tool"]}, NOT_SURE_REF, intro, [judge("correctness", 0)])
    assert other["passed"][0] == 0


# --- retries ----------------------------------------------------------------------

class RateLimitError(Exception):
    pass


@pytest.mark.parametrize("message", [
    "tokens per minute (TPM): Limit 8000",
    "429 RESOURCE_EXHAUSTED: requests per minute limit exceeded on Free Tier",
])
def test_retry_waits_out_a_per_minute_limit(message):
    attempts, waits = [], []

    def flaky():
        attempts.append(1)
        if len(attempts) == 1:
            raise RateLimitError(message)
        return "ok"
    assert run_eval.with_retry(flaky, sleep=waits.append) == "ok"
    assert waits == [15]


def test_retry_gives_up_at_once_on_the_daily_limit(capsys):
    waits = []

    def capped():
        raise RateLimitError("Rate limit reached ... on tokens per day (TPD): Limit 200000")
    with pytest.raises(RateLimitError):
        run_eval.with_retry(capped, sleep=waits.append)
    assert waits == [] and run_eval.DAILY_LIMIT in capsys.readouterr().err


# --- summarize and compare --------------------------------------------------------

def record(qid, passed, rep=1, mode="keyword", commit="abc1234", source="registrar", **scores):
    return {"experiment": f"agent-{mode}-{commit}-x", "commit": commit, "model": "m", "mode": mode,
            "setup": f"setup: m; {mode}", "id": qid, "source": source, "set": None, "tags": [],
            "repetition": rep, "passed": passed, "scores": {"cited_page": passed, **scores}}


def write(path, recs):
    run_eval.write_records(path, recs)
    return path


def test_summarize_merges_files_from_one_setup_and_refuses_to_mix(tmp_path, capsys):
    a = write(tmp_path / "a.jsonl", [record("r-01", 1, latency_s=2.0), record("r-02", 0, latency_s=4.0)])
    b = write(tmp_path / "b.jsonl", [record("sr-01", 1, source="student-rules", latency_s=3.0, fell_back=0)])
    assert summarize.main([str(a), str(b)]) == 0
    out = capsys.readouterr().out
    lines = {line.split()[0]: line.split()[1:] for line in out.splitlines() if line.strip()}
    assert lines["all"][:2] == ["3", "67%"]
    assert lines["source=registrar"][:2] == ["2", "50%"]
    assert "p50 3.0, p95 4.0 over 3 runs" in out and "pass^k not measured" in out

    c = write(tmp_path / "c.jsonl", [record("r-02", 1, mode="vector")])
    assert summarize.main([str(a), str(c)]) == 1
    assert "mix modes: keyword, vector" in capsys.readouterr().err


def test_compare_pairs_questions_and_counts_wins():
    a = [record("q1", 1), record("q2", 0), record("q3", 1), record("q4", 1)]
    b = [record("q1", 1, mode="vector"), record("q2", 1, mode="vector"), record("q3", 0, mode="vector"),
         record("q2", 1, rep=2, mode="vector"), record("q5", 1, mode="vector")]
    result = compare.compare(a, b)
    assert (result["both"], result["a_only"], result["b_only"]) == (3, 1, 1)
    assert (result["wins"], result["losses"], result["ties"]) == (1, 1, 1)
    metric, n, mean_a, mean_b, diff, low, high = result["rows"][0]
    assert (metric, n, diff) == ("passed", 3, 0.0) and low <= 0 <= high


def test_compare_main_refuses_a_setup_change_unless_asked(tmp_path, capsys):
    a = write(tmp_path / "a.jsonl", [record("q1", 0)])
    b = write(tmp_path / "b.jsonl", [{**record("q1", 1, commit="def5678"), "model": "google_genai:x"}])
    assert compare.main([str(a), str(b)]) == 1
    assert "--allow-setup-change" in capsys.readouterr().err
    assert compare.main([str(a), str(b), "--allow-setup-change"]) == 0
    out = capsys.readouterr().out
    assert "google_genai:x" in out and "B wins 1, loses 0, ties 0" in out


# --- end to end, locally ----------------------------------------------------------

def test_main_runs_locally_and_prints_pass_rates(tmp_path, monkeypatch, capsys):
    rows = [{"id": "sr-01", "question": "how many q drops", "answer": "Four.", "source_url": RULE01},
            {"id": "sr-02", "question": "parking permit price", "answer": "NOT_SURE", "source_url": None,
             "tags": ["no-tool"], "tools": []},
            {"id": "sr-03", "question": "gap", "answer": "x", "source_url": RULE01, "tags": ["known-gap"]}]
    (tmp_path / "student-rules-test.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n",
                                                       encoding="utf-8")
    runs = {"sr-01": 0}

    def fake_answer(question, question_id, history=None):
        if question_id == "sr-02":
            return {"answer": "I'm not sure.", "sources": [], "documents": [], "calls": [], "trace": []}
        runs["sr-01"] += 1  # cites the page on the first run only
        cited = [passage(RULE01)] if runs["sr-01"] == 1 else []
        return {"answer": "Four.", "sources": cited, "documents": cited, "trace": [],
                "calls": [call("search_student_rules", query="q drops")]}

    monkeypatch.setattr(run_eval, "answer_fn", fake_answer)
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("AGGIEFLOW_SEARCH", "keyword")  # main sets it; monkeypatch restores it after
    out_file = tmp_path / "results" / "run.jsonl"
    assert run_eval.main(["--questions", str(tmp_path), "--repetitions", "2",
                          "--no-upload", "--no-judges", "--out", str(out_file)]) == 0
    out = capsys.readouterr().out
    assert "setup: " in out
    lines = {line.split()[0]: line.split()[1:] for line in out.splitlines() if line.strip()}
    assert lines["all"] == ["2", "75%", "[50%,", "100%]", "50%"]  # sr-01 passed 1 of 2 runs, sr-02 both
    assert lines["source=student-rules"][:2] == ["2", "75%"]
    assert lines["tag=no-tool"] == ["1", "100%", "[100%,", "100%]", "100%"]
    assert "false refusals (wrongly_not_sure): 0 of 2 answerable runs" in out
    assert "false answers (answered_out_of_scope): 0 of 2 NOT_SURE runs" in out

    saved = summarize.load([out_file])
    assert len(saved) == 4 and {r["mode"] for r in saved} == {"hybrid"}  # the default mode
    assert sorted((r["id"], r["repetition"], r["passed"]) for r in saved) == [
        ("sr-01", 1, 1), ("sr-01", 2, 0), ("sr-02", 1, 1), ("sr-02", 2, 1)]
    assert "cited_page" in saved[0]["scores"] and "passed" not in saved[0]["scores"]

    assert run_eval.main(["--questions", str(tmp_path), "--repetitions", "1", "--no-upload",
                          "--no-judges", "--search-only", "--out", str(out_file)]) == 0
    assert [r["id"] for r in summarize.load([out_file])] == ["sr-01"]  # sr-02 expects no tools


def test_ids_keeps_only_the_listed_questions(tmp_path, monkeypatch, capsys):
    rows = [{"id": f"sr-0{i}", "question": f"q{i}", "answer": "x", "source_url": RULE01} for i in (1, 2, 3)]
    (tmp_path / "student-rules-test.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n",
                                                       encoding="utf-8")
    ids = tmp_path / "ids.txt"
    ids.write_text("# sample\nsr-01\n\nsr-03  # last\n", encoding="utf-8")
    seen = []

    def fake_answer(question, question_id, history=None):
        seen.append(question_id)
        return {"answer": "x", "sources": [], "documents": [], "calls": [], "trace": []}

    monkeypatch.setattr(run_eval, "answer_fn", fake_answer)
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("AGGIEFLOW_SEARCH", "keyword")
    args = ["--questions", str(tmp_path), "--repetitions", "1", "--no-upload", "--no-judges",
            "--out", str(tmp_path / "run.jsonl"), "--ids", str(ids)]
    assert run_eval.main(args) == 0
    assert sorted(seen) == ["sr-01", "sr-03"]

    ids.write_text("sr-01\nsr-09\n", encoding="utf-8")
    assert run_eval.main(args) == 1
    assert "sr-09" in capsys.readouterr().err


def test_release_parts_cover_every_question_once():
    ids = [i for n in range(1, 5) for i in run_eval.read_ids(ROOT / "eval" / f"release-part{n}.txt")]
    assert len(ids) == len(set(ids))
    assert set(ids) == {t["id"] for t in run_eval.load_tasks()}


# --- multi-turn and ask tasks -------------------------------------------------------

LEYK_Q = {"prompt": "Which Professor Leyk?", "options": ["Teresa Leyk (CSCE)", "Zbigniew Leyk (MATH)"]}


def test_example_fields_carry_history_and_ask_fields_only_when_set():
    task = {"id": "t1", "source": "x", "question": "what about summer?", "answer": "a", "source_url": "u"}
    plain = run_eval.example_fields(task)
    assert plain["inputs"] == {"question": "what about summer?"} and "ask" not in plain["metadata"]
    history = [{"role": "user", "content": "how many q drops"}, {"role": "assistant", "content": "Four."}]
    assert run_eval.example_fields({**task, "history": history})["inputs"]["history"] == history
    # the same follow-up after different conversations, or with different replies, is two tasks
    assert run_eval.task_key(task["question"], history) != run_eval.task_key(task["question"], None)
    assert run_eval.task_key("is leyk good", None, "Teresa") != run_eval.task_key("is leyk good", None, "Zbigniew")

    fields = run_eval.example_fields({**task, "ask": True, "options": ["Teresa"], "reply": "Teresa Leyk"})
    assert fields["inputs"]["reply"] == "Teresa Leyk"
    assert fields["metadata"]["ask"] is True and fields["metadata"]["options"] == ["Teresa"]


def test_judges_see_a_multi_turn_tasks_earlier_turns():
    task = {"question": "what about summer?",
            "history": [{"role": "user", "content": "q drop deadline in spring?"},
                        {"role": "assistant", "content": "April 20, 2027."}]}
    seen = run_eval.judged_question(task)
    assert seen.index("Student: q drop deadline in spring?") < seen.index("AggieFlow: April 20, 2027.")
    assert seen.endswith("The student now asks: what about summer?")
    assert run_eval.judged_question({"question": "hi"}) == "hi"


def ask_meta(ask, **extra):
    return {"tools": ["get_professor_ratings"], "ask": ask, **extra}


@pytest.mark.parametrize("meta, asked, expected", [
    (ask_meta(True, options=["teresa", "Zbigniew"]), LEYK_Q, 1),
    (ask_meta(True, options=["Teresa", "Kim"]), LEYK_Q, 0),       # an expected option is missing
    (ask_meta(True), {"prompt": "Which minor?", "options": []}, 1),  # open question
    (ask_meta(True), None, 0),                                     # under-asked
    (ask_meta(False), LEYK_Q, 0),                                  # over-asked
    (ask_meta(False), None, 1),
    ({"tools": []}, LEYK_Q, None),                                 # not an ask task
])
def test_asked_right(meta, asked, expected):
    assert run_eval.asked_right(meta, asked)[0] == expected


def test_ask_tasks_gate_on_asked_right_and_count_over_and_under_asking():
    reference = {"answer": "Students like her.", "source_url": "https://www.ratemyprofessors.com/professor/1"}
    rated = passage(reference["source_url"])
    outputs = {"answer": "Students like Teresa Leyk.", "sources": [rated], "documents": [rated],
               "calls": [call("get_professor_ratings", professor="leyk"), call("ask_user", round_=2, **LEYK_Q),
                         call("get_professor_ratings", round_=3, professor="teresa leyk")]}
    asked = run_eval.grade(ask_meta(True), reference, {**outputs, "asked": LEYK_Q}, YES_JUDGES)
    assert asked["passed"][0] == 1 and asked["under_asked"][0] == 0 and asked["over_asked"][0] is None
    assert asked["tool_match"][0] == 1 and asked["tool_call_count"][0] == 2  # ask_user isn't a lookup

    guessed = run_eval.grade(ask_meta(True), reference, {**outputs, "asked": None}, YES_JUDGES)
    assert guessed["passed"][0] == 0 and guessed["under_asked"][0] == 1

    over = run_eval.grade(ask_meta(False), reference, {**outputs, "asked": LEYK_Q}, YES_JUDGES)
    assert over["passed"][0] == 0 and over["over_asked"][0] == 1
    plain = run_eval.grade({"tools": ["get_professor_ratings"]}, reference, outputs, YES_JUDGES)
    assert plain["asked_right"][0] is None and plain["passed"][0] == 1


def test_a_reply_resumes_the_same_thread():
    class Data:
        fallback_count = 0

    seen = []

    def answer(question, metadata, history=None, thread_id=None):
        seen.append((question, thread_id))
        if len(seen) == 1:
            return {"answer": "Which Professor Leyk?", "question": LEYK_Q}
        return {"answer": "Students like Teresa Leyk.", "question": None}

    result = run_eval.measured(answer, Data, "is leyk good", "ask-01", reply="Teresa Leyk (CSCE)")
    assert result["answer"] == "Students like Teresa Leyk." and result["asked"] == LEYK_Q
    assert seen[1][0] == "Teresa Leyk (CSCE)" and seen[0][1] == seen[1][1] and seen[0][1].startswith("eval-")

    seen.clear()
    answer_only = lambda q, metadata, history=None, thread_id=None: seen.append(q) or {"answer": "x", "question": None}
    result = run_eval.measured(answer_only, Data, "when is the last day to drop", "ask-02", reply="fall")
    assert seen == ["when is the last day to drop"] and result["asked"] is None  # didn't ask: no reply sent


@pytest.mark.parametrize("line, problem", [
    ({"ask": "yes"}, "ask must be true or false"),
    ({"ask": True}, "needs a reply"),
    ({"reply": "Teresa"}, "need ask: true"),
    ({"ask": False, "options": ["a"]}, "need ask: true"),
])
def test_bad_ask_fields_are_skipped(tmp_path, capsys, line, problem):
    import score

    q = {"id": "ask-01", "question": "q", "answer": "a", "source_url": "u", "tools": [], **line}
    (tmp_path / "ask-test.jsonl").write_text(json.dumps(q) + "\n", encoding="utf-8")
    assert score.load_questions(tmp_path / "ask-test.jsonl") == []
    assert problem in capsys.readouterr().err
