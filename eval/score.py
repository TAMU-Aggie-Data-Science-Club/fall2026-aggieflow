"""Score AggieFlow against the eval questions.

    python eval/score.py                 # the real agent (agent.run.answer)
    python eval/score.py --dummy         # always "I'm not sure.", no API key needed
    python eval/score.py --d1 deliverable1/rushil.py   # a Deliverable 1 agent
    python eval/score.py --questions eval/questions/student-rules-rushilsagar.jsonl

Reads every eval/questions/*.jsonl file (format in deliverable3/README.md, Part 2) and
prints one line per file plus a TOTAL line:

- cited the expected page: the answer's sources include the question's source_url
- said not sure correctly: a NOT_SURE question got "not sure" and cited nothing
- wrongly not sure: an answerable question got "not sure"
- errors: the answer function raised (counted as a miss; the run keeps going)

Standard library only at import time, so --dummy and the tests run without the
agent's packages installed.
"""

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
QUESTIONS = ROOT / "eval" / "questions"
NOT_SURE = "NOT_SURE"
FIELDS = ("id", "question", "answer", "source_url")
COUNTS = ("answerable", "cited", "not_sure_questions", "not_sure_correct",
          "wrongly_not_sure", "errors")


def normalize_url(url: str) -> str:
    """The part of a URL that says which page it is.

    Drops the scheme, a trailing slash and the #fragment, and lowercases the host,
    because none of those change the page a student lands on. The path and query
    keep their case: some servers treat /Rule01 and /rule01 as different pages.
    """
    parts = urlsplit(url.strip())
    key = parts.netloc.lower() + parts.path.rstrip("/")
    if parts.query:
        key += "?" + parts.query
    return key


def dummy_answer(question: str) -> dict:
    """A baseline that always gives up: every NOT_SURE right, every other question wrong."""
    return {"answer": "I'm not sure.", "sources": []}


def agent_answer(question: str) -> dict:
    """The real agent. Imported here, not at the top, so this file loads without
    langgraph, langchain or dotenv. If they are missing, each question counts as
    an error and the message is printed, instead of the whole run stopping."""
    if str(ROOT) not in sys.path:  # `python eval/score.py` puts eval/ on the path, not the root
        sys.path.insert(0, str(ROOT))
    from agent.run import answer

    return answer(question)


def d1_result(text: str) -> dict:
    """A Deliverable 1 answer in the scorer's shape.

    D1 agents return one string and cite with a "Source: <url>" line (see
    deliverable1/TUTORIAL.md), so every such line becomes a source. The text is
    kept whole: the scorer only looks for "not sure" in it.
    """
    urls = [line[len("Source:"):].strip() for line in text.splitlines()
            if line.startswith("Source:")]
    return {"answer": text, "sources": [{"source_url": url} for url in urls if url]}


def d1_answer_fn(path: Path):
    """An answer function for a Deliverable 1 file, e.g. deliverable1/rushil.py.

    The file builds its graph as `agent` at import, so it is loaded once here and
    not once per question. Loading by path keeps its `if __name__ == "__main__"`
    demo from running, and needs no __init__.py in deliverable1/.
    """
    spec = importlib.util.spec_from_file_location("d1_agent", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # the importlib recipe; typing looks classes up here
    spec.loader.exec_module(module)
    agent = module.agent

    def answer(question: str) -> dict:
        return d1_result(agent.invoke({"question": question})["answer"])

    return answer


def question_files(path: Path) -> list[Path]:
    """A single .jsonl file, or every .jsonl file in a folder."""
    if path.is_file():
        return [path]
    if path.is_dir():
        return sorted(path.glob("*.jsonl"))
    return []


def load_questions(path: Path) -> list[dict]:
    """Questions from one file. Bad lines are reported and skipped, not scored:
    a broken question says nothing about the agent."""
    questions = []
    with open(path, encoding="utf-8") as f:
        for n, line in enumerate(f, start=1):
            if not line.strip():
                continue
            try:
                q = json.loads(line)
            except json.JSONDecodeError as err:
                print(f"{path.name}:{n}: skipped, not valid JSON ({err})", file=sys.stderr)
                continue
            if not isinstance(q, dict) or any(k not in q for k in FIELDS):
                print(f"{path.name}:{n}: skipped, needs {', '.join(FIELDS)}", file=sys.stderr)
                continue
            if q["answer"] != NOT_SURE and not isinstance(q["source_url"], str):
                print(f"{path.name}:{n}: skipped, answerable but source_url is not a URL", file=sys.stderr)
                continue
            questions.append(q)
    return questions


def score(questions: list[dict], answer_fn) -> dict:
    """Run each question through answer_fn and count the results."""
    counts = dict.fromkeys(COUNTS, 0)
    for q in questions:
        expects_not_sure = q["answer"] == NOT_SURE
        counts["not_sure_questions" if expects_not_sure else "answerable"] += 1
        try:
            result = answer_fn(q["question"])
            sources = result["sources"]
            cited = {normalize_url(p["source_url"]) for p in sources if p.get("source_url")}
            said_not_sure = "not sure" in result["answer"].lower()
        except Exception as err:  # a crash is a miss, not the end of the run
            counts["errors"] += 1
            print(f"{q['id']}: error: {type(err).__name__}: {err}", file=sys.stderr)
            continue
        if expects_not_sure:
            if said_not_sure and not sources:
                counts["not_sure_correct"] += 1
        else:
            if normalize_url(q["source_url"]) in cited:
                counts["cited"] += 1
            if said_not_sure:
                counts["wrongly_not_sure"] += 1
    return counts


def report_line(name: str, c: dict) -> str:
    return (f"{name}: cited the expected page {c['cited']}/{c['answerable']}, "
            f"said not sure correctly {c['not_sure_correct']}/{c['not_sure_questions']}, "
            f"wrongly not sure {c['wrongly_not_sure']}, errors {c['errors']}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    agent_choice = parser.add_mutually_exclusive_group()
    agent_choice.add_argument("--dummy", action="store_true",
                              help="use a dummy that always says it is not sure (no API key needed)")
    agent_choice.add_argument("--d1", type=Path, metavar="PATH",
                              help="score a Deliverable 1 agent file instead of the real agent")
    parser.add_argument("--questions", type=Path, default=QUESTIONS,
                        help="a .jsonl file or a folder of them (default: eval/questions)")
    args = parser.parse_args(argv)

    files = question_files(args.questions)
    if not files:
        print(f"No question files found at {args.questions}", file=sys.stderr)
        return 1

    answer_fn = dummy_answer if args.dummy else agent_answer
    if args.d1:
        # Loaded once, so a file that cannot load is a usage error, not 10 errors.
        try:
            answer_fn = d1_answer_fn(args.d1)
        except Exception as err:
            print(f"Could not load {args.d1}: {type(err).__name__}: {err}", file=sys.stderr)
            return 1
    total = dict.fromkeys(COUNTS, 0)
    for path in files:
        counts = score(load_questions(path), answer_fn)
        print(report_line(path.name, counts))
        for key in COUNTS:
            total[key] += counts[key]
    print(report_line("TOTAL", total))
    return 0


if __name__ == "__main__":
    sys.exit(main())
