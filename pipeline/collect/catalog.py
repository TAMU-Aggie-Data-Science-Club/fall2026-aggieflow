"""Collect the Texas A&M Course Catalog (https://catalog.tamu.edu).

The catalog runs on CourseLeaf, and every page is plain HTML. The sitemap
lists all 1,575 pages. This script fetches the undergraduate and graduate
pages from it and turns them into passages:

- Course description pages (one per subject, like .../course-descriptions/csce/)
  become one passage per course: code, title, credits, description and
  prerequisites.
- Every other page (degree plans, minors, certificates, the core curriculum,
  policies) is split at its headings into passages of about 100-400 words.
  A degree plan's semester grid becomes one line per semester, course lists
  become one line per course, and footnotes become "Note N: ...".

Run from the repo root:
    python pipeline/collect/catalog.py              # everything, most of an hour
    python pipeline/collect/catalog.py --limit 5    # 5 course pages + 5 other pages
    python pipeline/collect/catalog.py --from-raw   # re-parse saved HTML, no requests

Writes:
    data/raw/catalog/sitemap.xml       the sitemap as fetched
    data/raw/catalog/<page>.html       exactly what each page returned
    data/processed/catalog.jsonl       one passage per line
"""

import argparse
import html
import json
import random
import re
import shutil
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup, NavigableString

SOURCE = "catalog"
BASE_URL = "https://catalog.tamu.edu"
SITEMAP_URL = f"{BASE_URL}/sitemap.xml"
USER_AGENT = "AggieFlowCollector/0.1 (TAMU Aggie Data Science Club student project)"
DELAY_SECONDS = 1  # robots.txt sets no crawl delay; the team rule is at least 1 second
RETRIES = 3

# Pages that are only lists of names, or an index of links to other pages.
SKIP_PATHS = re.compile(
    r"/(faculty|board-regents-administrative-officers)/$"
    r"|/course-descriptions/$"
)
SKIP_TABS = {"faculty", "courses"}
# Passages shorter than this are a lone heading or a name, not an answer.
TINY_WORDS = 15
COURSE_PAGE = re.compile(r"^/(undergraduate|graduate)/course-descriptions/[^/]+/$")
# "CSCE 121", "AFST 327/MUSC 327", "MATH 151H"
COURSE_CODE = re.compile(r"^([A-Z]{3,4}\s?\d{3}[A-Z]?(?:/[A-Z]{3,4}\s?\d{3}[A-Z]?)*)\s+(.*)$")
EDITION = re.compile(r"(\d{4}-\d{4}) Edition")
SENTENCE_END = re.compile(r"(?<=[.;:?!])\s+(?=[A-Z0-9(\"“])")

MIN_WORDS = 100
MAX_WORDS = 400

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = REPO_ROOT / "data" / "raw" / SOURCE
OUT_FILE = REPO_ROOT / "data" / "processed" / f"{SOURCE}.jsonl"


# --- Fetching -------------------------------------------------------------

def now_utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def url_path(url):
    return url[len(BASE_URL):] if url.startswith(BASE_URL) else url


def page_key(url):
    """'https://catalog.tamu.edu/undergraduate/engineering/computer-science/bs/'
    -> 'undergraduate/engineering/computer-science/bs'"""
    return url_path(url).strip("/")


def raw_file(url):
    return RAW_DIR / (page_key(url).replace("/", "__") + ".html")


def get(session, url):
    """GET with a few retries. Returns the response, or None for a 404."""
    for attempt in range(1, RETRIES + 1):
        try:
            resp = session.get(url, timeout=60)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            if attempt == RETRIES:
                raise
            print(f"  retry {attempt} for {url}: {e}")
            time.sleep(5 * attempt)


def catalog_urls(sitemap_xml):
    """Undergraduate and graduate page URLs from the sitemap, minus skipped ones."""
    root = ET.fromstring(sitemap_xml)
    urls = []
    for loc in root.iter("{http://www.sitemaps.org/schemas/sitemap/0.9}loc"):
        url = (loc.text or "").strip()
        path = url_path(url)
        if not re.match(r"^/(undergraduate|graduate)/", path):
            continue
        if not path.endswith("/") or SKIP_PATHS.search(path):
            continue
        urls.append(url)
    return sorted(set(urls))


