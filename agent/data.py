"""Where the tools get their passages.

Searches and course lookups read passages from one of two places:

- MongoDB Atlas, when MONGODB_URI is set (the `passages` collection, filled by
  pipeline/load.py; set up by pipeline/db/setup.py).
- The collectors' files, data/processed/<source>.jsonl, otherwise. Setting
  AGGIEFLOW_DATA_DIR picks the folder and always uses files (the tests do).

On Atlas, AGGIEFLOW_SEARCH picks hybrid (default), keyword or vector search.

Either way the tools get the same passages back. Grades come live from
anex.us and professor ratings live from RateMyProfessors (see below), not
from the database.
"""

import json
import logging
import math
import os
import re
import threading
import time
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
    best = sorted(scores, key=lambda i: -scores[i])[:k]
    return [by_id[i] for i in best]


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
_anex_cache: dict[tuple[str, str], tuple[float, list[Passage], list[dict]]] = {}  # time, passages, sections
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


def _anex_entry(dept: str, number: str) -> tuple[list[Passage], list[dict]]:
    """(passages, raw sections) for one course, live and cached. Passage ids end in ':live'."""
    key = (dept, number)
    with _anex_lock:
        hit = _anex_cache.get(key)
        if hit and time.monotonic() - hit[0] < ANEX_CACHE_SECONDS:
            return hit[1], hit[2]
        anex = _anex_module()
        fetched_at = anex.now_utc()
        sections = anex.load_sections(_fetch_anex(dept, number))
        made = anex.course_passages(dept, number, sections, fetched_at)
        found = [{**p, "id": p["id"] + ":live"} for p in made]
        _anex_cache[key] = (time.monotonic(), found, sections)
        return found, sections


def _anex_course(dept: str, number: str) -> list[Passage]:
    """All anex passages for one course, live. Ids end in ':live'."""
    return _anex_entry(dept, number)[0]


def grade_chart(code: str) -> dict | None:
    """Grade counts by professor for one course, for the UI's chart: the same professors
    (since anex.RECENT_SINCE_YEAR, at least anex.MIN_RANKED_STUDENTS graded students) and
    numbers as get_course_grades' ranking. None when no professor qualifies.

    {"course", "source_url", "since", "min_students",
     "professors": [{"name", "sections", "gpa", "counts": {"A", "B", "C", "D", "F", "Q"}}]}
    """
    dept, number = parse_course(code)
    anex = _anex_module()
    ranked = anex.ranked_professors(_anex_entry(dept, number)[1])
    if not ranked:
        return None
    return {
        "course": f"{dept} {number}",
        "source_url": anex.PAGE_URL.format(dept=dept, number=number),
        "since": anex.RECENT_SINCE_YEAR,
        "min_students": anex.MIN_RANKED_STUDENTS,
        "professors": [
            {"name": name, "sections": t.sections, "gpa": round(t.gpa, 2),
             "counts": {g: t.counts[g] for g in [*anex.GRADES, "Q"]}}
            for name, t in ranked
        ],
    }


def grades(code: str) -> list[Passage]:
    """anex.us summary for one course: all professors together, with a ranking."""
    dept, number = parse_course(code)
    return [p for p in _anex_course(dept, number) if p["id"] == f"anex:{dept.lower()}-{number}:1:live"]


