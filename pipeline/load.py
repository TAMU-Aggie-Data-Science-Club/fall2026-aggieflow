"""Load validated JSONL passages into MongoDB Atlas.

Run from the repository root (needs MONGODB_URI in .env; run
pipeline/db/setup.py once first):
    python pipeline/load.py                    # every data/processed/*.jsonl
    python pipeline/load.py --source catalog   # one source (repeatable)

Each passage is stored with its id as `_id` (and still in `id`, which the
agent searches on). Writes are upserts with $set, so loading twice leaves the
same documents and a reload keeps fields added later (such as `embedding`).
After a source loads, its documents whose ids weren't in this run are
deleted, so pages that disappeared from the site disappear from the database.

anex.us grades are fetched live by the agent and never stored, so
anex.jsonl is skipped.
"""

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv

if __package__:
    from .check import check_file
else:
    from check import check_file


PROCESSED_DIR = Path(__file__).resolve().parents[1] / "data" / "processed"
COLLECTION = "passages"
DEFAULT_DB = "aggieflow"
BATCH_SIZE = 1000
SKIP_SOURCES = {"anex"}  # fetched live by the agent, never stored


def read_passages(directory=PROCESSED_DIR, sources=None):
    """Validate JSONL files and return passages with counts by source.

    `sources` limits which <source>.jsonl files are read (default: all but
    the skipped ones). Raises ValueError if a file is invalid or missing.
    """
    directory = Path(directory)
    if sources:
        files = [directory / f"{source}.jsonl" for source in sources]
        missing = [path.name for path in files if not path.exists()]
        if missing:
            raise ValueError(f"No such file in {directory}: {', '.join(missing)}")
    else:
        files = sorted(directory.glob("*.jsonl"))
        files = [path for path in files if path.stem not in SKIP_SOURCES]

    if not files:
        raise ValueError(f"No processed JSONL files found in {directory}")

    passages = []
    counts = Counter()
    seen_ids = set()

    for path in files:
        if path.stem in SKIP_SOURCES:
            raise ValueError(f"{path.name} isn't loaded: that source is fetched live")

        errors, warnings, _ = check_file(path)

        if errors:
            details = "; ".join(
                f"line {line}: {message}"
                for line, message in errors[:5]
            )
            raise ValueError(f"Invalid passages in {path.name}: {details}")

        if warnings:
            print(
                f"Warning: {path.name} has {len(warnings)} format warnings",
                file=sys.stderr,
            )

        with path.open(encoding="utf-8") as file:
            for line in file:
                passage = json.loads(line)

                if passage["id"] in seen_ids:
                    raise ValueError(
                        f"Duplicate passage ID across files: {passage['id']}"
                    )

                seen_ids.add(passage["id"])
                passages.append(passage)
                counts[passage["source"]] += 1

    return passages, counts


def upsert_passages(collection, passages, batch_size=BATCH_SIZE):
    """Insert new passages or update existing ones, keyed by id, in batches."""
    from pymongo import UpdateOne

    for start in range(0, len(passages), batch_size):
        batch = passages[start:start + batch_size]
        collection.bulk_write(
            [
                UpdateOne({"_id": p["id"]}, {"$set": p}, upsert=True)
                for p in batch
            ],
            ordered=False,
        )


def remove_stale(collection, passages, sources):
    """Delete documents of the given sources whose ids weren't just loaded.

    Returns the number deleted per source.
    """
    deleted = {}
    for source in sources:
        ids = [p["id"] for p in passages if p["source"] == source]
        result = collection.delete_many({"source": source, "_id": {"$nin": ids}})
        deleted[source] = result.deleted_count
    return deleted


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--source",
        action="append",
        help="load only this source's file (repeat for more than one)",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    load_dotenv()

    try:
        passages, counts = read_passages(sources=args.source)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"Loader error: {error}", file=sys.stderr)
        return 1

    uri = os.getenv("MONGODB_URI")
    database_name = os.getenv("MONGODB_DB") or DEFAULT_DB

    if not uri:
        print("Loader error: Set MONGODB_URI in .env", file=sys.stderr)
        return 1

    try:
        from pymongo import MongoClient
    except ImportError:
        print(
            "Loader error: pymongo is required (pip install -r requirements.txt)",
            file=sys.stderr,
        )
        return 1

    try:
        with MongoClient(uri, serverSelectionTimeoutMS=10000, appname="aggieflow-loader") as client:
            client.admin.command("ping")
            collection = client[database_name][COLLECTION]
            upsert_passages(collection, passages)
            deleted = remove_stale(collection, passages, counts)
            stored = {
                source: collection.count_documents({"source": source})
                for source in counts
            }
    except Exception as error:
        print(
            f"MongoDB load failed: {type(error).__name__}: {error}",
            file=sys.stderr,
        )
        return 1

    for source in sorted(counts):
        print(
            f"{source}: {counts[source]} passages loaded, "
            f"{deleted[source]} stale removed, {stored[source]} in database"
        )

    print(f"TOTAL: {sum(counts.values())} passages loaded into {database_name}.{COLLECTION}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
