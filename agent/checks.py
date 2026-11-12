"""Checks that run in code after the model answers. No model calls here.

1. No sources gathered -> "I'm not sure".
2. Any link in the answer that no tool returned is removed.
3. A "Sources:" list is added. Live data says when it was fetched.
"""

import re

from agent.state import Passage

NOT_SURE = (
    "I'm not sure. I couldn't find this in AggieFlow's sources. "
    "Try the Registrar (https://registrar.tamu.edu) or the Student Rules "
    "(https://student-rules.tamu.edu)."
)

URL = re.compile(r"https?://[^\s)\]>\"']+")


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

    text = URL.sub(keep_or_drop, answer).strip()

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
