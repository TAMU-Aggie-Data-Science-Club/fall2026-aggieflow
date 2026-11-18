"""Where the tools get their passages.

Searches and course lookups read passages from one of two places:

- MongoDB Atlas, when MONGODB_URI is set (the `passages` collection, filled by
  pipeline/load.py; set up by pipeline/db/setup.py).
- The collectors' files, data/processed/<source>.jsonl, otherwise. Setting
  AGGIEFLOW_DATA_DIR picks the folder and always uses files (the tests do).

Either way the tools get the same passages back. Grades come live from
anex.us (see below), not from the database.
"""

import json
import math
import os
import re
import threading
import time
from collections import Counter
from functools import lru_cache
from pathlib import Path

from agent.state import Passage

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


def search(source: str, query: str, k: int = 5) -> list[Passage]:
    """The k passages from one source that best match the query."""
    if use_atlas():
        return _atlas_search(source, query, k)
    return _index(data_dir(), source).search(query, k)


# --- course and grade lookups -------------------------------------------------

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


# --- anex.us grades: fetched live ---------------------------------------------
# anex.us isn't stored in the database. Each course is fetched when a question
# needs it, turned into passages by the anex collector's own code (so the text
# matches what the eval answers were written from), and kept for ANEX_CACHE_SECONDS.
# Requests go one at a time, at least ANEX_GAP_SECONDS apart: anex.us stops
# answering if it gets many requests in a row.

ANEX_TIMEOUT_SECONDS = 10
ANEX_CACHE_SECONDS = 24 * 60 * 60  # grades only change about three times a year
ANEX_GAP_SECONDS = 1.0

_anex_lock = threading.Lock()
_anex_cache: dict[tuple[str, str], tuple[float, list[Passage]]] = {}
_anex_last_request = 0.0


def _anex_module():
    from pipeline.collect import anex  # the collector: feed URL, parsing, passage text

    return anex


def _fetch_anex(dept: str, number: str) -> str:
    """The raw feed response for one course. Tests replace this."""
    import requests

    global _anex_last_request
    anex = _anex_module()
    wait = ANEX_GAP_SECONDS - (time.monotonic() - _anex_last_request)
    if wait > 0:
        time.sleep(wait)
    _anex_last_request = time.monotonic()
    try:
        resp = requests.post(
            anex.FEED_URL,
            data={"dept": dept, "number": number},
            headers={"User-Agent": anex.USER_AGENT},
            timeout=ANEX_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
    except requests.RequestException as err:
        raise RuntimeError(f"anex.us didn't answer ({type(err).__name__}); try again later") from err
    return resp.text


def _anex_course(dept: str, number: str) -> list[Passage]:
    """All anex passages for one course, live. Ids end in ':live'."""
    key = (dept, number)
    with _anex_lock:
        hit = _anex_cache.get(key)
        if hit and time.monotonic() - hit[0] < ANEX_CACHE_SECONDS:
            return hit[1]
        anex = _anex_module()
        fetched_at = anex.now_utc()
        made = anex.course_passages(dept, number, anex.load_sections(_fetch_anex(dept, number)), fetched_at)
        found = [{**p, "id": p["id"] + ":live"} for p in made]
        _anex_cache[key] = (time.monotonic(), found)
        return found


def grades(code: str) -> list[Passage]:
    """anex.us summary for one course: all professors together, with a ranking."""
    dept, number = parse_course(code)
    return [p for p in _anex_course(dept, number) if p["id"] == f"anex:{dept.lower()}-{number}:1:live"]


def professor_grades(code: str, professor: str) -> list[Passage]:
    """anex.us passages for one professor in one course.

    anex names professors like 'KEYSER J', so 'Keyser', 'keyser j' and
    'John Keyser' all match. Raises ValueError listing who taught the course
    when nobody matches, so the model can try again.
    """
    dept, number = parse_course(code)
    marker = " grades with "
    by_prof: dict[str, list[Passage]] = {}
    for p in _anex_course(dept, number):
        if marker in p["title"]:
            by_prof.setdefault(p["title"].split(marker, 1)[1], []).append(p)
    if not by_prof:
        return []

    asked = set(_WORD.findall(professor.lower()))
    for name, found in by_prof.items():
        parts = name.lower().split()  # 'KEYSER J' -> last name ['keyser']
        last = parts[:-1] if len(parts) > 1 and len(parts[-1]) <= 2 else parts
        if set(last) <= asked:
            return found
    names = ", ".join(sorted(by_prof))
    raise ValueError(
        f"no professor matching {professor!r} taught {dept} {number} since 2023. "
        f"Professors with data: {names}."
    )
