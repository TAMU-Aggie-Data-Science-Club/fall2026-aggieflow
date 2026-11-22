"""Grade answers the agent already gave with all four LLM judges, without running the agent again.

The answers are in eval/saved/pass3-aa05068.jsonl: the 40-question sample from the pass^3 run
(commit aa05068, first of its 3 runs), each with the passages the agent retrieved.

Each member judges 10 of the 40 questions with their own Groq key (about 10-12 minutes):

    uv run python eval/judge_saved.py judge --ids eval/sample-40-part1.txt   # parts 1 to 4

Needs only GROQ_API_KEY in .env. No Gemini, MongoDB or LangSmith key. Writes
eval/results/judged-<part>.jsonl. Merge everyone's files with:

    uv run python eval/summarize.py eval/results/judged-*.jsonl

The saved file was made once with (needs LANGSMITH_API_KEY for the workspace that holds the run):

    uv run python eval/judge_saved.py export
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "eval")]

import run_eval  # noqa: E402

EXPERIMENT = "Gemini 3.5 Flash Lite · 40 questions × 3 (pass^3) · no judge · aa05068"
RUN_INFO = {  # what the pass^3 run recorded, so summarize.py can check everyone judged the same run
    "experiment": "agent-keyword-aa05068-6ce3493b", "commit": "aa05068",
    "model": "google_genai:gemini-3.5-flash-lite", "mode": "keyword",
    "setup": "setup: google_genai:gemini-3.5-flash-lite at temperature 0; Atlas (aggieflow), "
             "keyword search; commit aa05068; LangSmith tracing on; judged later by eval/judge_saved.py",
}
SAVED = ROOT / "eval" / "saved" / "pass3-aa05068.jsonl"
KEEP = ("answer", "documents", "sources", "calls", "latency_s", "fell_back")  # what grade() reads


def export(path: Path = SAVED) -> int:
    """Copy the first run of each question in EXPERIMENT from LangSmith into path."""
    from langsmith import Client

    client = Client()
    question_id = {e.id: e.metadata.get("id") for e in client.list_examples(dataset_name=run_eval.DATASET)}
    first = {}
    for run in client.list_runs(project_name=EXPERIMENT, is_root=True):
        qid = question_id.get(run.reference_example_id)
        if run.outputs and (qid not in first or run.start_time < first[qid].start_time):
            first[qid] = run
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for qid in sorted(first):
            outputs = {k: first[qid].outputs.get(k) for k in KEEP}
            f.write(json.dumps({"id": qid, "outputs": outputs}, ensure_ascii=False) + "\n")
    print(f"wrote {len(first)} answers to {path}")
    return 0


def judge(ids_file: Path, path: Path = SAVED) -> int:
    """Grade the saved answers for the questions in ids_file against today's eval/questions."""
    from judges import JUDGES

    saved = {r["id"]: r["outputs"] for r in map(json.loads, path.read_text(encoding="utf-8").splitlines())}
    tasks = {t["id"]: t for t in run_eval.load_tasks()}
    wanted = run_eval.read_ids(ids_file)
    missing = [i for i in wanted if i not in saved or i not in tasks]
    if missing:
        print(f"No saved answer or question for: {', '.join(missing)}", file=sys.stderr)
        return 1

    recs = []
    for n, qid in enumerate(wanted, start=1):
        task = tasks[qid]
        meta = {**run_eval.example_fields(task)["metadata"], "question": task["question"]}
        reference = run_eval.example_fields(task)["outputs"]
        graded = run_eval.grade(meta, reference, saved[qid], JUDGES)
        scores = {k: s for k, (s, _) in graded.items()}
        recs.append({**RUN_INFO, "id": qid, "source": task["source"], "set": task.get("set"),
                     "tags": task.get("tags", []), "repetition": 1,
                     "passed": scores.pop("passed", 0) or 0, "scores": scores})
        judged = {k: scores.get(k) for k in ("correctness", "relevance", "groundedness", "retrieval_relevance")}
        print(f"[{n}/{len(wanted)}] {qid}: {judged}", flush=True)

    out = run_eval.RESULTS / f"judged-{ids_file.stem.removeprefix('sample-40-')}.jsonl"
    run_eval.write_records(out, recs)
    print(f"\nresults: {out}\nSend this file to whoever merges the 4 parts.")
    run_eval.print_summary(run_eval.summarize(recs))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("export", help="copy the saved answers from LangSmith (done once already)")
    j = sub.add_parser("judge", help="judge your questions")
    j.add_argument("--ids", type=Path, required=True, help="your part, e.g. eval/sample-40-part1.txt")
    args = parser.parse_args(argv)

    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    return export() if args.command == "export" else judge(args.ids)


if __name__ == "__main__":
    sys.exit(main())