def professor_grades(code: str, professor: str) -> list[Passage]:
    """anex.us passages for one professor in one course.

    anex names professors like 'KEYSER J', so 'Keyser', 'keyser j' and
    'John Keyser' all match. Raises ValueError listing who taught the course
    when nobody matches, or the candidates when two share a last name and the
    initial doesn't settle it, so the model can try again.
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
    matches = []  # (name, first initial, passages)
    for name, found in by_prof.items():
        parts = name.lower().split()  # 'KEYSER J' -> last name ['keyser'], initial 'j'
        initial = parts.pop()[0] if len(parts) > 1 and len(parts[-1]) <= 2 else ""
        if set(parts) <= asked:
            matches.append((name, initial, found))
    if len(matches) == 1:
        return matches[0][2]
    if matches:
        # Two professors share a last name ('SMITH A', 'SMITH J'): use the first name's initial.
        by_initial = [m for m in matches if m[1] and any(
            w[0] == m[1] for w in asked - set(m[0].lower().split()))]
        if len(by_initial) == 1:
            return by_initial[0][2]
        names = ", ".join(sorted(m[0] for m in matches))
        raise ValueError(
            f"more than one professor matches {professor!r} in {dept} {number}: {names}. "
            "Ask again with the first name or initial."
        )
    names = ", ".join(sorted(by_prof))
    raise ValueError(
        f"no professor matching {professor!r} taught {dept} {number} since 2023. "
        f"Professors with data: {names}."
    )


# --- RateMyProfessors ratings: fetched live -----------------------------------
# RateMyProfessors has no public API. Its own site calls an undocumented GraphQL
# endpoint, which answers without a real login (the site itself sends the
# placeholder "test:test" credentials). It can change without notice, so a
# failed or reshaped response raises RuntimeError instead of a wrong answer.
# Same pacing as anex: one request at a time, RMP_GAP_SECONDS apart, cached.

RMP_URL = "https://www.ratemyprofessors.com/graphql"
RMP_AUTH = "Basic dGVzdDp0ZXN0"  # base64 of "test:test", what the site's own pages send
RMP_SCHOOL_ID = "U2Nob29sLTEwMDM="  # base64 of "School-1003": Texas A&M, College Station
RMP_TIMEOUT_SECONDS = 10
RMP_CACHE_SECONDS = 6 * 60 * 60  # reviews come in daily during the semester
RMP_GAP_SECONDS = 1.0
RMP_MAX_PROFESSORS = 5  # common last names (Kim, Lee) match many people
RMP_REVIEWS = 10  # newest reviews per professor

_RMP_QUERY = """query($text: String!, $schoolID: ID!, $reviews: Int!) {
  newSearch { teachers(query: {text: $text, schoolID: $schoolID}, first: 10) { edges { node {
    legacyId firstName lastName department
    avgRating avgDifficulty numRatings wouldTakeAgainPercent
    ratings(first: $reviews) { edges { node {
      class comment date qualityRating difficultyRatingRounded grade
    } } }
  } } } }
}"""

_rmp_lock = threading.Lock()
# name -> (time, professors, fetched_at, closest names when the search matched nobody, else None)
_rmp_cache: dict[str, tuple[float, list[dict], str, list[str] | None]] = {}
RMP_PREFIXES = (5, 4, 3)  # letters kept when looking for names close to one that matched nobody
_rmp_last_request = 0.0


def _fetch_rmp(name: str) -> dict:
    """The raw GraphQL response for a professor search at Texas A&M. Tests replace this."""
    import requests

    global _rmp_last_request
    wait = RMP_GAP_SECONDS - (time.monotonic() - _rmp_last_request)
    if wait > 0:
        time.sleep(wait)
    _rmp_last_request = time.monotonic()
    try:
        resp = requests.post(
            RMP_URL,
            json={"query": _RMP_QUERY,
                  "variables": {"text": name, "schoolID": RMP_SCHOOL_ID, "reviews": RMP_REVIEWS}},
            headers={"Authorization": RMP_AUTH, "User-Agent": _anex_module().USER_AGENT},
            timeout=RMP_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        return resp.json()
    except (requests.RequestException, ValueError) as err:
        raise RuntimeError(f"RateMyProfessors didn't answer ({type(err).__name__}); try again later") from err


def _rmp_passage(t: dict, fetched_at: str) -> Passage:
    name = f"{t['firstName']} {t['lastName']}".strip()
    take_again = t.get("wouldTakeAgainPercent")
    summary = (
        f"{name} ({t['department']}, Texas A&M) on RateMyProfessors: overall quality "
        f"{t['avgRating']}/5, difficulty {t['avgDifficulty']}/5"
        + (f", {round(take_again)}% would take again" if take_again is not None and take_again >= 0 else "")
        + f", from {t['numRatings']} ratings."
    )
    if t.get("closestTo"):  # found by correcting a misspelled name (#117)
        summary = (f"No exact match for {t['closestTo']!r}; {name} is the closest name on "
                   f"RateMyProfessors (say so in the answer). " + summary)
    lines = [summary]
    reviews = [e["node"] for e in t["ratings"]["edges"]]
    if reviews:
        lines.append("Newest reviews first:")
    for r in reviews:
        grade = f", grade {r['grade']}" if r.get("grade") else ""
        lines.append(
            f"- {r['date'][:10]}, {r['class']}: quality {r['qualityRating']}/5, "
            f"difficulty {r['difficultyRatingRounded']}/5{grade}. {' '.join(r['comment'].split())}"
        )
    return {
        "id": f"ratemyprofessors:{t['legacyId']}:live",
        "source": "ratemyprofessors",
        "title": f"{name} on RateMyProfessors",
        "text": "\n".join(lines),
        "source_url": f"https://www.ratemyprofessors.com/professor/{t['legacyId']}",
        "fetched_at": fetched_at,
    }


def _taught(t: dict, dept: str, number: str) -> bool:
    """Whether any of a professor's reviews is for this course. Review labels
    vary ('CSCE221', 'CSCE 221', '221'), so a label without a department counts."""
    for e in t["ratings"]["edges"]:
        m = re.fullmatch(r"([A-Za-z]*)\s*-?\s*(\d{3})[A-Za-z]?", e["node"]["class"].strip())
        if m and m.group(2) == number and m.group(1).upper() in ("", dept):
            return True
    return False


RMP_TYPO_MIN_LETTERS = 6  # shorter names are too easy to confuse: 'leik' is close to 'Lei'
RMP_TYPO_SIMILARITY = 0.85  # 'eruhimova'/'Erukhimova' 0.95, 'altemoss'/'Altemose' 0.88, 'hassanikhenar'/'Hassani' 0.7


def _rmp_closest(key: str) -> list[dict]:
    """Professors whose name starts like the longest word of a name that matched nobody:
    RMP matches the start of a name, so 'eru' finds Erukhimova when 'eruhimova' doesn't."""
    word = max(key.split(), key=len)
    for n in RMP_PREFIXES:
        if n < len(word):
            edges = _fetch_rmp(word[:n])["data"]["newSearch"]["teachers"]["edges"]
            if edges:
                return [e["node"] for e in edges[:RMP_MAX_PROFESSORS]]
    return []


