"""Tool routing tests (#72): which tool does the agent pick for each eval question?

Only the agent's first model call runs: no tools, no database. That makes these
tests fast and cheap, and it isolates routing from search quality.

Run from the repo root (needs GOOGLE_API_KEY in .env):

    uv run pytest -m live tests/test_routing.py --langsmith-output

Each task is scored three ways, logged to LangSmith as feedback:

- retrieval_decision: called a tool if and only if the task expects one
- tool_selection: every tool called is one the task lists
- tool_params: the call's arguments match the task's `args` (only when given)

A confusion matrix of expected vs picked tools prints at the end of the run.
Without LANGSMITH_API_KEY the tests still run; results just aren't uploaded.
"""

import os
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import pytest
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langsmith import testing as t

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "eval"))
from score import QUESTIONS, load_questions, question_files  # noqa: E402

from agent.data import parse_course  # noqa: E402

pytestmark = pytest.mark.live

NO_TOOL = "(no tool)"
# Groq's free tier limits requests and tokens per minute. Wait and retry on a
# rate-limit error instead of failing the task.
RATE_LIMIT_WAITS = [10, 20, 40, 60, 60]


def _tasks() -> list[dict]:
    tasks = []
    for path in question_files(QUESTIONS):
        tasks.extend(load_questions(path))
    return tasks


TASKS = _tasks()
RESULTS: list[tuple[list[str], list[str]]] = []  # (expected tools, tools picked) per task


@pytest.fixture(scope="module")
def agent_node():
    # .env is loaded here, not at import, so offline tests in the same run never see its keys.
    load_dotenv(ROOT / ".env")
    from agent.graph import model_name

    key = "GOOGLE_API_KEY" if model_name().startswith("google_genai:") else "GROQ_API_KEY"
    if not os.environ.get(key):
        pytest.skip(f"needs {key}")
    if not os.environ.get("LANGSMITH_API_KEY"):
        os.environ.setdefault("LANGSMITH_TEST_TRACKING", "false")  # run locally, upload nothing
    from agent.graph import default_model, make_agent_node

    return make_agent_node(default_model())


def first_reply(node, question: str):
    """The agent's first model call, retried when Groq rate-limits us."""
    for wait in [*RATE_LIMIT_WAITS, None]:
        try:
            return node({"messages": [HumanMessage(question)]})["messages"][0]
        except Exception as err:
            if wait is None or not is_rate_limit(err):
                raise
            time.sleep(wait)


def is_rate_limit(err: Exception) -> bool:
    """Groq's 429 'rate limit reached' error, however the client wraps it."""
    text = f"{type(err).__name__} {err}".lower()
    return ("ratelimit" in text.replace(" ", "").replace("_", "")
            or "429" in text or "too many requests" in text)


def _same_value(key: str, expected, actual) -> bool:
    """Course codes compare by parse_course, so 'csce121' equals 'CSCE 121'.
    Other strings compare without case or surrounding spaces."""
    if key == "course":
        try:
            return parse_course(str(actual)) == parse_course(str(expected))
        except ValueError:
            return False
    if isinstance(expected, str) and isinstance(actual, str):
        return expected.strip().lower() == actual.strip().lower()
    return expected == actual


def args_match(expected: dict, calls: list[dict]) -> bool:
    """Every expected argument appears, with the right value, in some call that
    takes it; no call that takes that argument gives a different value."""
    for key, value in expected.items():
        given = [c["args"][key] for c in calls if key in c.get("args", {})]
        if not given or not all(_same_value(key, value, g) for g in given):
            return False
    return True


@pytest.mark.langsmith
@pytest.mark.parametrize("task", TASKS, ids=[q["id"] for q in TASKS])
def test_routing(task, agent_node):
    expected = task.get("tools") or []
    reply = first_reply(agent_node, task["question"])
    calls = [{"name": c["name"], "args": c.get("args", {})} for c in reply.tool_calls]
    picked = [c["name"] for c in calls]
    RESULTS.append((expected, picked))

    t.log_inputs({"question": task["question"], "id": task["id"]})
    t.log_outputs({"tool_calls": calls})
    t.log_reference_outputs({"tools": expected, "args": task.get("args")})

    decision = bool(calls) == bool(expected)
    selection = all(name in expected for name in picked)
    t.log_feedback(key="retrieval_decision", score=int(decision))
    t.log_feedback(key="tool_selection", score=int(selection))
    checks = {"retrieval_decision": decision, "tool_selection": selection}
    if "args" in task:
        params = args_match(task["args"], calls)
        t.log_feedback(key="tool_params", score=int(params))
        checks["tool_params"] = params

    failed = [name for name, ok in checks.items() if not ok]
    assert not failed, f"{', '.join(failed)}: expected {expected or NO_TOOL}, got {calls or NO_TOOL}"


def confusion_matrix(results: list[tuple[list[str], list[str]]]) -> str:
    """Rows: the tools a task expects ('a / b' when either is fine). Columns: the
    tools the agent picked, counted once per task, plus a column for no tool."""
    rows: dict[str, Counter] = defaultdict(Counter)
    columns = set()
    for expected, picked in results:
        row = " / ".join(sorted(expected)) if expected else NO_TOOL
        for col in sorted(set(picked)) or [NO_TOOL]:
            rows[row][col] += 1
            columns.add(col)
    cols = sorted(columns - {NO_TOOL}) + ([NO_TOOL] if NO_TOOL in columns else [])
    labels = sorted(rows)
    width = max(len(r) for r in labels)
    header = " " * width + " | " + " | ".join(cols)
    lines = ["Tool routing: expected (rows) vs picked (columns), tasks counted per tool", header,
             "-" * len(header)]
    for r in labels:
        cells = " | ".join(str(rows[r][c] or ".").rjust(len(c)) for c in cols)
        lines.append(f"{r.ljust(width)} | {cells}")
    return "\n".join(lines)


class _MatrixReport:
    """A small pytest plugin: prints the matrix in the end-of-run summary, where
    pytest's output capture can't hide it."""

    def pytest_terminal_summary(self, terminalreporter):
        if RESULTS:
            terminalreporter.write_sep("=", "tool routing confusion matrix")
            terminalreporter.write_line(confusion_matrix(RESULTS))


@pytest.fixture(scope="module", autouse=True)
def report_matrix(request):
    plugins = request.config.pluginmanager
    if not plugins.has_plugin("routing-matrix"):
        plugins.register(_MatrixReport(), "routing-matrix")
