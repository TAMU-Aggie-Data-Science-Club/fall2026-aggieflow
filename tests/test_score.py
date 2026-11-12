"""Offline tests for eval/score.py: standard library only, no API key or network.

Run from the repo root:  python -m unittest discover -s tests -p "test_score.py" -v

The last test also runs the real agent.run.answer with a scripted model; it is
skipped when langchain_core and langgraph are not installed.
"""

import contextlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCORE_PY = ROOT / "eval" / "score.py"

# eval/ is not a package, so load the file by path.
_spec = importlib.util.spec_from_file_location("score", SCORE_PY)
score = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(score)

RULE01 = "https://student-rules.tamu.edu/rule01/"
RULE07 = "https://student-rules.tamu.edu/rule07/"

QUESTIONS = [
    {"id": "t-01", "question": "how many q drops do i get", "answer": "Four.", "source_url": RULE01},
    {"id": "t-02", "question": "when is a doctors note due", "answer": "Three days.", "source_url": RULE07},
    {"id": "t-03", "question": "how much is a parking permit", "answer": "NOT_SURE", "source_url": None},
]


def passage(url):
    return {"id": "x:y:1", "source": "student-rules", "title": "T", "text": "t",
            "source_url": url, "fetched_at": "2026-11-06T00:00:00Z"}


def answers(table):
    """An answer function that looks each question up in a dict of results."""
    return lambda question: table[question]


def write_jsonl(folder, name, rows):
    path = Path(folder) / name
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write((row if isinstance(row, str) else json.dumps(row)) + "\n")
    return path