def _is_typo_of(word: str, last_name: str) -> bool:
    """Is a RateMyProfessors last name the asked-for word with a small spelling difference?"""
    from difflib import SequenceMatcher

    last = " ".join(_WORD.findall(last_name.lower()))
    return len(word) >= RMP_TYPO_MIN_LETTERS and SequenceMatcher(None, word, last).ratio() >= RMP_TYPO_SIMILARITY


def _name(t: dict) -> str:
    return f"{t['firstName'].strip()} {t['lastName'].strip()}"


def professor_ratings(professor: str, course: str | None = None) -> list[Passage]:
    """RateMyProfessors ratings and newest reviews for Texas A&M professors
    matching a name, most-rated first. Professors with no ratings are left out
    (so [] means they exist but have no ratings); a name that matches nobody raises LookupError.
    With a course, only professors with a review for it are kept, unless none have one."""
    key = " ".join(_WORD.findall(professor.lower()))
    if not key:
        raise ValueError("give a professor's name, like 'Leyk' or 'Teresa Leyk'")
    wanted = parse_course(course) if course else None
    with _rmp_lock:
        hit = _rmp_cache.get(key)
        if hit and time.monotonic() - hit[0] < RMP_CACHE_SECONDS:
            teachers, fetched_at, closest = hit[1], hit[2], hit[3]
        else:
            fetched_at = _anex_module().now_utc()
            raw = _fetch_rmp(key)
            try:
                teachers = [e["node"] for e in raw["data"]["newSearch"]["teachers"]["edges"]]
                closest = None
                if not teachers:  # a misspelling, or no page: look for names that start the same way
                    word = max(key.split(), key=len)
                    near = _rmp_closest(key)
                    teachers = [t for t in near if _is_typo_of(word, t["lastName"])]
                    closest = None if teachers else [_name(t) for t in near]
                    for t in teachers:  # the answer should say the name was corrected
                        t["closestTo"] = professor
                teachers = [t for t in teachers if t["numRatings"] > 0]
                # RMP matches any one word ('John Keyser' finds every John), so
                # professors whose last name was asked for come first.
                asked = set(key.split())
                teachers.sort(key=lambda t: (not set(_WORD.findall(t["lastName"].lower())) <= asked,
                                             -t["numRatings"]))
                teachers = teachers[:RMP_MAX_PROFESSORS]
                [_rmp_passage(t, fetched_at) for t in teachers]  # check the shape before caching
            except (KeyError, TypeError) as err:
                raise RuntimeError("RateMyProfessors changed its response format; the tool needs updating") from err
            _rmp_cache[key] = (time.monotonic(), teachers, fetched_at, closest)
    if closest is not None:  # RMP's search doesn't fuzzy-match: 'eruhimova' finds nobody (#117)
        hint = (f" Names on RateMyProfessors that start the same way: {', '.join(closest)}. These are "
                "different names, so don't give their ratings as this professor's. If one might be the "
                "same person, call ask_user with those names and 'None of these' as options; "
                "otherwise say the professor has no RateMyProfessors page." if closest else "")
        raise LookupError(
            f"no Texas A&M professor on RateMyProfessors matches {professor!r}. Its search needs "
            "the exact spelling: try again with another spelling, the last name only, or the name "
            f"as get_professor_grades or get_course_grades lists it.{hint}")
    if wanted:
        teachers = [t for t in teachers if _taught(t, *wanted)] or teachers
    return [_rmp_passage(t, fetched_at) for t in teachers]