def pick(urls, limit):
    """With --limit, keep `limit` course pages and `limit` other pages."""
    if not limit:
        return urls
    courses = [u for u in urls if COURSE_PAGE.match(url_path(u))]
    others = [u for u in urls if not COURSE_PAGE.match(url_path(u))]
    return courses[:limit] + others[:limit]


def fetch_all(limit):
    """Fetch the sitemap and every page. Returns {url: (html, fetched_at)}."""
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    if RAW_DIR.exists():
        shutil.rmtree(RAW_DIR)
    RAW_DIR.mkdir(parents=True)

    sitemap = get(session, SITEMAP_URL)
    (RAW_DIR / "sitemap.xml").write_bytes(sitemap.content)
    urls = pick(catalog_urls(sitemap.content), limit)
    print(f"Fetching {len(urls)} pages (about {len(urls) * (DELAY_SECONDS + 0.5) / 60:.0f} minutes)")

    pages = {}
    for i, url in enumerate(urls, start=1):
        time.sleep(DELAY_SECONDS)
        resp = get(session, url)
        if resp is None:
            print(f"  404, skipped: {url}")
            continue
        raw_file(url).write_bytes(resp.content)
        pages[url] = (resp.text, now_utc())
        if i % 50 == 0 or i == len(urls):
            print(f"  {i}/{len(urls)}")
    return pages


def load_raw(limit):
    """Read pages saved by an earlier run instead of fetching them again."""
    sitemap = (RAW_DIR / "sitemap.xml").read_bytes()
    pages = {}
    for url in pick(catalog_urls(sitemap), limit):
        path = raw_file(url)
        if path.exists():
            mtime = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
            pages[url] = (path.read_text(encoding="utf-8"), mtime.strftime("%Y-%m-%dT%H:%M:%SZ"))
    return pages


# --- Cleaning -------------------------------------------------------------

def clean_text(text):
    # A few pages double-escape ampersands ("A&amp;M" in the page text).
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()
    text = re.sub(r"\s+([,.;:)\]])", r"\1", text)
    return re.sub(r"([(\[])\s+", r"\1", text)


def words(text):
    return len(text.split())


def page_title(soup):
    """'Computer Science - BS < Texas A&M Catalogs < ...' -> 'Computer Science - BS'."""
    title = soup.title.get_text() if soup.title else ""
    return clean_text(title.split("<")[0]) or "Texas A&M Catalog"


def edition(html_text):
    m = EDITION.search(html_text)
    return m.group(1) if m else None


def mark_footnotes(soup):
    """Footnote numbers like <sup>1,4</sup> become '(note 1,4)' so they survive as text."""
    for sup in soup.find_all("sup"):
        t = clean_text(sup.get_text())
        if re.fullmatch(r"[\d, ]+", t):
            sup.replace_with(f" (note {t.replace(' ', '')})")


def cell(td):
    return clean_text(td.get_text(" ")) if td else ""


def hours_suffix(hours):
    if not hours or not re.search(r"\d", hours):
        return ""
    return f" ({hours} hour)" if hours == "1" else f" ({hours} hours)"


def plangrid_lines(table):
    """A semester-by-semester degree plan, one line per semester:
    'First Year, Fall: CHEM 107 General Chemistry ... (3 hours); ... Semester total: 16 hours.'"""
    lines, year, term, rows = [], "", "", []

    def flush():
        if rows:
            label = ", ".join(x for x in (year, term) if x)
            lines.append(f"{label}: " + "; ".join(rows) if label else "; ".join(rows))
            rows.clear()

    for tr in table.find_all("tr"):
        classes = tr.get("class") or []
        text = clean_text(tr.get_text(" "))
        if "plangridyear" in classes:
            flush()
            year, term = text, ""
        elif "plangridterm" in classes:
            flush()
            ths = tr.find_all("th")
            term = cell(ths[0]) if ths else text
        elif "plangridsum" in classes:
            tds = tr.find_all("td")
            hours = cell(tds[-1]) if tds else ""
            if rows and hours:
                rows[-1] += f". Semester total: {hours} hours"
            flush()
        elif "plangridtotal" in classes:
            flush()
            tds = tr.find_all("td")
            hours = cell(tds[-1]) if tds else ""
            lines.append(f"Total semester credit hours: {hours}")
        else:
            code = cell(tr.find("td", class_="codecol"))
            title = cell(tr.find("td", class_="titlecol"))
            hours = cell(tr.find("td", class_="hourscol"))
            row = " ".join(x for x in (code, title) if x)
            if row:
                rows.append(row + hours_suffix(hours))
    flush()
    return lines


