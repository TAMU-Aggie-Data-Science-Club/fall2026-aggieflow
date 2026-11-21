"""Run the whole agent on every eval task in LangSmith, grade each run, and summarize (#73).

    uv run python eval/run_eval.py --mode keyword --repetitions 3
    uv run python eval/run_eval.py --questions eval/questions/anex-rushilsagar.jsonl --repetitions 1
    uv run python eval/run_eval.py --no-upload --no-judges     # no LangSmith key, code graders only

1. Syncs eval/questions/*.jsonl to the LangSmith dataset "aggieflow-questions". Only
   question ids that aren't in the dataset yet are added; an edited question keeps its old example.
2. Runs agent.run.answer() on each task --repetitions times with client.evaluate().
3. Grades every run (one evaluator, so each LLM judge runs once per run):
   - code graders, 1 or 0:
     cited_page        an answerable task cites its source_url
     not_sure_correct  a NOT_SURE task says "not sure" and cites nothing
     tool_match        it called tools only from the task's "tools" (and none if that's [])
     numbers_match     grade tasks only: every number in the reference answer, and the professor
                       named there, is in the answer (GPA to 2 decimals, % within 1 point, counts within 1%)
   - LLM judges from eval/judges.py: correctness (skipped on grade tasks, where numbers_match
     grades the answer instead), relevance, groundedness, retrieval_relevance
   - path metrics, numbers that never fail a task: rounds, tool_call_count, redundant_calls,
     tool_error_rate, hit_round_limit, recovered (recovery tasks)
   - passed: the run passes when every outcome grader that applies passes: cited_page or
     not_sure_correct, numbers_match or correctness, and tool_match. A judge's "unknown" doesn't count.
4. Prints pass@1 (the average pass rate) and pass^k (passed all k runs) by source, set and tag.

known-gap tasks are skipped. Needs GROQ_API_KEY and MONGODB_URI (for Atlas), and LANGSMITH_API_KEY
unless --no-upload. Experiments are named <area>-<mode>-<commit>, e.g. agent-keyword-284cec7.
"""

import argparse
import json
import os
import re
import sys
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "eval")]  # agent/, and score.py, judges.py, calibrate.py

import score  # noqa: E402

DATASET = "aggieflow-questions"
MODES = ("keyword", "vector", "hybrid")
GRADE_TOOLS = {"get_course_grades", "get_professor_grades"}
NOT_SURE = score.NOT_SURE


# --- tasks and the dataset ----------------------------------------------------

def source_of(path: Path) -> str:
    """'student-rules-rushilsagar.jsonl' -> 'student-rules'; 'extra-krishjayanth.jsonl' -> 'extra'."""
    for prefix in score.DEFAULT_TOOLS:
        if path.name.startswith(prefix):
            return prefix
    return path.stem.split("-")[0]


def load_tasks(path: Path = score.QUESTIONS) -> list[dict]:
    tasks = []
    for file in score.question_files(path):
        for q in score.load_questions(file):
            if not score.is_known_gap(q):
                tasks.append({**q, "source": source_of(file)})
    return tasks


def example_fields(task: dict) -> dict:
    return {
        "inputs": {"question": task["question"]},
        "outputs": {"answer": task["answer"], "source_url": task["source_url"]},
        "metadata": {"id": task["id"], "source": task["source"], "tools": task.get("tools"),
                     "set": task.get("set"), "tags": task.get("tags", [])},
    }


def sync_dataset(client, tasks: list[dict]) -> list:
    """Add tasks whose id isn't in the dataset yet; return the dataset's examples for these tasks."""
    if not client.has_dataset(dataset_name=DATASET):
        client.create_dataset(DATASET, description="AggieFlow eval questions (eval/questions/*.jsonl)")
    existing = {e.metadata.get("id") for e in client.list_examples(dataset_name=DATASET)}
    new = [t for t in tasks if t["id"] not in existing]
    if new:
        client.create_examples(dataset_name=DATASET, examples=[example_fields(t) for t in new])
    print(f"dataset {DATASET}: {len(new)} new examples, {len(existing)} already there")
    by_id = {e.metadata.get("id"): e for e in client.list_examples(dataset_name=DATASET)}
    return [by_id[t["id"]] for t in tasks if t["id"] in by_id]


def local_examples(tasks: list[dict]) -> list:
    """The same examples, in memory, for --no-upload runs (no LangSmith account needed)."""
    from langsmith import schemas

    dataset_id = uuid.uuid5(uuid.NAMESPACE_URL, DATASET)
    now = datetime.now(timezone.utc)
    return [schemas.Example(id=uuid.uuid5(dataset_id, t["id"]), dataset_id=dataset_id,
                            created_at=now, **example_fields(t)) for t in tasks]


# --- code graders ---------------------------------------------------------------

_NUMBER = re.compile(r"(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?(\s?%|\s?percent)?", re.IGNORECASE)
_COURSE = re.compile(r"\b[A-Z]{3,4}\s?$")
_PROFESSOR = re.compile(r"\b([A-Z]{2,}(?:[-'][A-Z]+)?) [A-Z]{1,2}\b(?![a-z\d])")


