"""Pick the questions to run 2 more times after the release run's first pass (#74).

    uv run python eval/release_rerun.py eval/results/release-part*.jsonl

Reruns every question that failed its first run, plus every ask-* and multiturn-* question
(newer, so their reliability isn't known yet). Writes eval/release-rerun.txt (all of them) and
eval/release-rerun-part1.txt to part4.txt (split evenly, one per Groq key). Standard library only.
"""

import argparse
import json
import sys
from pathlib import Path

EVAL = Path(__file__).resolve().parent
ALWAYS = ("ask-", "multiturn-")
PARTS = 4


def rerun_ids(recs: list[dict]) -> list[str]:
    """Ids that failed any run or always get rerun, in first-seen order."""
    ids = {}
    for r in recs:
        if not r["passed"] or r["id"].startswith(ALWAYS):
            ids[r["id"]] = True
    return list(ids)


def write(path: Path, header: str, ids: list[str]) -> None:
    path.write_text(f"# {header}\n" + "".join(i + "\n" for i in ids), encoding="utf-8")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("files", nargs="+", type=Path, help="the first pass's run_eval.py --out files")
    parser.add_argument("--out-dir", type=Path, default=EVAL, help="where to write the lists (default eval/)")
    args = parser.parse_args(argv)
    recs = [json.loads(line) for f in args.files for line in f.read_text(encoding="utf-8").splitlines() if line.strip()]
    ids = rerun_ids(recs)
    if not ids:
        print("Nothing to rerun", file=sys.stderr)
        return 1
    failed = sum(not r["passed"] for r in recs)
    write(args.out_dir / "release-rerun.txt",
          f"#74 reruns: {len(ids)} questions ({failed} failed first runs, plus every ask-* and multiturn-*)", ids)
    for n in range(PARTS):
        part = ids[n::PARTS]
        write(args.out_dir / f"release-rerun-part{n + 1}.txt", f"Rerun part {n + 1} of {PARTS}: {len(part)} questions", part)
    print(f"{len(ids)} questions to rerun ({failed} failed first runs); wrote release-rerun.txt and {PARTS} parts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
