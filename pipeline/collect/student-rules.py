"""Collect the Texas A&M Student Rules (https://student-rules.tamu.edu).

The site runs on WordPress, and its public REST API returns every page
(rules, appendices and index pages) with its full HTML in one request.
This script saves that response untouched, then splits each page into
passages of about 100-400 words, breaking at the rule's numbered
subsections (7.1, 7.2, ...) and headings.

Run from the repo root:
    python pipeline/collect/student-rules.py

Writes:
    data/raw/student-rules/pages-<n>.json   exactly what the API returned
    data/processed/student-rules.jsonl      one passage per line
"""

import html
import json
import random
import re
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

SOURCE = "student-rules"
API_URL = "https://student-rules.tamu.edu/wp-json/wp/v2/pages"
FIELDS = "id,slug,link,title,modified,content"
USER_AGENT = "AggieFlowCollector/0.1 (TAMU Aggie Data Science Club student project)"
# robots.txt asks for Crawl-delay: 10. One request usually gets every page,
# but if the site ever needs more than one page of results, wait this long.
DELAY_SECONDS = 10

# Pages that are not rules: a web form for proposing a revision.
SKIP_SLUGS = {"propose-revision"}

MIN_WORDS = 100
MAX_WORDS = 400

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = REPO_ROOT / "data" / "raw" / SOURCE
OUT_FILE = REPO_ROOT / "data" / "processed" / f"{SOURCE}.jsonl"

# A top-level subsection such as "7.3 Absence Documentation" (one dot).
# Deeper ones like "7.3.1.1" stay with their parent subsection.
TOP_SECTION = re.compile(r"^\d+\.\d+(?!\.\d)\b")
SENTENCE_END = re.compile(r"(?<=[.;:?!])\s+(?=[A-Z0-9(\"“])")


def fetch_pages():
    """Fetch every page from the API. Returns (list of raw bodies, fetched_at)."""
    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    bodies = []
    page = 1
    while True:
        if page > 1:
            time.sleep(DELAY_SECONDS)
        resp = session.get(
            API_URL,
            params={"per_page": 100, "page": page, "_fields": FIELDS},
            timeout=60,
        )
        resp.raise_for_status()
        bodies.append(resp.text)
        total_pages = int(resp.headers.get("X-WP-TotalPages", "1"))
        if page >= total_pages:
            break
        page += 1
    return bodies, fetched_at


def save_raw(bodies):
    if RAW_DIR.exists():
        shutil.rmtree(RAW_DIR)
    RAW_DIR.mkdir(parents=True)
    for i, body in enumerate(bodies, start=1):
        (RAW_DIR / f"pages-{i}.json").write_text(body, encoding="utf-8")


def clean_title(raw_title):
    """'Rule 7 &#8211; Attendance' -> 'Rule 7: Attendance'."""
    title = html.unescape(raw_title).strip()
    return re.sub(r"^(Rule \d+)\s*[–—-]\s*", r"\1: ", title)


def clean_text(text):
    text = re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()
    # get_text(" ") puts spaces around inline tags: "( see Rule 24 )".
    text = re.sub(r"\s+([,.;:)\]])", r"\1", text)
    return re.sub(r"([(\[])\s+", r"\1", text)


def words(text):
    return len(text.split())


def page_blocks(content_html):
    """Turn a page's HTML into an ordered list of (kind, text) blocks.

    kind is "heading" for h2/h3 and "text" for paragraphs, list items,
    table rows and quotes.
    """
    soup = BeautifulSoup(content_html, "html.parser")
    # The "Propose a Student Rule Revision" box at the bottom of each rule.
    for box in soup.select("section.section-wrap--divider"):
        box.decompose()
    for tag in soup(["script", "style", "form", "button", "input", "textarea", "label"]):
        tag.decompose()
    # Some pages end with a plain "Propose a Student Rule Revision" link instead.
    for link in soup.select('a[href*="propose-revision"]'):
        block = link.find_parent(["p", "h2", "h3", "h4"])
        if block and clean_text(block.get_text(" ")) == clean_text(link.get_text(" ")):
            block.decompose()

    blocks = []
    for el in soup.find_all(["h2", "h3", "h4", "p", "li", "tr", "blockquote"]):
        # Skip elements nested in another block we already take whole.
        if el.find_parent(["p", "li", "tr", "blockquote"]):
            continue
        if el.name == "tr":
            cells = [clean_text(c.get_text(" ")) for c in el.find_all(["th", "td"])]
            text = " | ".join(c for c in cells if c)
        else:
            text = clean_text(el.get_text(" "))
        if not text:
            continue
        kind = "heading" if el.name in ("h2", "h3", "h4") else "text"
        # A short paragraph that is all bold, like <p><strong>Procedures</strong></p>,
        # is a sub-heading too.
        bold = el.find("strong") if el.name == "p" else None
        if bold and clean_text(bold.get_text(" ")) == text and words(text) <= 8:
            kind = "heading"
        blocks.append((kind, text))
    return blocks