# --- LibCal: library hours and Tech Bar equipment, fetched live (#121) ---------
# The University Libraries run their hours and their Tech Bar equipment lending on
# Springshare LibCal (tamu.libcal.com), which serves both as public JSON with no
# key or login. The hours page on library.tamu.edu draws its tables from the same
# feed with JavaScript, so that page's HTML has no times in it
# (deliverable2/libraries-kaushalp55.md). Hours change for holidays and breaks, so
# they're cached for an hour; the equipment catalog for a day. Same pacing as anex.

LIBCAL = "https://tamu.libcal.com"
LIBCAL_HOURS_URL = f"{LIBCAL}/api_hours_grid.php"
LIBCAL_EQUIPMENT_URL = f"{LIBCAL}/process_equip_cat.php"
LIBRARY_HOURS_PAGE = "https://library.tamu.edu/about/hours.html"  # what students open to check
LIBCAL_HOURS_WIDGET = 150  # the Libraries' hours calendar (LibCal's `iid`)
LIBCAL_HOURS_WEEKS = 2  # LibCal's week starts on Monday; two weeks lets Sunday answer "tomorrow"
LIBCAL_TIMEOUT_SECONDS = 10
LIBCAL_HOURS_CACHE_SECONDS = 60 * 60
LIBCAL_EQUIPMENT_CACHE_SECONDS = 24 * 60 * 60
LIBCAL_GAP_SECONDS = 1.0
LIBCAL_PER_PAGE = 100  # items per equipment request; the biggest category has about 50
LIBCAL_MAX_PAGES = 5
CAMPUS_TZ = "America/Chicago"

# Extra names students use for LibCal hours locations (lid -> words), on top of the words
# in each location's own name.
LIBRARY_ALIASES = {
    1644: {"evans", "main", "sterling"},
    1645: {"evans", "annex", "sterling"},
    3516: {"wcl", "west"},
    1647: {"msl", "medical"},
    3517: {"cushing"},
    3521: {"psel"},
    23383: {"williams", "galveston"},
    11483: {"askus", "chat", "ask"},
}
_LOCATION_NOISE = {"library", "libraries", "the", "hours", "hour", "tamu", "texas", "a", "m",
                   "open", "is", "at", "of", "s", "campus"}

