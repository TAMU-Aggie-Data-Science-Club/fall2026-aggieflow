"""Check the LLM judges (eval/judges.py) against a person's labels (#71).

    python eval/calibrate.py --make   # run the agent on 20 questions, write eval/calibration.jsonl
    (open the file and fill in every "labels" value with "yes", "no" or "unknown")
    python eval/calibrate.py          # run the judges and print % agreement per judge

A judge passes at 85% agreement. Where a judge disagrees with you, its reasoning is
printed so you can fix its prompt. Your label "unknown", a judge answer of "unknown" (or retrieval_relevance
with no passages) isn't counted either way.

Exits 1 if any judge is under 85% or any label is still empty.
"""

import argparse
import json
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "eval")]  # agent/, and score.py + judges.py

import score  # noqa: E402
from judges import JUDGE_MODEL, JUDGES, NOT_SURE, SCORES  # noqa: E402

CALIBRATION = ROOT / "eval" / "calibration.jsonl"
SIZE = 20
NOT_SURE_COUNT = 3  # a few questions the agent should decline
SEED = 71
PASS = 0.85
KEYS = [j.__name__ for j in JUDGES]


RETRY = {"RateLimitError", "APIConnectionError", "APITimeoutError"}  # worth waiting out


def with_retry(fn, *args, tries=8, wait=15, **kwargs):
    """Call fn, waiting out rate limits (Groq's free tier allows a few thousand tokens a minute)."""
    for attempt in range(tries):
        try:
            return fn(*args, **kwargs)
        except Exception as err:
            if type(err).__name__ not in RETRY or attempt == tries - 1:
                raise
            print(f"  {type(err).__name__}, waiting {wait}s", file=sys.stderr)
            time.sleep(wait)


def pick_questions(folder: Path = score.QUESTIONS, size: int = SIZE, seed: int = SEED) -> list[dict]:
    """size questions spread across the files, NOT_SURE_COUNT of them NOT_SURE. Same seed, same pick."""
    rng = random.Random(seed)
    not_sure, by_file = [], []
    for path in score.question_files(folder):
        qs = [q for q in score.load_questions(path) if not score.is_known_gap(q)]
        not_sure += [q for q in qs if q["answer"] == NOT_SURE]
        answerable = [q for q in qs if q["answer"] != NOT_SURE]
        rng.shuffle(answerable)
        by_file.append(answerable)
    picked = rng.sample(not_sure, min(NOT_SURE_COUNT, len(not_sure)))
    while len(picked) < size and any(by_file):  # one from each file in turn
        for qs in by_file:
            if qs and len(picked) < size:
                picked.append(qs.pop())
    return picked


def make(path: Path, force: bool) -> int:
    if path.exists() and not force:
        print(f"{path} exists; it may hold your labels. Pass --force to replace it.", file=sys.stderr)
        return 1
    print(score.run_setup())
    lines = []
    for q in pick_questions(size=2 * SIZE):  # spares, in case some questions fail
        if len(lines) == SIZE:
            break
        print(f"{q['id']}: {q['question']}")
        try:
            result = with_retry(score.agent_answer, q["question"], question_id=q["id"])
        except Exception as err:
            if "Request too large" not in str(err):  # only skip questions too big for Groq's free tier
                raise
            print(f"  skipped: {type(err).__name__}: {str(err)[:150]}", file=sys.stderr)
            continue
        lines.append({
            "id": q["id"],
            "question": q["question"],
            "reference": q["answer"],
            "answer": result["answer"],
            "labels": dict.fromkeys(KEYS),
            "documents": [{k: d.get(k) for k in ("id", "title", "source_url", "text")}
                          for d in result["documents"]],
        })
        # saved after every answer, so a crash late in a long run keeps what's done
        path.write_text("".join(json.dumps(line, ensure_ascii=False) + "\n" for line in lines), encoding="utf-8")
    print(f"\nWrote {len(lines)} answers to {path}. Fill in each \"labels\" value, then run without --make.")
    return 0


def judge_line(line: dict) -> dict:
    """The result of each judge you labeled this line for, by judge name."""
    inputs = {"question": line["question"]}
    outputs = {"answer": line["answer"], "documents": line["documents"]}
    reference = {"answer": line["reference"]}
    return {j.__name__: with_retry(j, inputs, outputs, reference) for j in JUDGES
            if SCORES.get(line["labels"].get(j.__name__)) is not None}


def compare(lines: list[dict], results: list[dict]) -> dict:
    """Per judge: agreed, counted, missing labels, and the disagreements."""
    report = {k: {"agreed": 0, "counted": 0, "missing": 0, "disagreements": []} for k in KEYS}
    for line, result in zip(lines, results):
        for key in KEYS:
            r = report[key]
            label = line["labels"].get(key)
            if label not in SCORES:
                r["missing"] += 1
                continue
            if SCORES[label] is None:  # you couldn't tell: not counted, like the judge's "unknown"
                continue
            got = result[key]["score"]
            if got is None:  # the judge couldn't tell: not counted
                continue
            r["counted"] += 1
            if got == SCORES[label]:
                r["agreed"] += 1
            else:
                r["disagreements"].append((line["id"], label, got, result[key]["comment"]))
    return report


def print_report(report: dict) -> bool:
    ok = True
    verdict_word = {1: "yes", 0: "no"}
    for key, r in report.items():
        pct = r["agreed"] / r["counted"] if r["counted"] else 0.0
        passed = r["counted"] > 0 and pct >= PASS and not r["missing"]
        ok &= passed
        extra = f", {r['missing']} unlabeled" if r["missing"] else ""
        print(f"{key}: {pct:.0%} agreement ({r['agreed']}/{r['counted']}{extra}) "
              f"{'PASS' if passed else 'FAIL'}")
    for key, r in report.items():
        for qid, label, got, comment in r["disagreements"]:
            print(f"\n{key} disagrees on {qid}: you said {label}, judge said {verdict_word[got]}\n  {comment}")
    return ok


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--make", action="store_true", help="run the agent and write the unlabeled file")
    parser.add_argument("--force", action="store_true", help="with --make, replace an existing file")
    parser.add_argument("--file", type=Path, default=CALIBRATION)
    args = parser.parse_args(argv)
    if args.make:
        return make(args.file, args.force)
    if not args.file.exists():
        print(f"No {args.file}. Run with --make first.", file=sys.stderr)
        return 1
    lines = [json.loads(s) for s in args.file.read_text(encoding="utf-8").splitlines() if s.strip()]
    print(f"judges: {JUDGE_MODEL}; {len(lines)} answers in {args.file.name}")
    results = [judge_line(line) for line in lines]
    return 0 if print_report(compare(lines, results)) else 1


if __name__ == "__main__":
    sys.exit(main())