def chunk_page(blocks):
    """Group blocks into passages. Returns a list of (heading, text)."""
    chunks = []
    cur, cur_words, cur_heading = [], 0, None
    heading = None
    first_heading_seen = False

    def flush():
        nonlocal cur, cur_words
        if cur:
            chunks.append((cur_heading, "\n".join(cur)))
        cur, cur_words = [], 0

    for kind, text in blocks:
        n = words(text)
        if kind == "heading":
            # The first h2 is the page's own title ("7. Attendance").
            if first_heading_seen:
                heading = text
            first_heading_seen = True
        elif TOP_SECTION.match(text):
            # "7.3 Absence Documentation and Verification" is a section label;
            # "8.4 In those instances where..." is a section with no label.
            heading = text if n <= 12 else None
        starts_section = kind == "heading" or bool(TOP_SECTION.match(text))

        if starts_section and cur_words >= MIN_WORDS:
            flush()
        # A very long block is split by sentence below, so it can top up the
        # current passage instead of leaving a short one behind.
        if cur and n <= MAX_WORDS and cur_words + n > MAX_WORDS:
            flush()
        if not cur:
            cur_heading = heading

        if n > MAX_WORDS:
            # Split the paragraph at sentence ends, never mid-sentence.
            para = []
            for sentence in SENTENCE_END.split(text):
                if (cur or para) and cur_words + words(sentence) > MAX_WORDS:
                    if para:
                        cur.append(" ".join(para))
                        para = []
                    flush()
                    cur_heading = heading
                para.append(sentence)
                cur_words += words(sentence)
            if para:
                cur.append(" ".join(para))
        else:
            cur.append(text)
            cur_words += n
    flush()

    # A short last passage reads better merged into the one before it.
    if len(chunks) > 1 and words(chunks[-1][1]) < MIN_WORDS:
        prev_heading, prev_text = chunks[-2]
        merged = prev_text + "\n" + chunks[-1][1]
        if words(merged) <= MAX_WORDS:
            chunks[-2:] = [(prev_heading, merged)]
    return chunks


def build_passages(bodies, fetched_at):
    """Turn raw API responses into passage dicts."""
    passages = []
    for body in bodies:
        for page in json.loads(body):
            slug = page["slug"]
            if slug in SKIP_SLUGS:
                continue
            title = clean_title(page["title"]["rendered"])
            chunks = chunk_page(page_blocks(page["content"]["rendered"]))
            for i, (heading, text) in enumerate(chunks, start=1):
                passages.append({
                    "id": f"{SOURCE}:{slug}:{i}",
                    "source": SOURCE,
                    "title": f"{title} – {heading}" if heading else title,
                    "text": text,
                    "source_url": page["link"],
                    "fetched_at": fetched_at,
                })
    return passages


def write_passages(passages):
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with OUT_FILE.open("w", encoding="utf-8") as f:
        for p in passages:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")


def main():
    bodies, fetched_at = fetch_pages()
    save_raw(bodies)
    passages = build_passages(bodies, fetched_at)
    write_passages(passages)

    pages = {p["source_url"] for p in passages}
    counts = [words(p["text"]) for p in passages]
    print(f"Saved {len(bodies)} raw response(s) to {RAW_DIR.relative_to(REPO_ROOT)}")
    print(f"Wrote {len(passages)} passages from {len(pages)} pages to {OUT_FILE.relative_to(REPO_ROOT)}")
    print(f"Words per passage: min {min(counts)}, median {sorted(counts)[len(counts) // 2]}, max {max(counts)}")
    print("Three random passages:")
    for p in random.sample(passages, min(3, len(passages))):
        print(f"  {p['id']}  {p['title']}  ({words(p['text'])} words)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
