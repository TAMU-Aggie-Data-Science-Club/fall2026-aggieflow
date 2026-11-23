"""Ask the AggieFlow agent a question.

    python -m agent.run "when's q drop"
    python -m agent.run --file eval/questions/student-rules-rushilsagar.jsonl
    python -m agent.run --chat        (a conversation: follow-ups use earlier turns)

Needs GOOGLE_API_KEY in your environment or in a .env file at the repo root.
Set AGGIEFLOW_MODEL to try another model (default: google_genai:gemini-3.5-flash-lite, temperature 0).
Set LANGSMITH_TRACING=true and LANGSMITH_API_KEY to send each run to LangSmith (see .env.example).
Set AGGIEFLOW_CHECKPOINTS=atlas to keep conversations (threads) in Atlas instead of memory.
"""

import argparse
import json
import os
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

from langgraph.types import Command

from agent.graph import question_text
from agent.tools import GROUP_OF

ROOT = Path(__file__).resolve().parent.parent
CHECKPOINT_TTL_SECONDS = 7 * 24 * 60 * 60  # Atlas deletes a thread's checkpoints a week after they're written
_graphs = {}


def checkpointer():
    """Where threads are kept. AGGIEFLOW_CHECKPOINTS=atlas: the checkpoints and
    checkpoint_writes collections next to the passages, which needs a MONGODB_URI user
    that can write (members' read-only user can't). Otherwise memory: threads last
    until the process restarts."""
    if os.environ.get("AGGIEFLOW_CHECKPOINTS") == "atlas":
        from langgraph.checkpoint.mongodb import MongoDBSaver
        from pymongo import MongoClient

        client = MongoClient(os.environ["MONGODB_URI"], serverSelectionTimeoutMS=5_000,
                             appname="aggieflow-checkpoints")
        return MongoDBSaver(client, db_name=os.environ.get("MONGODB_DB", "aggieflow"),
                            ttl=CHECKPOINT_TTL_SECONDS)
    from langgraph.checkpoint.memory import InMemorySaver

    return InMemorySaver()


def _get_graph(threads: bool = False):
    """The agent graph, built once. threads=True compiles it with checkpointer(), for
    answers in a thread; without a thread nothing is stored, as in evals."""
    if threads not in _graphs:
        from dotenv import load_dotenv

        from agent.graph import build_graph, default_model

        load_dotenv()
        model = _graphs["model"] = _graphs.get("model") or default_model()
        _graphs[threads] = build_graph(model, checkpointer() if threads else None)
    return _graphs[threads]


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
           history: list[dict] | None = None, thread_id: str | None = None) -> dict:
    """Answer one question. This is what the Scorer (#40) and members' evals call.

    history is the conversation so far, oldest first:
    [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}].
    Without thread_id the caller keeps it and sends it every turn, and nothing is stored.
    With thread_id the conversation is kept between calls (see checkpointer()), and
    history only starts a thread that has no messages yet.

    metadata is added to the LangSmith trace, e.g. {"question_id": "sr-03"}.
    The model, temperature, search mode and git commit are always added.

    Returns {
        "answer": str,
        "sources": [passages cited in the answer],
        "documents": [every passage the tools returned, cited or not],
        "trace": [[tool calls], ...] round by round,
        "calls": [{"round", "name", "args", "error"}, ...] every tool call in order,
        "question": {"prompt", "options"} when the agent asked the student instead of
                    answering (ask_user), else None. "answer" is then the question as text.
    }
    "documents" is what groundedness and retrieval-relevance judges read.

    In a thread that is waiting on such a question, `question` is the student's reply
    (an option or their own words) and the paused turn goes on from there.
    """
    graph = graph or _get_graph(threads=thread_id is not None)
    config = {"run_name": "aggieflow", "metadata": {**run_metadata(), **(metadata or {})}}
    if thread_id is not None:
        config["configurable"] = {"thread_id": thread_id}
    if thread_id is not None and graph.get_state(config).interrupts:
        inputs = Command(resume=question)  # the student's reply to ask_user
    else:
        inputs = {"question": question, "history": history or []}
    state = graph.invoke(inputs, config=config)
    retrieved = state.get("sources", [])
    documents = list({p["id"]: p for p in retrieved}.values())  # each passage once, in order found
    result = {"trace": trace(state["messages"]), "calls": tool_calls(state["messages"]),
              "documents": documents, "question": None}
    if state.get("__interrupt__"):  # paused on ask_user: the student's reply resumes it
        asked = state["__interrupt__"][0].value
        return {**result, "answer": question_text(asked), "sources": [], "question": asked}
    return {**result, "answer": state["answer"], "sources": state["cited"]}


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