# The two Tech Bars (LibCal equipment location ids). Category ids differ per Tech Bar,
# so each category maps location id -> category id. From tamu.libcal.com/equipment,
# checked Nov 22, 2026; a category missing from a Tech Bar isn't lent there.
TECH_BARS = {20326: "Tech Bar at Evans Library Annex", 20467: "Tech Bar at West Campus Library"}
TECH_BAR_ALIASES = {20326: {"evans", "annex", "sterling", "main"}, 20467: {"west", "wcl"}}
EQUIPMENT_CATEGORIES = {
    "Assistive tech": {20326: 42965, 20467: 49521},
    "Astronomy": {20326: 43020},
    "Audio equipment": {20326: 42970, 20467: 43824},
    "Calculators": {20326: 42841, 20467: 43366},
    "Chargers, cables and adaptors": {20326: 42931, 20467: 43369},
    "Chromebooks": {20326: 42969, 20467: 43370},
    "Computer accessories": {20326: 42986, 20467: 43367},
    "Gadgets and tools": {20326: 42984},
    "Photography accessories": {20326: 42971, 20467: 43372},
    "Cameras": {20326: 42913, 20467: 43368},
    "Projectors": {20326: 42862, 20467: 43371},
    "Video equipment": {20326: 42968, 20467: 43783},
}
# Words a student might use -> category. Anything else is searched by item name (like 'TI-84').
EQUIPMENT_WORDS = {
    "assistive": "Assistive tech", "astronomy": "Astronomy", "telescope": "Astronomy",
    "binocular": "Astronomy", "audio": "Audio equipment", "microphone": "Audio equipment",
    "mic": "Audio equipment", "headphone": "Audio equipment", "speaker": "Audio equipment",
    "recorder": "Audio equipment", "calculator": "Calculators", "charger": "Chargers, cables and adaptors",
    "cable": "Chargers, cables and adaptors", "adapter": "Chargers, cables and adaptors",
    "adaptor": "Chargers, cables and adaptors", "cord": "Chargers, cables and adaptors",
    "chromebook": "Chromebooks", "laptop": "Chromebooks", "accessory": "Computer accessories",
    "mouse": "Computer accessories", "keyboard": "Computer accessories", "webcam": "Computer accessories",
    "accessories": "Computer accessories",
    "gadget": "Gadgets and tools", "tool": "Gadgets and tools", "camera": "Cameras",
    "tripod": "Photography accessories", "lens": "Photography accessories",
    "projector": "Projectors", "video": "Video equipment", "camcorder": "Video equipment",
}

_libcal_lock = threading.Lock()
_libcal_cache: dict[tuple, tuple[float, object, str]] = {}  # key -> (time, data, fetched_at)
_libcal_last_request = 0.0
_TAG = re.compile(r"<[^>]+>")


def _fetch_libcal(url: str, params: dict) -> dict:
    """GET one LibCal JSON endpoint. Tests replace this."""
    import requests

    global _libcal_last_request
    wait = LIBCAL_GAP_SECONDS - (time.monotonic() - _libcal_last_request)
    if wait > 0:
        time.sleep(wait)
    _libcal_last_request = time.monotonic()
    try:
        resp = requests.get(url, params=params, headers={"User-Agent": _anex_module().USER_AGENT},
                            timeout=LIBCAL_TIMEOUT_SECONDS)
        resp.raise_for_status()
        return resp.json()
    except (requests.RequestException, ValueError) as err:
        raise RuntimeError(f"the Libraries' LibCal didn't answer ({type(err).__name__}); try again later") from err


def _libcal_cached(key: tuple, seconds: int, load):
    """(data, fetched_at) for a cache key, calling load() at most once per `seconds`."""
    with _libcal_lock:
        hit = _libcal_cache.get(key)
        if hit and time.monotonic() - hit[0] < seconds:
            return hit[1], hit[2]
        fetched_at = _anex_module().now_utc()
        value = load()
        _libcal_cache[key] = (time.monotonic(), value, fetched_at)
        return value, fetched_at


def campus_today():
    """Today's date in College Station. Tests replace this."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    return datetime.now(ZoneInfo(CAMPUS_TZ)).date()


def _plain_hours(rendered: str) -> str:
    """'7am - 12am' -> '7am - midnight', so closing at 12am isn't read as morning."""
    text = re.sub(r"\b12am\b", "midnight", rendered)
    return re.sub(r"\b12pm\b", "noon", text)


