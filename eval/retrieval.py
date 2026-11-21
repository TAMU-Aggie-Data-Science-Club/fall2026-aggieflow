"""Compare keyword, vector and hybrid search on the eval questions, with no LLM (#75).

    uv run python eval/retrieval.py --modes keyword,vector,hybrid --queries raw
    uv run python eval/retrieval.py --judge     # also context precision@5 (LLM judge, slow)

Each answerable question from a search source (student-rules, registrar, oal,
catalog) is sent straight to data.search(source, query, k=10) in every mode.
A hit is a result whose source_url matches the question's (normalize_url).

Prints hit@1, hit@5 and MRR@10 per mode, the same split by source and by tag,
and per-question wins/losses/ties against the first mode with a paired
bootstrap 95% CI. Exits 1 if any vector query still fell back to keyword
search after retries, because then "vector" results are really keyword ones.

Query sets: `raw` is the question as written. `agent` (the query the agent
sent, from #73's traces) isn't available until #73 lands.
"""

import argparse
import os
import random
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "eval")]

from score import NOT_SURE, QUESTIONS, is_known_gap, load_questions, normalize_url, question_files  # noqa: E402

TOOL_SOURCE = {
    "search_student_rules": "student-rules",
    "search_registrar": "registrar",
    "search_tech_help": "oal",
    "search_degree_plans": "catalog",
}
K = 10
VECTOR_GAP_SECONDS = 0.5  # with a payment method on the Atlas org the embedding limit is about 2,000 a minute
RETRIES = 3


def tasks(path: Path) -> list[dict]:
    """Answerable, non-known-gap questions whose expected tools include exactly one search source."""
    out = []
    for f in question_files(path):
        for q in load_questions(f):
            sources = {TOOL_SOURCE[t] for t in q.get("tools", []) if t in TOOL_SOURCE}
            if q["answer"] != NOT_SURE and not is_known_gap(q) and len(sources) == 1:
                out.append({**q, "source": sources.pop()})
    return out


def rank(results: list[dict], url: str) -> int | None:
    """1-based rank of the first result on the expected page, or None."""
    want = normalize_url(url)
    for i, p in enumerate(results, start=1):
        if normalize_url(p.get("source_url") or "") == want:
            return i
    return None


def metrics(ranks: list[int | None]) -> dict:
    n = len(ranks) or 1
    return {
        "hit@1": sum(r == 1 for r in ranks) / n,
        "hit@5": sum(r is not None and r <= 5 for r in ranks) / n,
        "mrr@10": sum(1 / r for r in ranks if r) / n,
    }


def bootstrap_ci(diffs: list[float], resamples: int = 1000, seed: int = 0) -> tuple[float, float]:
    """95% CI for the mean of paired per-question differences."""
    if not diffs:
        return (0.0, 0.0)
    rng = random.Random(seed)
    means = sorted(sum(rng.choices(diffs, k=len(diffs))) / len(diffs) for _ in range(resamples))
    return means[int(0.025 * resamples)], means[int(0.975 * resamples) - 1]


def run_search(data, mode: str, source: str, query: str) -> tuple[list[dict], bool]:
    """Search once in one mode. Returns (results, fell_back). Vector-backed modes
    are paced and retried when Atlas's embedding limit forces a keyword fallback."""
    os.environ["AGGIEFLOW_SEARCH"] = mode
    for attempt in range(RETRIES + 1):
        if mode != "keyword":
            time.sleep(VECTOR_GAP_SECONDS * (attempt + 1))
        before = data.fallback_count
        results = data.search(source, query, k=K)
        if data.fallback_count == before:
            return results, False
    return results, True


def judge_with_wait(judge, question: str, passage: dict) -> dict:
    """One judge call, waiting out Groq's per-minute token limit (429) instead of crashing."""
    while True:
        try:
            return judge({"question": question}, {"documents": [passage]})
        except Exception as err:
            if type(err).__name__ != "RateLimitError":
                raise
            wait = getattr(getattr(err, "response", None), "headers", {}).get("retry-after")
            time.sleep(float(wait) + 1 if wait else 15)


def precision_at_5(judge, question: str, results: list[dict]) -> float | None:
    """Share of the top 5 that the retrieval_relevance judge says answer the question."""
    scores = [judge_with_wait(judge, question, p)["score"] for p in results[:5]]
    scores = [s for s in scores if s is not None]
    return sum(scores) / len(scores) if scores else None


