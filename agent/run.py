"""Ask the AggieFlow agent a question.

    python -m agent.run "when's q drop"
    python -m agent.run --file eval/questions/student-rules-rushilsagar.jsonl

Needs GROQ_API_KEY in your environment or in a .env file at the repo root.
Set AGGIEFLOW_MODEL to try another model (default: groq:openai/gpt-oss-20b).
"""

import argparse
import json
import sys

from agent.checks import finalize
from agent.tools import GROUP_OF

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
    """Which tools ran, round by round: [["course_tools.get_grades(...)", ...], ...]."""
    rounds = []
    for m in messages:
        calls = getattr(m, "tool_calls", None)
        if calls:
            rounds.append([
                f"{GROUP_OF.get(c['name'], '?')}.{c['name']}({json.dumps(c['args'])})"
                for c in calls
            ])
    return rounds


def answer(question: str, graph=None) -> dict:
    """Answer one question. This is what the Scorer (#40) calls.

    Returns {"answer": str, "sources": [passages cited], "trace": [...]}.
    """
    state = (graph or _get_graph()).invoke({"question": question})
    _, cited = finalize(state["messages"][-1].text, state.get("sources", []))
    return {"answer": state["answer"], "sources": cited, "trace": trace(state["messages"])}


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
    args = parser.parse_args()

    if args.file:
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
