"""Ask the AggieFlow agent a question.

    python -m agent.run "when's q drop"
    python -m agent.run --file eval/questions/student-rules-rushilsagar.jsonl
    python -m agent.run --chat        (a conversation: follow-ups use earlier turns)

Needs GOOGLE_API_KEY in your environment or in a .env file at the repo root.
Set AGGIEFLOW_MODEL to try another model (default: google_genai:gemini-3.5-flash-lite, temperature 0).
Set LANGSMITH_TRACING=true and LANGSMITH_API_KEY to send each run to LangSmith (see .env.example).
"""

import argparse
import json
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

from agent.checks import finalize, tools_called
from agent.tools import GROUP_OF

ROOT = Path(__file__).resolve().parent.parent
_graph = None


def _get_graph():
    global _graph
    if _graph is None:
        from dotenv import load_dotenv

        from agent.graph import build_graph

        load_dotenv()
        _graph = build_graph()
    return _graph


def trace(messages) -> list[list[str]]:
    """Which tools ran, round by round: [["course_tools.get_course_grades(...)", ...], ...]."""
    rounds = []
    for m in messages:
        calls = getattr(m, "tool_calls", None)
        if calls:
            rounds.append([
                f"{GROUP_OF.get(c['name'], '?')}.{c['name']}({json.dumps(c['args'])})"
                for c in calls
            ])
    return rounds


def tool_calls(messages) -> list[dict]:
    """Every tool call in order: {"round", "name", "args", "error"}, where error is True
    when the tool's result was an "Error: ..." message (the tools node reports failures
    to the model that way instead of crashing). Path metrics in eval/run_eval.py read this."""
    results = {m.tool_call_id: m.content for m in messages if getattr(m, "tool_call_id", None)}
    calls, round_number = [], 0
    for m in messages:
        if getattr(m, "tool_calls", None):
            round_number += 1
            for c in m.tool_calls:
                result = results.get(c["id"], "")
                calls.append({"round": round_number, "name": c["name"], "args": c["args"],
                              "error": isinstance(result, str) and result.startswith("Error:")})
    return calls


@lru_cache(maxsize=1)
def git_commit() -> str:
    """The short commit hash, plus " + uncommitted changes" if tracked files changed."""
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                                capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT,
                               capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return commit + (" + uncommitted changes" if dirty else "")


def run_metadata() -> dict:
    """What this run used, attached to every LangSmith trace so runs can be filtered and compared."""
    from agent import data
    from agent.graph import TEMPERATURE, model_name

    return {
        "model": model_name(),
        "temperature": TEMPERATURE,
        "search": data.search_mode() if data.use_atlas() else "local-keyword",
        "commit": git_commit(),
    }


def answer(question: str, graph=None, metadata: dict | None = None,
           history: list[dict] | None = None) -> dict:
    """Answer one question. This is what the Scorer (#40) and members' evals call.

    history is the conversation so far, oldest first:
    [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}].
    The caller keeps it and sends it every turn; nothing is stored between calls.

    metadata is added to the LangSmith trace, e.g. {"question_id": "sr-03"}.
    The model, temperature, search mode and git commit are always added.

    Returns {
        "answer": str,
        "sources": [passages cited in the answer],
        "documents": [every passage the tools returned, cited or not],
        "trace": [[tool calls], ...] round by round,
        "calls": [{"round", "name", "args", "error"}, ...] every tool call in order,
    }
    "documents" is what groundedness and retrieval-relevance judges read.
    """
    graph = graph or _get_graph()
    config = {"run_name": "aggieflow", "metadata": {**run_metadata(), **(metadata or {})}}
    state = graph.invoke({"question": question, "history": history or []}, config=config)
    retrieved = state.get("sources", [])
    _, cited = finalize(state["messages"][-1].text, retrieved, tools_called(state["messages"]))
    documents = list({p["id"]: p for p in retrieved}.values())  # each passage once, in order found
    return {"answer": state["answer"], "sources": cited, "documents": documents,
            "trace": trace(state["messages"]), "calls": tool_calls(state["messages"])}


def _print(question: str, result: dict) -> None:
    print(f"Q: {question}")
    for i, calls in enumerate(result["trace"], start=1):
        print(f"  round {i}: " + " | ".join(calls))
    if not result["trace"]:
        print("  (no tools called)")
    print("A: " + result["answer"].replace("\n", "\n   "))
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("question", nargs="?", help="the question to ask")
    parser.add_argument("--file", help="a .jsonl file of eval questions to run")
    parser.add_argument("--chat", action="store_true", help="have a conversation (empty line to quit)")
    args = parser.parse_args()

    if args.chat:
        history = []
        while question := input("you> ").strip():
            result = answer(question, history=history)
            _print(question, result)
            history += [{"role": "user", "content": question},
                        {"role": "assistant", "content": result["answer"]}]
    elif args.file:
        with open(args.file, encoding="utf-8") as f:
            for line in f:
                q = json.loads(line)
                try:
                    result = answer(q["question"])
                except Exception as err:  # keep going through the file
                    print(f"Q: {q['question']}\n  ERROR: {err}\n")
                    continue
                _print(q["question"], result)
                got = [p["source_url"] for p in result["sources"]]
                print(f"   expected: {q['source_url']}  cited: {got}\n")
    elif args.question:
        _print(args.question, answer(args.question))
    else:
        parser.print_help()
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
