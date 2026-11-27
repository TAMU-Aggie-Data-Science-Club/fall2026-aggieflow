"""anex.us grade distributions for the grade tools, fetched live (see the note below)."""

import threading
import time

from agent.data import _WORD, parse_course
from agent.state import Passage


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