def _pick(found: list[tuple[int, object]], asked: str, what: str, names: list[str]):
    """The best-scoring matches, or LookupError naming what exists."""
    best = max((score for score, _ in found), default=0)
    if best == 0:
        raise LookupError(f"no {what} matches {asked!r}. Try one of: {', '.join(names)}.")
    return [item for score, item in found if score == best]


def library_hours(location: str | None = None) -> list[Passage]:
    """This week's and next week's hours for one library location, live from LibCal.
    Without a location, every library (not the services inside them) that has hours set.
    'Evans' matches both Evans Library and the Evans Annex, which share a building."""

    def load():
        raw = _fetch_libcal(LIBCAL_HOURS_URL, {"iid": LIBCAL_HOURS_WIDGET, "format": "json",
                                              "weeks": LIBCAL_HOURS_WEEKS, "systemTime": 0})
        try:
            return [{"lid": loc["lid"], "name": loc["name"], "category": loc.get("category"),
                     "days": [(d["date"], day, d.get("rendered") or "")
                              for week in loc["weeks"] for day, d in week.items()]}
                    for loc in raw["locations"]]
        except (KeyError, TypeError, AttributeError) as err:
            raise RuntimeError("LibCal changed its hours format; get_library_hours needs updating") from err

    locations, fetched_at = _libcal_cached(("hours",), LIBCAL_HOURS_CACHE_SECONDS, load)
    has_hours = [loc for loc in locations if any(r for _, _, r in loc["days"])]
    if location:
        asked = set(_WORD.findall(location.lower())) - _LOCATION_NOISE
        scored = [(len(asked & (set(_WORD.findall(loc["name"].lower())) | LIBRARY_ALIASES.get(loc["lid"], set()))),
                   loc) for loc in locations]  # a match with no hours set says so, day by day
        chosen = _pick(scored, location, "library location",
                       sorted({loc["name"] for loc in has_hours if loc["category"] == "library"}))
    else:
        chosen = [loc for loc in has_hours if loc["category"] == "library"]

    today = campus_today()
    from datetime import date

    passages = []
    for loc in chosen:
        days = sorted(loc["days"])
        lines = []
        for iso, day, rendered in days:
            d = date.fromisoformat(iso)
            label = f"{day}, {d:%B} {d.day}" + (" (today)" if d == today else "")
            lines.append(f"{label}: {_plain_hours(rendered) if rendered else 'hours not posted'}")
        first, last = date.fromisoformat(days[0][0]), date.fromisoformat(days[-1][0])
        text = (f"{loc['name']} hours, {first:%B} {first.day} to {last:%B} {last.day}, {last.year}, "
                f"from the Libraries' hours calendar. Today is {today:%A, %B} {today.day}, {today.year}. "
                + "; ".join(lines) + ". Hours past midnight run into the next morning.")
        passages.append({
            "id": f"libraries:hours/{loc['lid']}:1:live",
            "source": "libraries",
            "title": f"{loc['name']} hours",
            "text": text,
            "source_url": LIBRARY_HOURS_PAGE,
            "fetched_at": fetched_at,
        })
    return passages


def _short(description: str, words: int = 20) -> str:
    """An item's HTML description as one short line of plain text."""
    import html

    text = " ".join(html.unescape(_TAG.sub(" ", description or "")).split())
    cut = text.split()
    return " ".join(cut[:words]) + ("..." if len(cut) > words else "")


def _equipment_items(lid: int, gid: int, query: str = "") -> list[dict]:
    """Every item in one Tech Bar category (gid 0 = all), following LibCal's pages."""

    def load():
        items, page = [], 1
        while page <= LIBCAL_MAX_PAGES:
            raw = _fetch_libcal(LIBCAL_EQUIPMENT_URL, {"lid": lid, "gid": gid, "perpage": LIBCAL_PER_PAGE,
                                                       "page": page, "q": query})
            try:
                found = [{"name": " ".join(r["NAME"].split()), "category": r["CATEGORY"],
                          "about": _short(r.get("DESCRIPTION", ""))} for r in raw["results"]]
                total = int(raw["total_results"])
            except (KeyError, TypeError, ValueError) as err:
                raise RuntimeError("LibCal changed its equipment format; list_library_equipment needs updating") from err
            items += found
            if not found or len(items) >= total:
                break
            page += 1
        return items

    return _libcal_cached(("equipment", lid, gid, query), LIBCAL_EQUIPMENT_CACHE_SECONDS, load)


