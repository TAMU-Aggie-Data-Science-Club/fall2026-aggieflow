"""Check processed passage files against the Deliverable 3 passage format.

Every Track A collector writes data/processed/<source>.jsonl, one passage per
line. This script reads those files and reports every line that breaks the
format in deliverable3/README.md, so problems are caught before the loader
puts them in the database.

Run from the repo root:
    python pipeline/check.py data/processed/student-rules.jsonl
    python pipeline/check.py data/processed/*.jsonl

Errors break the format and make the script exit with status 1. Warnings are
worth a look but are allowed (a short rule section, a file with an odd name).
Standard library only.
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path

SOURCES = {"anex", "catalog", "oal", "registrar", "student-rules", "transportation"}
FIELDS = ("id", "source", "title", "text", "source_url", "fetched_at")

MIN_WORDS = 100     # the README asks for about 100-400 words per passage
MAX_WORDS = 400
HUGE_WORDS = 800    # twice the ceiling: the page was almost certainly not split

# <source>:<page key>:<chunk number>. The page key may itself contain colons.
ID_FORMAT = re.compile(r"^(?P<source>[a-z-]+):(?P<key>\S+):(?P<chunk>\d+)$")
FETCHED_AT_FORMAT = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
# A real tag such as <p>, </div> or <br/>; "x < 5 and y > 3" is not one.
HTML_TAG = re.compile(r"</?[a-zA-Z][a-zA-Z0-9-]*(\s[^<>]*)?/?>")
HTML_ENTITY = re.compile(r"&(#\d+|#x[0-9a-fA-F]+|[a-zA-Z]+);")
# source_url is the citation a student opens, so it must not be an API endpoint.
API_URL = re.compile(r"/wp-json/|/api/|[?&]format=json|\.json($|\?)", re.IGNORECASE)


def check_passage(p):
    """Problems with one passage. Returns (errors, warnings), lists of strings."""
    errors, warnings = [], []
    if not isinstance(p, dict):
        return ["line is not a JSON object"], warnings

    missing = [f for f in FIELDS if f not in p]
    extra = sorted(set(p) - set(FIELDS))
    if missing:
        errors.append("missing field(s): " + ", ".join(missing))
    if extra:
        errors.append("unknown field(s): " + ", ".join(extra))
    for f in FIELDS:
        if f in p and not isinstance(p[f], str):
            errors.append(f"{f} must be a string, got {type(p[f]).__name__}")
    if errors:
        return errors, warnings

    source = p["source"]
    if source not in SOURCES:
        errors.append(f"source {source!r} is not one of: " + ", ".join(sorted(SOURCES)))

    m = ID_FORMAT.match(p["id"])
    if not m:
        errors.append(f"id {p['id']!r} is not <source>:<page key>:<chunk number>")
    elif m.group("source") != source:
        errors.append(f"id starts with {m.group('source')!r} but source is {source!r}")

    if not p["title"].strip():
        errors.append("title is empty")

    text = p["text"]
    words = len(text.split())
    if words == 0:
        errors.append("text is empty")
    elif words > HUGE_WORDS:
        errors.append(f"text is {words} words (over {HUGE_WORDS}); split the page at its headings")
    elif words < MIN_WORDS or words > MAX_WORDS:
        warnings.append(f"text is {words} words (aim for {MIN_WORDS}-{MAX_WORDS})")

    for f in ("title", "text"):
        tag = HTML_TAG.search(p[f])
        if tag:
            errors.append(f"{f} still has HTML: {tag.group(0)[:40]!r}")
        entity = HTML_ENTITY.search(p[f])
        if entity:
            errors.append(f"{f} still has an HTML entity: {entity.group(0)!r}")

    url = p["source_url"]
    if not re.match(r"^https?://[^\s/]+\.[^\s/]+", url) or re.search(r"\s", url):
        errors.append(f"source_url {url!r} is not a web address")
    elif API_URL.search(url):
        errors.append(f"source_url {url!r} looks like an API URL; use the page a student would open")

    ts = p["fetched_at"]
    if not FETCHED_AT_FORMAT.match(ts):
        errors.append(f"fetched_at {ts!r} is not UTC ISO 8601 like 2026-11-10T18:04:00Z")
    else:
        try:
            datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            errors.append(f"fetched_at {ts!r} is not a real date and time")

    return errors, warnings


def check_file(path):
    """Check one .jsonl file. Returns (errors, warnings, passage count).

    Each error and warning is a (line number, message) pair; line 0 means the
    whole file.
    """
    path = Path(path)
    errors, warnings = [], []
    seen = {}
    count = 0
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as e:
        return [(0, f"cannot read file: {e}")], warnings, 0

    for n, line in enumerate(lines, start=1):
        if not line.strip():
            errors.append((n, "blank line"))
            continue
        try:
            p = json.loads(line)
        except json.JSONDecodeError as e:
            errors.append((n, f"not valid JSON: {e.msg}"))
            continue
        count += 1
        errs, warns = check_passage(p)
        errors += [(n, e) for e in errs]
        warnings += [(n, w) for w in warns]
        pid = p.get("id") if isinstance(p, dict) else None
        if isinstance(pid, str):
            if pid in seen:
                errors.append((n, f"duplicate id {pid!r} (first on line {seen[pid]})"))
            else:
                seen[pid] = n

    if count == 0 and not errors:
        errors.append((0, "file has no passages"))
    if path.suffix != ".jsonl" or path.stem not in SOURCES:
        warnings.append((0, f"file name should be <source>.jsonl, one of: "
                            + ", ".join(sorted(SOURCES))))
    return errors, warnings, count


def main(argv):
    if not argv:
        print("usage: python pipeline/check.py <file.jsonl> [more files ...]")
        return 2
    failed = False
    for name in argv:
        errors, warnings, count = check_file(name)
        for n, msg in sorted(errors):
            print(f"{name}:{n}: error: {msg}")
        for n, msg in sorted(warnings):
            print(f"{name}:{n}: warning: {msg}")
        status = "FAIL" if errors else "OK"
        print(f"{status} {name}: {count} passages, {len(errors)} errors, {len(warnings)} warnings")
        failed = failed or bool(errors)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
