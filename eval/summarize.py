"""Summarize one or more eval/run_eval.py --out files as one table (#88).

    uv run python eval/summarize.py eval/results/agent-keyword-abc1234-*.jsonl

On Groq's free tier a full run is split across members (#89), each running some question
files. This merges their --out files and prints the same summary run_eval.py prints: pass@1
with 95% CIs by source, set and tag, grader averages, latency, fallbacks and refusal errors.

Files from different commits, models or search modes aren't merged: their numbers can't be
added together. Standard library only, so it runs without the agent's packages.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parent)]

import run_eval  # noqa: E402

MUST_MATCH = ("commit", "model", "mode")


def load(paths: list[Path]) -> list[dict]:
    recs = []
    for path in paths:
        with open(path, encoding="utf-8") as f:
            recs += [json.loads(line) for line in f if line.strip()]
    return recs


def mismatch(recs: list[dict], keys=MUST_MATCH) -> str | None:
    """Why these runs can't be merged, or None."""
    for key in keys:
        seen = sorted({str(r.get(key)) for r in recs})
        if len(seen) > 1:
            return f"the files mix {key}s: {', '.join(seen)}"
    return None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("files", nargs="+", type=Path, help="run_eval.py --out files")
    args = parser.parse_args(argv)
    recs = load(args.files)
    if not recs:
        print("No runs in those files", file=sys.stderr)
        return 1
    problem = mismatch(recs)
    if problem:
        print(f"Not merging: {problem}", file=sys.stderr)
        return 1
    for setup in sorted({r.get("setup", "") for r in recs}):
        print(setup)
    experiments = sorted({r.get("experiment", "") for r in recs})
    print(f"{len(recs)} runs from {len(experiments)} experiment(s): {', '.join(experiments)}")
    run_eval.print_summary(run_eval.summarize(recs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