def _equipment_text(what: str, items: list[dict]) -> str:
    """One line per item name, with how many copies the catalog lists."""
    copies = Counter(i["name"] for i in items)
    about = {}
    for i in items:
        about.setdefault(i["name"], i)
    lines = []
    for name in sorted(copies, key=str.lower):
        item = about[name]
        extra = [f"{copies[name]} listed"] if copies[name] > 1 else []
        if what == "search":
            extra.append(item["category"])
        if item["about"]:
            extra.append(item["about"])
        lines.append(f"- {name}" + (f" ({'; '.join(extra)})" if extra else ""))
    return "\n".join(lines)


def library_equipment(category: str, location: str | None = None) -> list[Passage]:
    """What the Tech Bars lend in one category, or items whose name matches (like 'TI-84'),
    live from LibCal. One passage per Tech Bar, linking the page where students reserve."""
    exact = [name for name in EQUIPMENT_CATEGORIES if name.lower() == " ".join(category.lower().split())]
    if exact:  # 'Photography accessories' is one category, not cameras plus computer accessories
        kinds = set(exact)
    else:
        words = set(_WORD.findall(category.lower()))
        words |= {w[:-1] for w in words if w.endswith("s") and len(w) > 3}  # calculators -> calculator
        kinds = {EQUIPMENT_WORDS[w] for w in words if w in EQUIPMENT_WORDS}

    bars = list(TECH_BARS)
    if location:
        asked = set(_WORD.findall(location.lower())) - _LOCATION_NOISE
        bars = _pick([(len(asked & TECH_BAR_ALIASES[lid]), lid) for lid in TECH_BARS], location,
                     "Tech Bar", list(TECH_BARS.values()))

    passages = []
    if len(kinds) == 1:  # a kind of device: list the whole category at each Tech Bar
        kind = kinds.pop()
        for lid in bars:
            gid = EQUIPMENT_CATEGORIES[kind].get(lid)
            if gid is None:
                continue
            items, fetched_at = _equipment_items(lid, gid)
            if not items:
                continue
            passages.append({
                "id": f"libraries:equipment/{lid}-{gid}:1:live",
                "source": "libraries",
                "title": f"{kind} at the {TECH_BARS[lid]}",
                "text": (f"{kind} you can borrow from the {TECH_BARS[lid]}, from its equipment catalog "
                         f"({len(items)} listed; this list doesn't show which are checked out right now). "
                         f"Reserving one needs a NetID login on the catalog page.\n"
                         + _equipment_text(kind, items)),
                "source_url": f"{LIBCAL}/equipment?lid={lid}&gid={gid}",
                "fetched_at": fetched_at,
            })
        if not passages:
            where = " or ".join(TECH_BARS[lid] for lid in bars)
            raise LookupError(f"the {where} doesn't lend {kind.lower()}.")
        return passages

    query = " ".join(category.split())
    for lid in bars:  # a model or brand: search item names across every category
        items, fetched_at = _equipment_items(lid, 0, query)
        if items:
            slug = "-".join(_WORD.findall(query.lower())) or "items"
            passages.append({
                "id": f"libraries:equipment/{lid}-search-{slug}:1:live",
                "source": "libraries",
                "title": f"Items matching '{query}' at the {TECH_BARS[lid]}",
                "text": (f"Items at the {TECH_BARS[lid]} whose name matches '{query}', from its equipment "
                         f"catalog ({len(items)} listed; this list doesn't show which are checked out right "
                         f"now). Reserving one needs a NetID login on the catalog page.\n"
                         + _equipment_text("search", items)),
                "source_url": f"{LIBCAL}/equipment?lid={lid}",
                "fetched_at": fetched_at,
            })
    if not passages:
        raise LookupError(
            f"nothing at the Tech Bars matches {category!r}. Kinds of equipment they lend: "
            f"{', '.join(EQUIPMENT_CATEGORIES)}. Try one of those, or a model name like 'TI-84'.")
    return passages
