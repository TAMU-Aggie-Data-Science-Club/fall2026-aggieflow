"""course_tools: live course lookups.

PLACEHOLDER. Later:
- get_course  -> Catalog course-search API (POST .../course-search/api/?page=fose&route=details)
- get_grades  -> anex JSON feed (POST https://anex.us/grades/getData/)
Both get a timeout and a short cache when they go live.
"""

from datetime import datetime, timezone

from langchain_core.tools import tool

from agent.state import Passage


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _split_code(code: str) -> tuple[str, str]:
    """'csce121' or 'CSCE 121' -> ('CSCE', '121')."""
    code = code.upper().replace(" ", "")
    dept = "".join(c for c in code if c.isalpha())
    number = "".join(c for c in code if c.isdigit())
    return dept, number


@tool
def get_course(code: str) -> list[Passage]:
    """Look up one course in the TAMU catalog: title, credit hours,
    description and prerequisites. `code` is like 'CSCE 121'."""
    dept, number = _split_code(code)
    return [{
        "id": f"catalog:{dept}-{number}:live",
        "source": "catalog",
        "title": f"{dept} {number} (placeholder)",
        "text": f"[placeholder] Catalog details for {dept} {number} will appear here.",
        "source_url": f"https://catalog.tamu.edu/search/?P={dept}%20{number}",
        "fetched_at": _now(),
    }]


@tool
def get_grades(dept: str, number: str, prof: str | None = None) -> list[Passage]:
    """Past grade distributions for a course (and optionally one professor)
    from anex.us. Use for 'is this class hard', 'who's the easiest prof',
    or GPA questions. Example: dept='CSCE', number='121'."""
    dept = dept.upper().strip()
    who = f" with {prof}" if prof else ""
    return [{
        "id": f"anex:{dept}-{number}:live",
        "source": "anex",
        "title": f"{dept} {number} grade distribution (placeholder)",
        "text": f"[placeholder] Grade distribution for {dept} {number}{who} will appear here.",
        "source_url": f"https://anex.us/grades/?dept={dept}&number={number}",
        "fetched_at": _now(),
    }]


TOOLS = [get_course, get_grades]