def run_main(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = score.main(argv)
    return code, out.getvalue(), err.getvalue()


class NormalizeUrlTest(unittest.TestCase):
    def test_same_page_written_differently_matches(self):
        for url in ["http://student-rules.tamu.edu/rule01/",
                    "https://student-rules.tamu.edu/rule01",
                    "https://Student-Rules.TAMU.edu/rule01/",
                    "https://student-rules.tamu.edu/rule01/#q-drops",
                    " https://student-rules.tamu.edu/rule01/ "]:
            self.assertEqual(score.normalize_url(url), score.normalize_url(RULE01), url)

    def test_different_pages_do_not_match(self):
        self.assertNotEqual(score.normalize_url(RULE01), score.normalize_url(RULE07))
        # Path case and the query string can change the page, so they are kept.
        self.assertNotEqual(score.normalize_url(RULE01),
                            score.normalize_url("https://student-rules.tamu.edu/Rule01/"))
        self.assertNotEqual(score.normalize_url("https://anex.us/grades/?dept=CSCE&number=121"),
                            score.normalize_url("https://anex.us/grades/?dept=CSCE&number=120"))


class ScoreTest(unittest.TestCase):
    def score_quietly(self, answer_fn, questions=QUESTIONS):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            counts = score.score(questions, answer_fn)
        return counts, err.getvalue()

    def test_perfect_answers(self):
        counts, _ = self.score_quietly(answers({
            "how many q drops do i get": {"answer": "Four.", "sources": [passage("http://STUDENT-RULES.tamu.edu/rule01#top")]},
            "when is a doctors note due": {"answer": "Three days.", "sources": [passage(RULE01), passage(RULE07)]},
            "how much is a parking permit": {"answer": "I'm Not Sure.", "sources": []},
        }))
        self.assertEqual(counts, {"answerable": 2, "cited": 2, "not_sure_questions": 1,
                                  "not_sure_correct": 1, "wrongly_not_sure": 0, "errors": 0})

    def test_dummy_is_right_only_on_not_sure(self):
        counts, _ = self.score_quietly(score.dummy_answer)
        self.assertEqual(counts, {"answerable": 2, "cited": 0, "not_sure_questions": 1,
                                  "not_sure_correct": 1, "wrongly_not_sure": 2, "errors": 0})

    def test_wrong_page_is_not_a_citation(self):
        counts, _ = self.score_quietly(answers({
            "how many q drops do i get": {"answer": "Four.", "sources": [passage(RULE07)]},
            "when is a doctors note due": {"answer": "Three days.", "sources": []},
            "how much is a parking permit": {"answer": "I'm not sure.", "sources": []},
        }))
        self.assertEqual(counts["cited"], 0)
        self.assertEqual(counts["wrongly_not_sure"], 0)

    def test_not_sure_that_still_cites_a_source_is_not_correct(self):
        # The agent's round-limit fallback says "I'm not sure." but lists what it found.
        counts, _ = self.score_quietly(answers({
            "how many q drops do i get": {"answer": "Four.", "sources": [passage(RULE01)]},
            "when is a doctors note due": {"answer": "Three days.", "sources": [passage(RULE07)]},
            "how much is a parking permit": {"answer": "I'm not sure.", "sources": [passage(RULE01)]},
        }))
        self.assertEqual(counts["not_sure_correct"], 0)

    def test_confident_answer_to_not_sure_question_is_not_correct(self):
        counts, _ = self.score_quietly(answers({
            "how many q drops do i get": {"answer": "Four.", "sources": [passage(RULE01)]},
            "when is a doctors note due": {"answer": "Three days.", "sources": [passage(RULE07)]},
            "how much is a parking permit": {"answer": "It is $100.", "sources": []},
        }))
        self.assertEqual(counts["not_sure_correct"], 0)

    def test_not_sure_with_the_right_page_counts_both_ways(self):
        counts, _ = self.score_quietly(answers({
            "how many q drops do i get": {"answer": "I'm not sure.", "sources": [passage(RULE01)]},
            "when is a doctors note due": {"answer": "Three days.", "sources": [passage(RULE07)]},
            "how much is a parking permit": {"answer": "I'm not sure.", "sources": []},
        }))
        self.assertEqual(counts["cited"], 2)
        self.assertEqual(counts["wrongly_not_sure"], 1)

    def test_errors_are_counted_and_the_run_keeps_going(self):
        def flaky(question):
            if question == "how many q drops do i get":
                raise RuntimeError("model timed out")
            if question == "when is a doctors note due":
                return {"answer": "Three days."}  # no "sources": malformed result
            return {"answer": "I'm not sure.", "sources": []}

        counts, err = self.score_quietly(flaky)
        self.assertEqual(counts, {"answerable": 2, "cited": 0, "not_sure_questions": 1,
                                  "not_sure_correct": 1, "wrongly_not_sure": 0, "errors": 2})
        self.assertIn("t-01: error: RuntimeError: model timed out", err)
        self.assertIn("t-02: error: KeyError", err)


class LoadQuestionsTest(unittest.TestCase):
    def test_bad_lines_are_reported_and_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_jsonl(tmp, "x.jsonl", [
                QUESTIONS[0],
                "",
                "{not json",
                {"id": "t-09", "question": "missing answer and source_url"},
                {"id": "t-10", "question": "q", "answer": "A real answer", "source_url": None},
                QUESTIONS[2],
            ])
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                loaded = score.load_questions(path)
        self.assertEqual([q["id"] for q in loaded], ["t-01", "t-03"])
        self.assertIn("x.jsonl:3: skipped, not valid JSON", err.getvalue())
        self.assertIn("x.jsonl:4: skipped", err.getvalue())
        self.assertIn("x.jsonl:5: skipped, answerable but source_url", err.getvalue())


class MainTest(unittest.TestCase):
    def test_one_line_per_file_then_total(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_jsonl(tmp, "b-source.jsonl", QUESTIONS)
            write_jsonl(tmp, "a-source.jsonl", QUESTIONS[:1])
            write_jsonl(tmp, "notes.txt", QUESTIONS)  # not a .jsonl file: ignored
            code, out, _ = run_main(["--dummy", "--questions", tmp])
        self.assertEqual(code, 0)
        self.assertEqual(out.splitlines(), [
            "a-source.jsonl: cited the expected page 0/1, said not sure correctly 0/0, wrongly not sure 1, errors 0",
            "b-source.jsonl: cited the expected page 0/2, said not sure correctly 1/1, wrongly not sure 2, errors 0",
            "TOTAL: cited the expected page 0/3, said not sure correctly 1/1, wrongly not sure 3, errors 0",
        ])

    def test_single_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_jsonl(tmp, "one.jsonl", QUESTIONS)
            code, out, _ = run_main(["--dummy", "--questions", str(path)])
        self.assertEqual(code, 0)
        self.assertEqual(len(out.splitlines()), 2)

    def test_no_question_files_exits_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out, err = run_main(["--dummy", "--questions", tmp])
            self.assertEqual(code, 1)
            code_missing, _, _ = run_main(["--dummy", "--questions", str(Path(tmp) / "nope")])
        self.assertEqual(code_missing, 1)
        self.assertEqual(out, "")
        self.assertIn("No question files found", err)

    def test_repo_questions_with_dummy(self):
        code, out, err = run_main(["--dummy"])
        self.assertEqual(code, 0)
        self.assertEqual(err, "")  # every committed question file loads cleanly
        lines = out.splitlines()
        self.assertTrue(lines[-1].startswith("TOTAL: "))
        self.assertIn("student-rules-rushilsagar.jsonl: cited the expected page 0/9, "
                      "said not sure correctly 1/1, wrongly not sure 9, errors 0", lines)


class CommandLineTest(unittest.TestCase):
    def test_runs_as_a_script_from_another_folder(self):
        # `python eval/score.py` from anywhere finds eval/questions next to itself.
        with tempfile.TemporaryDirectory() as tmp:
            done = subprocess.run([sys.executable, str(SCORE_PY), "--dummy"], cwd=tmp,
                                  capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertTrue(done.stdout.splitlines()[-1].startswith("TOTAL: "))

    def test_import_loads_no_agent_packages(self):
        code = (
            "import importlib.util, sys\n"
            f"spec = importlib.util.spec_from_file_location('score', {str(SCORE_PY)!r})\n"
            "spec.loader.exec_module(importlib.util.module_from_spec(spec))\n"
            "print([m for m in ('agent', 'langgraph', 'langchain_core', 'dotenv') if m in sys.modules])\n"
        )
        done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout.strip(), "[]")


def _installed(*names):
    return all(importlib.util.find_spec(n) for n in names)


@unittest.skipUnless(_installed("langchain_core", "langgraph"), "agent packages not installed")
class RealAgentTest(unittest.TestCase):
    """The scorer against the real agent.run.answer, with a scripted model instead of Groq."""

    def test_scores_the_real_answer_function(self):
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from langchain_core.messages import AIMessage

        from agent.graph import build_graph
        from agent.run import answer

        class ScriptedModel:
            def __init__(self, replies):
                self.replies = list(replies)

            def bind_tools(self, tools):
                return self

            def invoke(self, messages):
                return self.replies.pop(0)

        def search(query):
            return AIMessage("", tool_calls=[{"name": "search_policies", "args": {"query": query},
                                              "id": "1", "type": "tool_call"}])

        scripts = {
            "how many q drops do i get": [search("q-drop"), AIMessage(f"Four ({RULE01}).")],
            "how much is a parking permit": [search("parking permit"), AIMessage("It is $100.")],
        }
        counts = score.score(
            [QUESTIONS[0], QUESTIONS[2]],
            lambda q: answer(q, graph=build_graph(ScriptedModel(scripts[q]))),
        )
        self.assertEqual(counts, {"answerable": 1, "cited": 1, "not_sure_questions": 1,
                                  "not_sure_correct": 1, "wrongly_not_sure": 0, "errors": 0})


if __name__ == "__main__":
    unittest.main()