def courselist_lines(table):
    """A list of courses, one line per row: 'COMM 203 Public Speaking (3 hours)'."""
    lines = []
    for tr in table.find_all("tr"):
        classes = tr.get("class") or []
        if "hidden" in classes or tr.find_parent("thead"):
            continue
        tds = tr.find_all("td")
        if not tds:
            continue
        hours = cell(tr.find("td", class_="hourscol"))
        parts = [cell(td) for td in tds if "hourscol" not in (td.get("class") or [])]
        row = " ".join(p for p in parts if p)
        if "listsum" in classes:
            lines.append(f"Total: {hours} hours" if hours else row)
        elif row:
            lines.append(row + hours_suffix(hours))
    return lines


def table_lines(table):
    lines = []
    for tr in table.find_all("tr"):
        cells = [cell(c) for c in tr.find_all(["th", "td"])]
        row = " | ".join(c for c in cells if c)
        if row:
            lines.append(row)
    return lines


def footnote_lines(dl):
    lines = []
    for dt in dl.find_all("dt"):
        dd = dt.find_next_sibling("dd")
        number = re.sub(r"^\(note ([\d,]+)\)$", r"\1", cell(dt))
        lines.append(f"Note {number}: {cell(dd)}")
    return lines


def blocks(node):
    """Walk a content area in order. Yields ("heading", text) or ("text", line)."""
    for child in node.children:
        if isinstance(child, NavigableString):
            text = clean_text(str(child))
            if text:
                yield "text", text
            continue
        name = child.name
        classes = child.get("class") or []
        if name in ("h1", "h2", "h3", "h4", "h5"):
            text = clean_text(child.get_text(" "))
            if text:
                yield "heading", text
        elif name == "table":
            if "sc_plangrid" in classes:
                lines = plangrid_lines(child)
            elif "sc_courselist" in classes:
                lines = courselist_lines(child)
            else:
                lines = table_lines(child)
            for line in lines:
                yield "text", line
        elif name == "dl" and "sc_footnotes" in classes:
            for line in footnote_lines(child):
                yield "text", line
        elif name in ("ul", "ol"):
            for li in child.find_all("li", recursive=False):
                text = clean_text(li.get_text(" "))
                if text:
                    yield "text", text
        elif name in ("div", "section", "article", "blockquote"):
            yield from blocks(child)
        else:
            text = clean_text(child.get_text(" "))
            if text:
                yield "text", text


def content_blocks(soup):
    """Blocks from the page's main content, tab by tab ("Overview", "Program Requirements")."""
    # Tab links live in a <nav>, so read them before the navigation is removed.
    tab_names = {}
    for a in soup.select("a[role='tab'][href^='#']"):
        tab_names[a["href"][1:]] = clean_text(a.get_text(" "))

    for tag in soup(["script", "style", "nav", "form", "button", "input", "noscript"]):
        tag.decompose()
    for tag in soup.select(".hidden, .print-only, .onthispage"):
        tag.decompose()
    # Department pages repeat their courses (already collected from the
    # course description pages) and list their faculty. Skip both.
    for tag in soup.select("div.courseblock"):
        tag.decompose()
    for tab_id, name in tab_names.items():
        if name.lower() in SKIP_TABS:
            for tag in soup.select(f"[id='{tab_id}']"):
                tag.decompose()
    mark_footnotes(soup)

    containers = soup.select("div.page_content") or soup.select("#contentarea, main")
    for container in containers:
        name = tab_names.get(container.get("id", ""))
        if name:
            yield "heading", name
        yield from blocks(container)


# --- Passages -------------------------------------------------------------

def split_long(line):
    """Split a line over MAX_WORDS at sentence ends (or, failing that, every MAX_WORDS words)."""
    if words(line) <= MAX_WORDS:
        return [line]
    pieces, cur = [], []
    for sentence in SENTENCE_END.split(line):
        if cur and words(" ".join(cur + [sentence])) > MAX_WORDS:
            pieces.append(" ".join(cur))
            cur = []
        cur.append(sentence)
    if cur:
        pieces.append(" ".join(cur))
    out = []
    for piece in pieces:
        w = piece.split()
        out.extend(" ".join(w[i:i + MAX_WORDS]) for i in range(0, len(w), MAX_WORDS))
    return out


