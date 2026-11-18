"""Set up the AggieFlow database on MongoDB Atlas.

Run from the repo root (needs MONGODB_URI in .env):
    python pipeline/db/setup.py

Creates, if they don't exist yet:
- the `passages` collection (one document per passage, the Deliverable 3
  passage format)
- a unique index on `id`, so the loader can replace a passage by its id and
  the agent can look courses up by id
- the Atlas Search index `passages_search` on `title` and `text`, with
  `source` and `id` as filters, used by the agent's keyword search
- the Vector Search index `passages_vector`: Atlas embeds each passage's
  `text` itself with Voyage AI's voyage-4 (Automated Embedding), used by the
  agent's vector and hybrid search. Building it embeds every passage, about
  7M tokens of the organization's 200M free ones; re-embedding happens only
  when a passage's text changes or the definition below changes.

Running it again changes nothing, unless an index definition below was
edited, in which case that index is updated.
"""

import os
import sys
import time

from dotenv import load_dotenv

COLLECTION = "passages"
DEFAULT_DB = "aggieflow"
SEARCH_INDEX = "passages_search"
VECTOR_INDEX = "passages_vector"

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

# Semantic search: Atlas embeds `text` and each question with voyage-4.
# 512 dimensions keeps the vectors small on the free M0 cluster.
# `source` limits a search to one source.
VECTOR_DEFINITION = {
    "fields": [
        {"type": "autoEmbed", "modality": "text", "path": "text",
         "model": "voyage-4", "numDimensions": 512},
        {"type": "filter", "path": "source"},
    ]
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


def ensure_index(collection, name, kind, definition, key, wait_seconds=120):
    """Create or update one Atlas Search ("search") or Vector Search
    ("vectorSearch") index. `key` is the part of the definition Atlas echoes
    back, used to tell whether it changed."""
    from pymongo.operations import SearchIndexModel

    existing = {i["name"]: i for i in collection.list_search_indexes()}
    current = existing.get(name)
    if current is None:
        collection.create_search_index(SearchIndexModel(definition=definition, name=name, type=kind))
        print(f"index {name}: created")
    elif current.get("latestDefinition", {}).get(key) != definition[key]:
        collection.update_search_index(name, definition)
        print(f"index {name}: definition changed, updated")
    else:
        print(f"index {name}: already up to date")

    # Atlas builds these in the background (the vector index also embeds every
    # passage, which takes longer). Searches work once it says READY.
    deadline = time.monotonic() + wait_seconds
    while True:
        status = next(iter(collection.list_search_indexes(name)), {}).get("status", "?")
        if status == "READY" or time.monotonic() > deadline:
            break
        time.sleep(5)
    print(f"index {name}: {status}")


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
        ensure_index(collection, SEARCH_INDEX, "search", SEARCH_DEFINITION, "mappings")
        ensure_index(collection, VECTOR_INDEX, "vectorSearch", VECTOR_DEFINITION, "fields")
    return 0


if __name__ == "__main__":
    sys.exit(main())
