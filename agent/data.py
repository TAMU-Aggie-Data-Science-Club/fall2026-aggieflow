"""Where the tools get their passages.

For now this reads the collectors' output, data/processed/<source>.jsonl, into
memory the first time a tool needs it. When MongoDB Atlas is ready, only this
file changes: the tools keep calling search(), course() and grades() and keep
getting passages back.

Set AGGIEFLOW_DATA_DIR to read passages from another folder (the tests do).
"""

import json
import math
import os
import re
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
    found = []
    for p in passages("catalog"):
        if p["id"].startswith(COURSE_PREFIX):
            # 'catalog:course/undergraduate/csce-121-ecen-121:1': cross-listed codes share a page
            key = p["id"].rsplit("/", 1)[-1].split(":")[0]
            if want in _SLUG_CODES.findall(key):
                found.append(p)
    return found


def grades(code: str) -> list[Passage]:
    """anex.us summary for one course: all professors together, with a ranking."""
    dept, number = parse_course(code)
    want = f"anex:{dept.lower()}-{number}:1"
    return [p for p in passages("anex") if p["id"] == want]


def professor_grades(code: str, professor: str) -> list[Passage]:
    """anex.us passages for one professor in one course.

    anex names professors like 'KEYSER J', so 'Keyser', 'keyser j' and
    'John Keyser' all match. Raises ValueError listing who taught the course
    when nobody matches, so the model can try again.
    """
    dept, number = parse_course(code)
    prefix = f"anex:{dept.lower()}-{number}-"
    marker = " grades with "
    by_prof: dict[str, list[Passage]] = {}
    for p in passages("anex"):
        if p["id"].startswith(prefix) and marker in p["title"]:
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
