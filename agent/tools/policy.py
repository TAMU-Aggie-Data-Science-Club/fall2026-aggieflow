"""policy_tools: search over indexed sources.

PLACEHOLDER. Later this searches the pgvector `passages` table filled by the
collectors (Student Rules, Registrar, OAL, Catalog degree plans,
Transportation static pages). For now it keyword-matches a few canned
passages so we can watch the agent call it.
"""

from langchain_core.tools import tool

from agent.state import Passage

_CANNED: list[tuple[set[str], Passage]] = [
    (
        {"q-drop", "qdrop", "drop"},
        {
            "id": "student-rules:rule01:4",
            "source": "student-rules",
            "title": "Rule 1: Registration – Q-drops (placeholder)",
            "text": "[placeholder] Undergraduates normally get four Q-drops. A course can be "
            "Q-dropped through the 60th class day of a fall or spring semester.",
            "source_url": "https://student-rules.tamu.edu/rule01/",
            "fetched_at": "2026-11-06T00:00:00Z",
        },
    ),
    (
        {"absence", "absent", "excused", "sick", "doctor", "miss"},
        {
            "id": "student-rules:rule07:2",
            "source": "student-rules",
            "title": "Rule 7: Attendance – Absence Documentation (placeholder)",
            "text": "[placeholder] Documentation for an excused absence is due within three "
            "business days of the last date of the absence.",
            "source_url": "https://student-rules.tamu.edu/rule07/",
            "fetched_at": "2026-11-06T00:00:00Z",
        },
    ),
    (
        {"wifi", "wi-fi", "eduroam", "internet", "software"},
        {
            "id": "oal:wifi:1",
            "source": "oal",
            "title": "Wi-Fi on campus (placeholder)",
            "text": "[placeholder] Students connect to the eduroam network with their "
            "NetID@tamu.edu and NetID password.",
            "source_url": "https://www.it.tamu.edu/",
            "fetched_at": "2026-11-06T00:00:00Z",
        },
    ),
]


@tool
def search_policies(query: str, source: str | None = None) -> list[Passage]:
    """Search TAMU rules, policies, registrar info, degree plans, IT help and
    transportation pages. Use for questions about rules, deadlines, Q-drops,
    absences, registration, graduation, degree requirements, Wi-Fi or parking
    rules. `source` can narrow the search to one of: student-rules, registrar,
    oal, catalog, transportation."""
    words = set(query.lower().replace("?", " ").split())
    hits = []
    for keywords, passage in _CANNED:
        if source and passage["source"] != source:
            continue
        if any(k in words or k in query.lower() for k in keywords):
            hits.append(passage)
    return hits


TOOLS = [search_policies]
