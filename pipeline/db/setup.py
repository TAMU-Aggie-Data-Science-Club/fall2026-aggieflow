"""Set up the AggieFlow database on MongoDB Atlas.

Run from the repo root (needs MONGODB_URI in .env):
    python pipeline/db/setup.py

Creates, if they don't exist yet:
- the `passages` collection (one document per passage, the Deliverable 3
  passage format; `embedding` gets added later)
- a unique index on `id`, so the loader can replace a passage by its id and
  the agent can look courses up by id
- the Atlas Search index `passages_search` on `title` and `text`, with
  `source` and `id` as filters, used by the agent's search tools

Running it again changes nothing, unless the search index definition below
was edited, in which case the index is updated.
"""

import os
import sys
import time

from dotenv import load_dotenv

COLLECTION = "passages"
DEFAULT_DB = "aggieflow"
SEARCH_INDEX = "passages_search"

# Keyword search on title and text (English stemming, so "drops" finds
# "drop"). `source` limits a search to one source; `id` lets search skip
# catalog course pages, which get_course finds instead.
SEARCH_DEFINITION = {
    "mappings": {
        "dynamic": False,
        "fields": {
            "title": {"type": "string", "analyzer": "lucene.english"},
            "text": {"type": "string", "analyzer": "lucene.english"},
            "source": {"type": "token"},
            "id": {"type": "string", "analyzer": "lucene.keyword"},
        },
    }
}


def ensure_collection(db):
    if COLLECTION in db.list_collection_names():
        print(f"collection {COLLECTION}: already exists")
    else:
        db.create_collection(COLLECTION)
        print(f"collection {COLLECTION}: created")
    return db[COLLECTION]


def ensure_id_index(collection):
    name = collection.create_index("id", unique=True, name="id_unique")
    print(f"index {name}: ready")


def ensure_search_index(collection, wait_seconds=120):
    from pymongo.operations import SearchIndexModel

    existing = {i["name"]: i for i in collection.list_search_indexes()}
    current = existing.get(SEARCH_INDEX)
    if current is None:
        collection.create_search_index(
            SearchIndexModel(definition=SEARCH_DEFINITION, name=SEARCH_INDEX)
        )
        print(f"search index {SEARCH_INDEX}: created")
    elif current.get("latestDefinition", {}).get("mappings") != SEARCH_DEFINITION["mappings"]:
        collection.update_search_index(SEARCH_INDEX, SEARCH_DEFINITION)
        print(f"search index {SEARCH_INDEX}: definition changed, updated")
    else:
        print(f"search index {SEARCH_INDEX}: already up to date")

    # Atlas builds search indexes in the background. Wait a little so the
    # status printed is useful; searches work once it says READY.
    deadline = time.monotonic() + wait_seconds
    while True:
        status = next(iter(collection.list_search_indexes(SEARCH_INDEX)), {}).get("status", "?")
        if status == "READY" or time.monotonic() > deadline:
            break
        time.sleep(5)
    print(f"search index {SEARCH_INDEX}: {status}")


def main():
    load_dotenv()
    uri = os.environ.get("MONGODB_URI")
    if not uri:
        print("Set MONGODB_URI in .env (see .env.example).", file=sys.stderr)
        return 1

    from pymongo import MongoClient

    db_name = os.environ.get("MONGODB_DB", DEFAULT_DB)
    with MongoClient(uri, serverSelectionTimeoutMS=10_000) as client:
        client.admin.command("ping")
        print(f"connected, database {db_name}")
        collection = ensure_collection(client[db_name])
        ensure_id_index(collection)
        ensure_search_index(collection)
    return 0


if __name__ == "__main__":
    sys.exit(main())
