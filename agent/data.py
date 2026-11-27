"""Where the tools get their passages.

Searches and course lookups read passages from one of two places:

- MongoDB Atlas, when MONGODB_URI is set (the `passages` collection, filled by
  pipeline/load.py; set up by pipeline/db/setup.py).
- The collectors' files, data/processed/<source>.jsonl, otherwise. Setting
  AGGIEFLOW_DATA_DIR picks the folder and always uses files (the tests do).

On Atlas, AGGIEFLOW_SEARCH picks hybrid (default), keyword or vector search.

Either way the tools get the same passages back. Live sources, not stored in
the database, have their own modules: agent/grades.py (anex.us),
agent/ratings.py (RateMyProfessors) and agent/libcal.py (library hours and equipment).
"""

import json
import logging
import math
import os
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path

from agent.state import Passage

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DIR = ROOT / "data" / "processed"

# Course pages in the catalog are found with course(), not search().
COURSE_PREFIX = "catalog:course/"

# Common words that don't help find a passage.
STOP = set(
    "a an and are at be by can do does for from get how i if in is it many me much my of "
    "on or the to what when where which who why will with you your".split()
)

_WORD = re.compile(r"[a-z0-9]+")
_CODE = re.compile(r"^\s*([A-Za-z]{2,5})\s*-?\s*(\d{3})[A-Za-z]?\s*$")
_SLUG_CODES = re.compile(r"([a-z]{3,4})-(\d{3})")


class NoData(Exception):
    """A source's file hasn't been collected yet."""


def data_dir() -> Path:
    return Path(os.environ.get("AGGIEFLOW_DATA_DIR", DEFAULT_DIR))


def use_atlas() -> bool:
    return bool(os.environ.get("MONGODB_URI")) and "AGGIEFLOW_DATA_DIR" not in os.environ


# --- MongoDB Atlas ------------------------------------------------------------

SEARCH_INDEX = "passages_search"  # created by pipeline/db/setup.py
_HIDE = {"_id": 0, "embedding": 0}  # fields the model never needs


@lru_cache(maxsize=None)
def _collection(uri: str, db_name: str):
    from pymongo import MongoClient

    client = MongoClient(uri, serverSelectionTimeoutMS=5_000, appname="aggieflow-agent")
    return client[db_name]["passages"]


def passages_collection():
    return _collection(os.environ["MONGODB_URI"], os.environ.get("MONGODB_DB", "aggieflow"))


def _atlas_search(source: str, query: str, k: int) -> list[Passage]:
    """Atlas Search in one source.

    Question words (how, many, i, can, my...) are dropped first: Lucene's English
    stopword list keeps them, and they made broad table-of-contents passages
    outrank the right rule. Title and text count equally; boosting titles
    scored worse on the eval questions (Nov 18: 37/45 in the top 5 vs 34/45
    with titles x2, the same as the file search).
    """
    terms = " ".join(_words(query))
    if not terms:
        return []
    stage = {
        "index": SEARCH_INDEX,
        "compound": {
            "filter": [{"equals": {"path": "source", "value": source}}],
            "should": [
                {"text": {"query": terms, "path": "title"}},
                {"text": {"query": terms, "path": "text"}},
            ],
            "minimumShouldMatch": 1,
        },
    }
    if source == "catalog":
        stage["compound"]["mustNot"] = [
            {"wildcard": {"path": "id", "query": COURSE_PREFIX + "*", "allowAnalyzedField": True}}
        ]
    pipeline = [{"$search": stage}, {"$limit": k}, {"$project": _HIDE}]
    return list(passages_collection().aggregate(pipeline))


VECTOR_INDEX = "passages_vector"  # embeds `text` with voyage-4; see pipeline/db/setup.py
RRF_K = 60  # standard reciprocal rank fusion constant
fallback_count = 0  # vector queries answered by keyword search instead; eval/retrieval.py checks it


