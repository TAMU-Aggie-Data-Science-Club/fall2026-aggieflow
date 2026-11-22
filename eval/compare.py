"""Compare two eval experiments question by question (#88, for #76).

    uv run python eval/compare.py eval/results/keyword.jsonl eval/results/vector.jsonl
    uv run python eval/compare.py --a keyword-1.jsonl keyword-2.jsonl --b vector-1.jsonl vector-2.jsonl

A and B are eval/run_eval.py --out files; each side can be several files (one per member).
Only questions on both sides count. Each question's runs are averaged first, then for every
grader and metric this prints the mean in A and B, the difference B minus A, and its paired
bootstrap 95% CI over questions, plus wins / losses / ties on passed.

Each side must be one commit, model and mode, and both sides the same commit and model:
only the search mode (or whatever else you are testing on the same commit) may differ.
--allow-setup-change lets the two sides differ in commit and model too, for before/after-fix
runs or one model against another on the same questions.
"""

import argparse
import sys
from collections import defaultdict
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parent)]

import run_eval  # noqa: E402
from retrieval import bootstrap_ci  # noqa: E402
from summarize import load, mismatch  # noqa: E402


def per_question(recs: list[dict]) -> dict[str, dict[str, float]]:
    """{question id: {metric: mean over its runs}}, with "passed" among the metrics."""
    values = defaultdict(lambda: defaultdict(list))
    for r in recs:
        values[r["id"]]["passed"].append(float(r["passed"]))
        for key, s in r["scores"].items():
            if s is not None:
                values[r["id"]][key].append(float(s))
    return {q: {k: sum(v) / len(v) for k, v in metrics.items()} for q, metrics in values.items()}


def compare(a: list[dict], b: list[dict]) -> dict:
    """{"both": n, "a_only": n, "b_only": n, "rows": [(metric, n, mean_a, mean_b, diff, low, high)],
    "wins": n, "losses": n, "ties": n}. Wins are questions B passed more often than A."""
    qa, qb = per_question(a), per_question(b)
    both = sorted(qa.keys() & qb.keys())
    metrics = sorted({k for q in both for k in qa[q].keys() | qb[q].keys()}, key=lambda k: (k != "passed", k))
    rows = []
    for metric in metrics:
        ids = [q for q in both if metric in qa[q] and metric in qb[q]]
        if not ids:
            continue
        diffs = [qb[q][metric] - qa[q][metric] for q in ids]
        low, high = bootstrap_ci(diffs, resamples=run_eval.BOOTSTRAP, seed=0)
        mean_a = sum(qa[q][metric] for q in ids) / len(ids)
        mean_b = sum(qb[q][metric] for q in ids) / len(ids)
        rows.append((metric, len(ids), mean_a, mean_b, sum(diffs) / len(ids), low, high))
    passed = [qb[q]["passed"] - qa[q]["passed"] for q in both]
    return {"both": len(both), "a_only": len(qa.keys() - qb.keys()), "b_only": len(qb.keys() - qa.keys()),
            "rows": rows, "wins": sum(d > 0 for d in passed), "losses": sum(d < 0 for d in passed),
            "ties": sum(d == 0 for d in passed)}


def label(recs: list[dict]) -> str:
    return f"{recs[0].get('model')}, {recs[0].get('mode')}, commit {recs[0].get('commit')} ({', '.join(sorted({r.get('experiment', '') for r in recs}))})"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("files", nargs="*", type=Path, help="A.jsonl B.jsonl (or use --a and --b)")
    parser.add_argument("--a", nargs="+", type=Path, default=[], help="side A's --out files")
    parser.add_argument("--b", nargs="+", type=Path, default=[], help="side B's --out files")
    parser.add_argument("--allow-setup-change", action="store_true",
                        help="let A and B differ in commit and model (before/after fixes, model vs model)")
    args = parser.parse_args(argv)
    if args.files:
        if len(args.files) != 2 or args.a or args.b:
            parser.error("give exactly two files, A and B, or use --a and --b")
        args.a, args.b = [args.files[0]], [args.files[1]]
    if not args.a or not args.b:
        parser.error("needs both sides: A.jsonl B.jsonl, or --a ... --b ...")

    a, b = load(args.a), load(args.b)
    if not a or not b:
        print("No runs on one side", file=sys.stderr)
        return 1
    for side, recs in (("A", a), ("B", b)):
        if problem := mismatch(recs):
            print(f"Not comparing: side {side}: {problem}", file=sys.stderr)
            return 1
    if not args.allow_setup_change and (problem := mismatch(a[:1] + b[:1], keys=("commit", "model"))):
        print(f"Not comparing: A and B differ in more than the setting under test: {problem}"
              " (pass --allow-setup-change to compare anyway)", file=sys.stderr)
        return 1

    result = compare(a, b)
    print(f"A: {label(a)}\nB: {label(b)}")
    print(f"{result['both']} questions on both sides (only in A: {result['a_only']}, only in B: {result['b_only']})")
    print(f"\n{'metric':<22} {'n':>4} {'A':>7} {'B':>7} {'B - A':>7}  95% CI (paired)")
    for metric, n, mean_a, mean_b, diff, low, high in result["rows"]:
        print(f"{metric:<22} {n:>4} {mean_a:>7.2f} {mean_b:>7.2f} {diff:>+7.2f}  [{low:+.2f}, {high:+.2f}]")
    print(f"\npassed: B wins {result['wins']}, loses {result['losses']}, ties {result['ties']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