def numbers_in(text: str, skip_years_and_courses: bool = False) -> list[tuple[str, float]]:
    """[(kind, value)] for every number: kind is "percent", "gpa" (a decimal up to 4.5) or "count"."""
    found = []
    for m in _NUMBER.finditer(text):
        whole, decimal, percent = m.group(1), m.group(2), m.group(3)
        value = float(whole.replace(",", "") + (decimal or ""))
        if skip_years_and_courses and not decimal and not percent:
            if 2000 <= value <= 2035 or _COURSE.search(text[:m.start()]):
                continue
        kind = "percent" if percent else "gpa" if decimal and value <= 4.5 else "count"
        found.append((kind, value))
    return found


def _number_matches(kind: str, value: float, answer_numbers) -> bool:
    for other_kind, other in answer_numbers:
        if kind == "percent" and other_kind == "percent" and abs(other - value) <= 1:
            return True
        if kind == "gpa" and other_kind in ("gpa", "count") and round(other, 2) == round(value, 2):
            return True
        if kind == "count" and other_kind == "count" and abs(other - value) <= 0.01 * value:
            return True
    return False


def numbers_match(answer: str, reference: str) -> tuple[int | None, str]:
    wanted = numbers_in(reference, skip_years_and_courses=True)
    professors = {m.group(1) for m in _PROFESSOR.finditer(reference)}
    if not wanted and not professors:
        return None, "no numbers or professor in the reference"
    have = numbers_in(answer)
    missing = [f"{v:g}{'%' if k == 'percent' else ''}" for k, v in wanted
               if not _number_matches(k, v, have)]
    missing += [name for name in professors if name.lower() not in answer.lower()]
    if missing:
        return 0, "missing or wrong: " + ", ".join(missing)
    return 1, f"all {len(wanted)} numbers{' and the professor' if professors else ''} match"


def is_grade_task(meta: dict) -> bool:
    return bool(GRADE_TOOLS & set(meta.get("tools") or []))


def path_metrics(calls: list[dict], tags: list[str], max_rounds: int) -> dict:
    seen, redundant = set(), 0
    for c in calls:
        key = (c["name"], json.dumps(c["args"], sort_keys=True))
        redundant += key in seen
        seen.add(key)
    errors = [c["error"] for c in calls]
    rounds = max((c["round"] for c in calls), default=0)
    recovered = None
    if "recovery" in tags:
        first_error = next((i for i, e in enumerate(errors) if e), None)
        recovered = int(first_error is not None and not all(errors[first_error:]))
    return {
        "rounds": rounds,
        "tool_call_count": len(calls),
        "redundant_calls": redundant,
        "tool_error_rate": sum(errors) / len(errors) if errors else None,
        "hit_round_limit": int(rounds >= max_rounds),
        "recovered": recovered,
    }


def grade(meta: dict, reference: dict, outputs: dict | None, judges=None, max_rounds: int = 4) -> dict:
    """{key: (score, comment)} for every grader, metric and "passed". judges is a list of
    judge functions (None or [] to skip the LLM judges)."""
    if not outputs or "answer" not in outputs:
        return {"passed": (0, "the agent run failed")}
    answer, expects_not_sure = outputs["answer"], reference["answer"] == NOT_SURE
    cited = {score.normalize_url(p["source_url"]) for p in outputs.get("sources", []) if p.get("source_url")}
    said_not_sure = "not sure" in answer.lower()
    called = [c["name"] for c in outputs.get("calls", [])]
    expected = meta.get("tools")
    grade_task = is_grade_task(meta) and not expects_not_sure

    results = {
        "cited_page": (None, "NOT_SURE task") if expects_not_sure else
        (int(score.normalize_url(reference["source_url"]) in cited), f"cited {sorted(cited)}"),
        "not_sure_correct": (int(said_not_sure and not cited), "") if expects_not_sure else
        (None, "answerable task"),
        "tool_match": (None, "no expected tools") if expected is None else
        (int(set(called) <= set(expected) and bool(called) == bool(expected)),
         f"called {called}, expected {expected}"),
        "numbers_match": numbers_match(answer, reference["answer"]) if grade_task else
        (None, "not a grade task"),
    }
    inputs = {"question": meta.get("question", "")}
    for judge in judges or []:
        name = judge.__name__
        if name == "correctness" and grade_task:
            results[name] = (None, "grade task: numbers_match grades the answer")
            continue
        from calibrate import with_retry

        r = with_retry(judge, inputs, outputs, reference)
        results[name] = (r["score"], r.get("comment", ""))
    for key, value in path_metrics(outputs.get("calls", []), meta.get("tags") or [], max_rounds).items():
        results[key] = (value, "")

    gates = ["not_sure_correct" if expects_not_sure else "cited_page",
             "numbers_match" if grade_task else "correctness", "tool_match"]
    scores = {g: results[g][0] for g in gates if g in results and results[g][0] is not None}
    failed = [g for g, s in scores.items() if s != 1]
    results["passed"] = (int(not failed), f"failed {failed}" if failed else f"passed {sorted(scores)}")
    return results