def _atlas_vector_search(source: str, query: str, k: int) -> list[Passage]:
    """Semantic search in one source. Atlas embeds the question itself, with
    the same model that embedded the passages (Automated Embedding).

    The free cluster has a low limit on how many questions Atlas embeds per
    minute. When Atlas refuses, this falls back to keyword search rather than
    failing the question.
    """
    if not query.strip():
        return []
    # Course pages can't be excluded inside a vector filter (no prefix match),
    # so fetch extra and drop them here.
    extra = 3 * k if source == "catalog" else k
    stage = {
        "index": VECTOR_INDEX,
        "path": "text",
        "query": {"text": query},
        "filter": {"source": {"$eq": source}},
        "numCandidates": max(100, 20 * extra),
        "limit": extra,
    }
    from pymongo.errors import OperationFailure

    try:
        found = list(passages_collection().aggregate([{"$vectorSearch": stage}, {"$project": _HIDE}]))
    except OperationFailure as err:
        if "rate limit" not in str(err).lower():
            raise
        global fallback_count
        fallback_count += 1
        log.warning("Atlas embedding rate limit hit; using keyword search for this query")
        return _atlas_search(source, query, k)
    return [p for p in found if not p["id"].startswith(COURSE_PREFIX)][:k]


def _atlas_hybrid_search(source: str, query: str, k: int) -> list[Passage]:
    """Keyword and vector results merged by reciprocal rank fusion: a passage
    ranked high by either search, or fairly high by both, comes first."""
    depth = max(2 * k, 10)
    scores: dict[str, float] = {}
    by_id: dict[str, Passage] = {}
    for results in (_atlas_search(source, query, depth), _atlas_vector_search(source, query, depth)):
        for rank, p in enumerate(results):
            scores[p["id"]] = scores.get(p["id"], 0.0) + 1.0 / (RRF_K + rank + 1)
            by_id[p["id"]] = p
    merged = [by_id[i] for i in sorted(scores, key=lambda i: -scores[i])]
    return _rerank(query, merged, k)


RERANK_URL = "https://ai.mongodb.com/v1/rerank"
RERANK_MODEL = "rerank-2.5"


def _rerank(query: str, found: list[Passage], k: int) -> list[Passage]:
    """The k passages Voyage's reranker (via Atlas) judges best answer the query.
    Without VOYAGE_API_KEY, or if the call fails, keeps the order given."""
    key = os.environ.get("VOYAGE_API_KEY")
    if not key or len(found) <= 1:
        return found[:k]
    import requests

    try:
        resp = requests.post(
            RERANK_URL,
            headers={"Authorization": f"Bearer {key}"},
            json={"query": query, "documents": [p["text"] for p in found],
                  "model": RERANK_MODEL, "top_k": k},
            timeout=10,
        )
        resp.raise_for_status()
        return [found[r["index"]] for r in resp.json()["data"]]
    except Exception as err:
        log.warning("rerank failed (%s); using hybrid order", err)
        return found[:k]


def _atlas_course_candidates(dept: str, number: str) -> list[Passage]:
    """Catalog course pages whose id mentions the code (checked exactly by course())."""
    pattern = f"^{re.escape(COURSE_PREFIX)}[a-z]+/[a-z0-9-]*{dept.lower()}-{number}[a-z0-9-]*:"
    return list(passages_collection().find({"id": {"$regex": pattern}}, _HIDE))


def _words(text: str) -> list[str]:
    return [w for w in _WORD.findall(text.lower()) if w not in STOP]


@lru_cache(maxsize=None)
def _read(folder: Path, source: str) -> tuple[Passage, ...]:
    path = folder / f"{source}.jsonl"
    if not path.exists():
        raise NoData(
            f"no {source} data yet: run pipeline/collect/{source}.py to create {path.name}"
        )
    with path.open(encoding="utf-8") as f:
        return tuple(json.loads(line) for line in f if line.strip())


def passages(source: str) -> tuple[Passage, ...]:
    return _read(data_dir(), source)


