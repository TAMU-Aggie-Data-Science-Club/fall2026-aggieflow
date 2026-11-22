"""Checks that run in code after the model answers. No model calls here.

1. No sources gathered -> "I'm not sure".
2. The model said it's not sure and cited nothing -> "I'm not sure", with no
   sources (it didn't use the passages it was given, so they aren't citations).
3. A passage id, or a bare site name like (anex.us) when only one source is
   from that site, cited in place of a link becomes that link.
   Any link in the answer that no tool returned is removed.
4. A "Sources:" list is added. Live data says when it was fetched.
"""

import re
from urllib.parse import urlsplit

from agent.state import Passage

NOT_SURE = (
    "I'm not sure. I couldn't find this in AggieFlow's sources. "
    "Try the Registrar (https://registrar.tamu.edu) or the Student Rules "
    "(https://student-rules.tamu.edu)."
)

# Stops at brackets, quotes and the full-width 【】 some models (gpt-oss) wrap citations in.
URL = re.compile(r"https?://[^\s)\]>\"'【】]+")

BARE_SITE = re.compile(r"\(((?:www\.)?[a-z0-9-]+(?:\.[a-z0-9-]+)+)\)", re.IGNORECASE)


def _clean(url: str) -> str:
    return url.rstrip(".,;:")


def finalize(answer: str, sources: list[Passage]) -> tuple[str, list[Passage]]:
    """Return (final answer text, passages it cites)."""
    if not sources:
        return NOT_SURE, []

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
        return NOT_SURE, []

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