def make_evaluator(judges, max_rounds: int, questions_by_id: dict):
    def evaluate_run(outputs: dict, reference_outputs: dict, example) -> dict:
        meta = {**example.metadata, "question": questions_by_id.get(example.metadata.get("id"), "")}
        graded = grade(meta, reference_outputs, outputs, judges, max_rounds)
        return {"results": [{"key": k, "score": s, "comment": c} for k, (s, c) in graded.items()]}
    return evaluate_run


# --- summary ----------------------------------------------------------------------

def summarize(rows: list[dict]) -> dict:
    """{"passed": {example_id: [0/1 per run]}, "groups": {group: [example ids]}, "means": {key: avg}}"""
    passed, groups, values = defaultdict(list), defaultdict(set), defaultdict(list)
    for row in rows:
        example = row["example"]
        meta = example.metadata
        results = {r.key: r.score for r in row["evaluation_results"]["results"]}
        passed[example.id].append(results.get("passed", 0) or 0)
        for group in ["all", f"source={meta.get('source')}", f"set={meta.get('set') or 'unset'}",
                      *(f"tag={t}" for t in meta.get("tags") or [])]:
            groups[group].add(example.id)
        for key, s in results.items():
            if s is not None and key != "passed":
                values[key].append(float(s))
    means = {k: sum(v) / len(v) for k, v in sorted(values.items())}
    return {"passed": passed, "groups": groups, "means": means}


def print_summary(summary: dict) -> None:
    passed = summary["passed"]
    k = max((len(runs) for runs in passed.values()), default=0)
    print(f"\n{'group':<28} {'tasks':>5} {'pass@1':>7} {'pass^' + str(k):>7}")
    order = sorted(summary["groups"], key=lambda g: (g != "all", g.split("=")[0], g))
    for group in order:
        ids = summary["groups"][group]
        at1 = sum(sum(passed[i]) / len(passed[i]) for i in ids) / len(ids)
        all_k = sum(all(passed[i]) for i in ids) / len(ids)
        print(f"{group:<28} {len(ids):>5} {at1:>7.0%} {all_k:>7.0%}")
    print("\naverages (graders 0-1, metrics as numbers):")
    for key, mean in summary["means"].items():
        print(f"  {key:<20} {mean:.2f}")


# --- main -------------------------------------------------------------------------

def experiment_prefix(mode: str) -> str:
    from agent.run import git_commit

    commit = git_commit()
    return f"agent-{mode}-{commit.split()[0]}{'-dirty' if '+' in commit else ''}"


def answer_fn(question: str, question_id: str) -> dict:
    """The real agent, retrying rate limits. Tests replace this."""
    from agent.run import answer
    from calibrate import with_retry

    return with_retry(answer, question, metadata={"question_id": question_id})


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--mode", choices=MODES, default="keyword", help="Atlas search mode (default keyword)")
    parser.add_argument("--repetitions", type=int, default=3, help="runs per task (default 3)")
    parser.add_argument("--questions", type=Path, default=score.QUESTIONS,
                        help="a .jsonl file or a folder of them (default: eval/questions)")
    parser.add_argument("--no-judges", action="store_true", help="skip the LLM judges (code graders only)")
    parser.add_argument("--no-upload", action="store_true",
                        help="run locally without LangSmith (no dataset, no experiment)")
    args = parser.parse_args(argv)

    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    os.environ["AGGIEFLOW_SEARCH"] = args.mode
    from agent.graph import MAX_ROUNDS
    from langsmith import Client

    tasks = load_tasks(args.questions)
    if not tasks:
        print(f"No tasks found at {args.questions}", file=sys.stderr)
        return 1
    print(score.run_setup())
    ids = {t["question"]: t["id"] for t in tasks}
    judges = []
    if not args.no_judges:
        from judges import JUDGES

        judges = JUDGES

    def target(inputs: dict) -> dict:
        return answer_fn(inputs["question"], ids.get(inputs["question"], ""))

    if args.no_upload:
        os.environ["LANGSMITH_TRACING"] = "false"  # send nothing, even if .env turns tracing on
        client = Client(api_key="unused", auto_batch_tracing=False)
        examples = local_examples(tasks)
    else:
        client = Client()
        examples = sync_dataset(client, tasks)
    prefix = experiment_prefix(args.mode)
    results = client.evaluate(
        target, data=examples,
        evaluators=[make_evaluator(judges, MAX_ROUNDS, {t["id"]: t["question"] for t in tasks})],
        num_repetitions=args.repetitions, experiment_prefix=prefix, max_concurrency=1,
        upload_results=not args.no_upload,
        metadata={"mode": args.mode, "repetitions": args.repetitions, "judges": bool(judges)},
    )
    rows = list(results)
    if not args.no_upload:
        print(f"experiment: {results.experiment_name}")
    print_summary(summarize(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