# --- keyword search (BM25) --------------------------------------------------

class _Field:
    """BM25 statistics for one field (title or text) across a source."""

    K1, B = 1.2, 0.75

    def __init__(self, texts):
        self.tfs = [Counter(_words(t)) for t in texts]
        self.lengths = [sum(tf.values()) for tf in self.tfs]
        self.avg = (sum(self.lengths) / len(texts)) or 1 if texts else 1
        df = Counter(w for tf in self.tfs for w in tf)
        n = len(texts)
        self.idf = {w: math.log(1 + (n - c + 0.5) / (c + 0.5)) for w, c in df.items()}

    def score(self, i: int, terms: set[str]) -> float:
        tf, total = self.tfs[i], 0.0
        norm = self.K1 * (1 - self.B + self.B * self.lengths[i] / self.avg)
        for w in terms:
            if w in tf:
                total += self.idf[w] * tf[w] * (self.K1 + 1) / (tf[w] + norm)
        return total


class _Index:
    """BM25 on the text plus BM25 on the title, weighted higher: the title names
    the page's topic, while many pages mention a topic in passing."""

    TITLE_WEIGHT = 2.0

    def __init__(self, docs):
        self.docs = docs
        self.title = _Field([d["title"] for d in docs])
        self.text = _Field([d["text"] for d in docs])

    def search(self, query: str, k: int) -> list[Passage]:
        terms = set(_words(query))
        scored = []
        for i in range(len(self.docs)):
            score = self.text.score(i, terms) + self.TITLE_WEIGHT * self.title.score(i, terms)
            if score > 0:
                scored.append((score, i))
        scored.sort(key=lambda s: -s[0])
        return [self.docs[i] for _, i in scored[:k]]


@lru_cache(maxsize=None)
def _index(folder: Path, source: str) -> _Index:
    docs = _read(folder, source)
    if source == "catalog":
        docs = tuple(d for d in docs if not d["id"].startswith(COURSE_PREFIX))
    return _Index(docs)


SEARCH_MODES = {
    "keyword": _atlas_search,
    "vector": _atlas_vector_search,
    "hybrid": _atlas_hybrid_search,
}


def search_mode() -> str:
    """How Atlas searches: AGGIEFLOW_SEARCH = hybrid (default), keyword or vector (#76).
    The file search is always keyword."""
    mode = os.environ.get("AGGIEFLOW_SEARCH", "hybrid").strip().lower()
    if mode not in SEARCH_MODES:
        raise ValueError(f"AGGIEFLOW_SEARCH={mode!r}: use one of {', '.join(SEARCH_MODES)}")
    return mode


def search(source: str, query: str, k: int = 5) -> list[Passage]:
    """The k passages from one source that best match the query."""
    if use_atlas():
        return SEARCH_MODES[search_mode()](source, query, k)
    return _index(data_dir(), source).search(query, k)


# --- course lookups --------------------------------------------------------

def parse_course(code: str) -> tuple[str, str]:
    """'CSCE 121', 'csce121' or 'CSCE-121' -> ('CSCE', '121')."""
    m = _CODE.match(code)
    if not m:
        raise ValueError(f"{code!r} isn't a course code. Use a code like 'CSCE 121'.")
    return m.group(1).upper(), m.group(2)


def course(code: str) -> list[Passage]:
    """Catalog entries for one course (undergraduate and graduate if both exist)."""
    dept, number = parse_course(code)
    want = (dept.lower(), number)
    candidates = _atlas_course_candidates(dept, number) if use_atlas() else passages("catalog")
    found = []
    for p in candidates:
        if p["id"].startswith(COURSE_PREFIX):
            # 'catalog:course/undergraduate/csce-121-ecen-121:1': cross-listed codes share a page
            key = p["id"].rsplit("/", 1)[-1].split(":")[0]
            if want in _SLUG_CODES.findall(key):
                found.append(p)
    return found
