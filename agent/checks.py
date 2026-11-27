"""Checks that run in code after the model answers. No model calls here.

1. No tool called and the model didn't say it's not sure (hi, thanks, "what
   can you do") -> a fixed intro listing what AggieFlow covers. The model picks
   the case; code writes the words, so nothing made up gets through.
2. No sources gathered, or the model said it's not sure and cited nothing ->
   "I'm not sure", pointing to the sites it searched (or, if it searched none,
   to what AggieFlow covers), with no sources.
3. A passage id, or a bare site name like (anex.us) when only one source is
   from that site, cited in place of a link becomes that link.
   Any link in the answer that no tool returned is removed.
4. A "Sources:" list is added. Live data says when it was fetched.
"""

import re
from urllib.parse import urlsplit

from agent.state import Passage

NOT_SURE = "I'm not sure. I couldn't find this in AggieFlow's sources."

COVERS = ("the Student Rules, registrar dates and deadlines, degree plans, the course catalog, "
          "grade distributions, professor ratings, IT help, transportation and the libraries")

INTRO = f"Howdy! I'm AggieFlow. I can answer questions about {COVERS}. What do you need?"

# Where to look when a search found nothing: the site each tool searches.
SITES = {
    "search_student_rules": ("the Student Rules", "https://student-rules.tamu.edu"),
    "search_registrar": ("the Registrar", "https://registrar.tamu.edu"),
    "search_tech_help": ("Technology Services", "https://it.tamu.edu"),
    "search_degree_plans": ("the catalog", "https://catalog.tamu.edu"),
    "get_course": ("the catalog", "https://catalog.tamu.edu"),
    "search_transportation": ("Transportation Services", "https://transport.tamu.edu"),
    "get_course_grades": ("anex.us", "https://anex.us"),
    "get_professor_grades": ("anex.us", "https://anex.us"),
    "get_professor_ratings": ("RateMyProfessors", "https://www.ratemyprofessors.com"),
    "search_libraries": ("the University Libraries", "https://library.tamu.edu"),
    "get_library_hours": ("the Libraries' hours", "https://library.tamu.edu/about/hours.html"),
    "list_library_equipment": ("the Tech Bar", "https://library.tamu.edu/services/techbar.html"),
}


def tools_called(messages: list) -> list[str]:
    """Names of the tools the agent called this turn, in order."""
    return [c["name"] for m in messages for c in (getattr(m, "tool_calls", None) or [])]


def not_sure(called: list[str]) -> str:
    """'Not sure', pointing to the sites the agent searched, or to what AggieFlow covers."""
    sites = list(dict.fromkeys(SITES[name] for name in called if name in SITES))[:2]
    if not sites:
        return f"{NOT_SURE} I can help with {COVERS}."
    return f"{NOT_SURE} Try " + " or ".join(f"{label} ({url})" for label, url in sites) + "."

# Stops at brackets, quotes and the full-width 【】 some models (gpt-oss) wrap citations in.
URL = re.compile(r"https?://[^\s)\]>\"'【】]+")

BARE_SITE = re.compile(r"\(((?:www\.)?[a-z0-9-]+(?:\.[a-z0-9-]+)+)\)", re.IGNORECASE)


def _clean(url: str) -> str:
    return url.rstrip(".,;:")


def finalize(answer: str, sources: list[Passage], called: list[str] = ()) -> tuple[str, list[Passage]]:
    """Return (final answer text, passages it cites). called is the tools the agent
    called this turn, in order."""
    said_not_sure = "not sure" in answer.lower()
    if not called and not sources and not said_not_sure:
        return INTRO, []
    if not sources:
        return not_sure(called), []

    by_url: dict[str, Passage] = {}
    for p in sources:
        by_url.setdefault(p["source_url"], p)

    cited: list[str] = []

    def keep_or_drop(match: re.Match) -> str:
        url = _clean(match.group(0))
        if url in by_url:
            if url not in cited:
                cited.append(url)
            return match.group(0)
        return "[link removed: not from a source]"

    # Some models (Gemini Flash Lite) cite a passage's id instead of its link; swap in the link.
    ids = sorted({p["id"] for p in sources if p.get("source_url")}, key=len, reverse=True)
    if ids:
        url_of = {p["id"]: p["source_url"] for p in sources if p.get("source_url")}
        answer = re.sub("|".join(map(re.escape, ids)), lambda m: url_of[m.group(0)], answer)

    # "(anex.us)": a bare site name becomes the link when only one source is from that site.
    hosts: dict[str, set[str]] = {}
    for url in by_url:
        host = urlsplit(url).netloc.lower().removeprefix("www.")
        hosts.setdefault(host, set()).add(url)

    def site_to_link(match: re.Match) -> str:
        urls = hosts.get(match.group(1).lower().removeprefix("www."), set())
        return f"({next(iter(urls))})" if len(urls) == 1 else match.group(0)

    answer = BARE_SITE.sub(site_to_link, answer)

    text = URL.sub(keep_or_drop, answer).strip()

    if not cited and "not sure" in text.lower():
        return not_sure(called), []

    # A clarifying question ("Which Professor Kim?") cites nothing, so don't pad it with sources.
    if not cited and text.endswith("?"):
        return text, []

    # If the model cited nothing, list everything it was given.
    urls = cited or list(by_url)
    lines = []
    for url in urls:
        p = by_url[url]
        line = f"- {p['title']}: {url}"
        if p["id"].endswith(":live"):
            line += f" (as of {p['fetched_at']})"
        lines.append(line)
    return f"{text}\n\nSources:\n" + "\n".join(lines), [by_url[u] for u in urls]