def chunk(block_list):
    """Group blocks into (heading, text) chunks of about MIN_WORDS-MAX_WORDS words.
    A new heading starts a new chunk once the current one is long enough."""
    chunks, cur, cur_heading, heading = [], [], None, None

    def flush():
        nonlocal cur
        if cur:
            chunks.append((cur_heading, "\n".join(cur)))
            cur = []

    for kind, text in block_list:
        if kind == "heading":
            if words("\n".join(cur)) >= MIN_WORDS:
                flush()
            heading = text
            if not cur:
                cur_heading = heading
            cur.append(text)
            continue
        for line in split_long(text):
            if cur and words("\n".join(cur)) + words(line) > MAX_WORDS:
                flush()
            if not cur:
                cur_heading = heading
            cur.append(line)
    flush()

    # A short last chunk reads better merged into the one before it.
    if len(chunks) > 1 and words(chunks[-1][1]) < MIN_WORDS:
        merged = chunks[-2][1] + "\n" + chunks[-1][1]
        if words(merged) <= MAX_WORDS:
            chunks[-2:] = [(chunks[-2][0], merged)]
    # Drop chunks that are only a heading or a few words.
    return [(h, t) for h, t in chunks if words(t) >= TINY_WORDS]


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def course_passages(url, html_text, fetched_at):
    """One passage per course on a subject's course description page."""
    soup = BeautifulSoup(html_text, "html.parser")
    level = "undergraduate" if url_path(url).startswith("/undergraduate/") else "graduate"
    year = edition(html_text)
    passages, seen = [], set()
    for block in soup.select("div.courseblock"):
        title_el = block.select_one(".courseblocktitle")
        if not title_el:
            continue
        heading = clean_text(title_el.get_text(" "))
        m = COURSE_CODE.match(heading)
        code = m.group(1) if m else heading.split("  ")[0]
        title_el.decompose()
        body = clean_text(block.get_text(" "))
        about = f"{level.capitalize()} course" + (f" in the {year} catalog." if year else ".")
        key = f"course/{level}/{slug(code)}"
        if key in seen:
            continue
        seen.add(key)
        passages.append({
            "id": f"{SOURCE}:{key}:1",
            "source": SOURCE,
            "title": heading,
            "text": f"{heading}. {about} {body}",
            "source_url": url,
            "fetched_at": fetched_at,
        })
    return passages


def page_passages(url, html_text, fetched_at):
    """Passages for a degree plan, policy or other content page."""
    soup = BeautifulSoup(html_text, "html.parser")
    title = page_title(soup)
    year = edition(html_text)
    if year:
        title = f"{title} ({year})"
    passages = []
    for i, (heading, text) in enumerate(chunk(content_blocks(soup)), start=1):
        passages.append({
            "id": f"{SOURCE}:{page_key(url)}:{i}",
            "source": SOURCE,
            "title": f"{title} – {heading}" if heading else title,
            "text": text,
            "source_url": url,
            "fetched_at": fetched_at,
        })
    return passages


def build_passages(pages):
    passages = []
    for url, (html_text, fetched_at) in pages.items():
        if COURSE_PAGE.match(url_path(url)):
            passages.extend(course_passages(url, html_text, fetched_at))
        else:
            passages.extend(page_passages(url, html_text, fetched_at))
    return passages


def write_passages(passages):
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with OUT_FILE.open("w", encoding="utf-8") as f:
        for p in passages:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--limit", type=int, default=0,
                        help="only N course pages and N other pages, for testing")
    parser.add_argument("--from-raw", action="store_true",
                        help="re-parse pages saved in data/raw/catalog/ without fetching")
    args = parser.parse_args()

    pages = load_raw(args.limit) if args.from_raw else fetch_all(args.limit)
    passages = build_passages(pages)
    write_passages(passages)

    courses = sum(1 for p in passages if p["id"].startswith(f"{SOURCE}:course/"))
    counts = [words(p["text"]) for p in passages]
    print(f"Read {len(pages)} pages")
    print(f"Wrote {len(passages)} passages ({courses} courses, {len(passages) - courses} "
          f"from other pages) to {OUT_FILE.relative_to(REPO_ROOT)}")
    if counts:
        print(f"Words per passage: min {min(counts)}, median {sorted(counts)[len(counts) // 2]}, "
              f"max {max(counts)}")
        print("Three random passages:")
        for p in random.sample(passages, min(3, len(passages))):
            print(f"  {p['id']}  {p['title']}  ({words(p['text'])} words)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