def table(title: str, rows: dict[str, dict]) -> None:
    print(f"\n{title}")
    keys = list(next(iter(rows.values())).keys()) if rows else []
    print(f"  {'':24}" + "".join(f"{k:>10}" for k in keys))
    for name, row in rows.items():
        print(f"  {name:24}" + "".join(f"{v:>10.2f}" if isinstance(v, float) else f"{v!s:>10}" for v in row.values()))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--modes", default="keyword,vector,hybrid")
    parser.add_argument("--queries", default="raw", help="raw (agent needs #73)")
    parser.add_argument("--questions", type=Path, default=QUESTIONS)
    parser.add_argument("--judge", action="store_true", help="also score context precision@5 with the LLM judge")
    parser.add_argument("--judge-sample", type=int, default=0, metavar="N",
                        help="judge only N questions (fixed random sample); 0 = all. Groq's free tier allows ~5 judge calls a minute")
    args = parser.parse_args(argv)
    modes = args.modes.split(",")
    if args.queries != "raw":
        parser.error("only --queries raw for now: the agent query set needs #73's traces")

    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    from agent import data

    if not data.use_atlas():
        parser.error("set MONGODB_URI: vector and hybrid search only exist on Atlas")
    from score import run_setup

    print(run_setup().replace("keyword search", f"search modes {args.modes}"))
    judge = None
    if args.judge:
        from judges import retrieval_relevance as judge

    qs = tasks(args.questions)
    print(f"{len(qs)} questions, modes {', '.join(modes)}, k={K}")
    judged = {q["id"] for q in qs}
    if judge and 0 < args.judge_sample < len(qs):
        judged = set(random.Random(0).sample(sorted(judged), args.judge_sample))
        print(f"precision@5 on a sample of {len(judged)} questions")
    ranks = {m: {} for m in modes}  # mode -> question id -> rank
    precision = {m: [] for m in modes}
    fallbacks = 0
    for q in qs:
        for m in modes:
            results, fell_back = run_search(data, m, q["source"], q["question"])
            fallbacks += fell_back
            ranks[m][q["id"]] = rank(results, q["source_url"])
            if judge and q["id"] in judged and (p := precision_at_5(judge, q["question"], results)) is not None:
                precision[m].append(p)
        print(f"  {q['id']}: " + ", ".join(f"{m} {ranks[m][q['id']] or '-'}" for m in modes), flush=True)

    ids = [q["id"] for q in qs]
    overall = {}
    for m in modes:
        overall[m] = metrics([ranks[m][i] for i in ids])
        if judge:
            overall[m]["prec@5"] = sum(precision[m]) / len(precision[m]) if precision[m] else float("nan")
    table("Overall", overall)

    groups = defaultdict(list)
    for q in qs:
        groups[f"source {q['source']}"].append(q["id"])
        for t in q.get("tags", []):
            groups[f"tag {t}"].append(q["id"])
    for name, members in sorted(groups.items()):
        table(f"{name} ({len(members)})", {m: metrics([ranks[m][i] for i in members]) for m in modes})

    base = modes[0]
    for m in modes[1:]:
        rr = lambda r: 1 / r if r else 0.0  # noqa: E731
        hit5 = lambda r: float(r is not None and r <= 5)  # noqa: E731
        d_mrr = [rr(ranks[m][i]) - rr(ranks[base][i]) for i in ids]
        d_hit = [hit5(ranks[m][i]) - hit5(ranks[base][i]) for i in ids]
        wins, losses = sum(d > 0 for d in d_mrr), sum(d < 0 for d in d_mrr)
        lo_h, hi_h = bootstrap_ci(d_hit)
        lo_m, hi_m = bootstrap_ci(d_mrr)
        print(f"\n{m} vs {base}: {wins} wins, {losses} losses, {len(ids) - wins - losses} ties (by rank)")
        print(f"  hit@5 diff {sum(d_hit) / len(ids):+.3f}, 95% CI [{lo_h:+.3f}, {hi_h:+.3f}]")
        print(f"  MRR diff   {sum(d_mrr) / len(ids):+.3f}, 95% CI [{lo_m:+.3f}, {hi_m:+.3f}]")

    print(f"\nfallbacks: {fallbacks}")
    return 1 if fallbacks else 0


if __name__ == "__main__":
    sys.exit(main())
