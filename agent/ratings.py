"""RateMyProfessors ratings for get_professor_ratings, fetched live (see the note below)."""

import re
import threading
import time

from agent.data import _WORD, parse_course
from agent.grades import _anex_module
from agent.state import Passage


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
