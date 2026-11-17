
"""Load validated JSONL passages into MongoDB Atlas.

Run from the repository root:
    python pipeline/load.py
"""

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


def read_passages(directory=PROCESSED_DIR):
    """Validate JSONL files and return passages with counts by source."""
    files = sorted(Path(directory).glob("*.jsonl"))

    if not files:
        raise ValueError(f"No processed JSONL files found in {directory}")

    passages = []
    counts = Counter()
    seen_ids = set()

    for path in files:
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


def upsert_passages(collection, passages):
    """Insert new passages or replace existing ones with the same ID."""
    for passage in passages:
        collection.replace_one(
            {"id": passage["id"]},
            passage,
            upsert=True,
        )


def main():
    load_dotenv()

    try:
        passages, counts = read_passages()
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"Loader error: {error}", file=sys.stderr)
        return 1

    uri = os.getenv("MONGODB_URI")
    database_name = os.getenv("MONGODB_DB")

    if not uri or not database_name:
        print(
            "Loader error: Set MONGODB_URI and MONGODB_DB in .env",
            file=sys.stderr,
        )
        return 1

    try:
        from pymongo import MongoClient
    except ImportError:
        print(
            "Loader error: pymongo is required for MongoDB access",
            file=sys.stderr,
        )
        return 1

    try:
        with MongoClient(uri, serverSelectionTimeoutMS=10000) as client:
            client.admin.command("ping")
            collection = client[database_name]["passages"]
            upsert_passages(collection, passages)
    except Exception as error:
        print(
            f"MongoDB load failed: {type(error).__name__}: {error}",
            file=sys.stderr,
        )
        return 1

    for source, count in sorted(counts.items()):
        print(f"{source}: {count} passages loaded")

    print(f"TOTAL: {sum(counts.values())} passages processed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
