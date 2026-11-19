"""Collect Texas A&M Transportation Services pages (https://transport.tamu.edu).

The site runs on ASP.NET and has no sitemap (sitemap.xml and robots.txt both
return its "Webpage Not Found" page). So this script starts at the hub pages
(parking, transit, events, alternative transportation, fleet, about) and
follows links to other pages on the same site, one request per second. It
keeps the static pages (rules, permits, routes, gameday, bikes) and skips the
live bus times and garage counts, which go out of date within minutes.

Run from the repo root:
    python pipeline/collect/transportation.py              # crawl and rebuild everything
    python pipeline/collect/transportation.py --from-raw   # re-parse saved pages, no requests

Writes:
    data/raw/transportation/pages/<page>.html   exactly what each page returned
    data/raw/transportation/pages.json          URL and fetch time of each saved page
    data/processed/transportation.jsonl         one passage per line
"""

import argparse
import copy
import json
import re
import shutil
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

SOURCE = "transportation"
USER_AGENT = "AggieFlowCollector/0.1 (TAMU Aggie Data Science Club student project)"
HOST = "transport.tamu.edu"
BASE_URL = f"https://{HOST}"
SEEDS = ["/", "/parking.aspx", "/transit.aspx", "/events.aspx", "/alternative.aspx",
         "/fleet.aspx", "/about.aspx", "/football"]

REQUEST_DELAY_SECONDS = 1.0
TIMEOUT_SECONDS = 30
MAX_PAGES = 400  # safety limit; the site has about 200 static pages

# Paths that aren't static information pages: news archives, job and fleet
# portals that need a login, error pages and the AggieSpirit redirect.
SKIP_PATHS = re.compile(
    r"^/(about/news/|mis/|myfleet|errorpages/|busroutes|dprweb|bikemap)", re.IGNORECASE
)
FILE_EXTENSIONS = re.compile(r"\.(pdf|docx?|xlsx?|pptx?|jpe?g|png|gif|svg|zip|mp4|css|js)$",
                             re.IGNORECASE)
NOT_FOUND_TITLE = "Webpage Not Found"

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = REPO_ROOT / "data" / "raw" / SOURCE
PAGES_DIR = RAW_DIR / "pages"
INDEX_FILE = RAW_DIR / "pages.json"
OUT_FILE = REPO_ROOT / "data" / "processed" / f"{SOURCE}.jsonl"

MIN_WORDS = 100
MAX_WORDS = 400
TARGET_WORDS = 250
MIN_PAGE_WORDS = 25  # pages with less text are only a form or a heading


def now_utc():
    """Current time in the passage format, e.g. 2026-11-19T18:04:00Z."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def word_count(text):
    return len(text.split())


def clean_url(url):
    """Absolute https URL without its #fragment or ?query, or None if it isn't a
    page on this site worth fetching."""
    url, _ = urldefrag(url.strip())
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or parts.netloc.lower() != HOST:
        return None
    path = parts.path or "/"
    if SKIP_PATHS.match(path) or FILE_EXTENSIONS.search(path):
        return None
    # Pages are .aspx files or extensionless short links like /football.
    last = path.rstrip("/").rsplit("/", 1)[-1]
    if "." in last and not last.lower().endswith(".aspx"):
        return None
    return f"{BASE_URL}{path}"


def page_key(url):
    """'https://transport.tamu.edu/Parking/regulations.aspx' -> 'parking/regulations'."""
    path = urlsplit(url).path.strip("/").lower()
    path = re.sub(r"\.aspx$", "", path)
    return re.sub(r"(^|/)default$", "", path) or "home"


def links(html, page_url):
    soup = BeautifulSoup(html, "html.parser")
    found = []
    for a in soup.find_all("a", href=True):
        url = clean_url(urljoin(page_url, a["href"]))
        if url:
            found.append(url)
    return found


def is_not_found(response):
    if "/errorpages/" in response.url.lower():
        return True
    title = BeautifulSoup(response.text, "html.parser").title
    return bool(title and NOT_FOUND_TITLE.lower() in title.get_text().lower())


def crawl():
    """Fetch every page reachable from the seeds. Returns [(url, html, fetched_at)]."""
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    if PAGES_DIR.exists():
        shutil.rmtree(PAGES_DIR)
    PAGES_DIR.mkdir(parents=True)

    queue = deque(clean_url(BASE_URL + seed) for seed in SEEDS)
    queued = {page_key(url) for url in queue}
    saved = set()
    pages, index = [], []

    while queue and len(pages) < MAX_PAGES:
        url = queue.popleft()
        time.sleep(REQUEST_DELAY_SECONDS)
        try:
            response = session.get(url, timeout=TIMEOUT_SECONDS)
        except requests.RequestException as err:
            print(f"  failed, skipped: {url} ({type(err).__name__})")
            continue
        final = clean_url(response.url)  # redirects, e.g. /football -> /Parking/events/football.aspx
        if response.status_code != 200 or final is None or is_not_found(response):
            print(f"  not a page ({response.status_code}), skipped: {url}")
            continue
        if page_key(final) in saved:
            continue
        saved.add(page_key(final))
        queued.add(page_key(final))

        fetched_at = now_utc()
        name = page_key(final).replace("/", "__") + ".html"
        (PAGES_DIR / name).write_bytes(response.content)
        index.append({"url": final, "file": name, "fetched_at": fetched_at})
        pages.append((final, response.text, fetched_at))

        for link in links(response.text, final):
            if page_key(link) not in queued:
                queued.add(page_key(link))
                queue.append(link)

    INDEX_FILE.write_text(json.dumps(index, indent=1), encoding="utf-8")
    if queue:
        print(f"Stopped at the {MAX_PAGES}-page limit with {len(queue)} links left")
    print(f"Saved {len(pages)} pages")
    return pages


def saved_pages():
    """The pages from the last crawl, read from data/raw/ instead of the site."""
    index = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    return [(e["url"], (PAGES_DIR / e["file"]).read_text(encoding="utf-8"), e["fetched_at"])
            for e in index]


def main_content(soup):
    """The page's own text area, without the breadcrumb, side menu or link boxes."""
    main = soup.select_one("div.maincontent") or soup.find(id="main-content") or soup.body
    if main is None:
        return None
    for element in main.select(
        "script, style, nav, button, .breadcrumb, .quicklinks, .bottom-list, .aspNetHidden"
    ):
        element.decompose()
    return main


def page_title(soup, fallback):
    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        return " ".join(h1.get_text(" ", strip=True).split())
    if soup.title and soup.title.get_text(strip=True):
        return " ".join(soup.title.get_text().split())
    return fallback


BLOCK_TAGS = ["h1", "h2", "h3", "h4", "h5", "p", "li", "td", "th", "dt", "dd"]
NESTED_BLOCKS = ["p", "ul", "ol", "dl", "table"]


def page_blocks(main):
    """Headings and text blocks in reading order, without repeats from nesting."""
    blocks = []
    for element in main.find_all(BLOCK_TAGS):
        if element.name in ("p", "li", "td", "th", "dd") and element.find(NESTED_BLOCKS):
            # A list item or cell that wraps other blocks: take only its own text,
            # in order. The nested blocks come up as blocks of their own.
            own = copy.copy(element)
            for nested in own.find_all(NESTED_BLOCKS):
                nested.decompose()
            text = " ".join(own.get_text(" ", strip=True).split())
        else:
            text = " ".join(element.get_text(" ", strip=True).split())
        if not text:
            continue
        kind = "heading" if element.name in ("h1", "h2", "h3", "h4", "h5") else "text"
        if blocks and blocks[-1] == (kind, text):
            continue
        blocks.append((kind, text))
    if not blocks:  # a page with plain text and no block tags
        text = " ".join(main.get_text(" ", strip=True).split())
        if text:
            blocks.append(("text", text))
    return blocks


def split_long(text):
    """Split a block over MAX_WORDS at sentence ends, about TARGET_WORDS each."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    pieces, current = [], []
    for sentence in sentences:
        if current and word_count(" ".join(current + [sentence])) > TARGET_WORDS:
            pieces.append(" ".join(current))
            current = []
        current.append(sentence)
    if current:
        pieces.append(" ".join(current))
    # A single sentence longer than MAX_WORDS (a long list run together) is cut by words.
    sized = []
    for piece in pieces:
        words = piece.split()
        if len(words) > MAX_WORDS:
            sized += [" ".join(words[i:i + TARGET_WORDS]) for i in range(0, len(words), TARGET_WORDS)]
        else:
            sized.append(piece)
    return sized


def chunk_page(blocks):
    """Combine blocks into passages of about 100-400 words, starting new passages at headings."""
    sized = []
    for kind, text in blocks:
        if kind == "text" and word_count(text) > MAX_WORDS:
            sized += [("text", piece) for piece in split_long(text)]
        else:
            sized.append((kind, text))

    chunks, current = [], []
    for kind, text in sized:
        size = word_count(" ".join(current))
        too_big = size and word_count(" ".join(current + [text])) > MAX_WORDS
        heading_break = kind == "heading" and size >= MIN_WORDS
        target_break = kind == "text" and size >= MIN_WORDS and \
            word_count(" ".join(current + [text])) > TARGET_WORDS
        if too_big or heading_break or target_break:
            chunks.append(" ".join(current))
            current = []
        current.append(text)
    if current:
        chunks.append(" ".join(current))

    # Fold a short last chunk into the one before it when that stays under the limit.
    if len(chunks) >= 2 and word_count(chunks[-1]) < MIN_WORDS:
        combined = chunks[-2] + " " + chunks[-1]
        if word_count(combined) <= MAX_WORDS:
            chunks[-2:] = [combined]
    return chunks


def build_passages(pages):
    passages, seen = [], set()
    for url, html, fetched_at in pages:
        key = page_key(url)
        if key in seen:  # e.g. / and /default.aspx in a crawl saved before the crawl deduped them
            continue
        seen.add(key)
        soup = BeautifulSoup(html, "html.parser")
        title = page_title(soup, key)
        main = main_content(soup)
        if main is None:
            continue
        chunks = chunk_page(page_blocks(main))
        if word_count(" ".join(chunks)) < MIN_PAGE_WORDS:
            continue
        for i, chunk in enumerate(chunks, start=1):
            passages.append({
                "id": f"{SOURCE}:{key}:{i}",
                "source": SOURCE,
                "title": title,
                "text": chunk,
                "source_url": url,
                "fetched_at": fetched_at,
            })
    return passages


def write_passages(passages):
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with OUT_FILE.open("w", encoding="utf-8") as f:
        for p in passages:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    print(f"Saved {len(passages)} passages to {OUT_FILE.relative_to(REPO_ROOT)}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--from-raw", action="store_true",
                        help="re-parse the pages saved by the last crawl, with no requests")
    args = parser.parse_args()
    pages = saved_pages() if args.from_raw else crawl()
    write_passages(build_passages(pages))


if __name__ == "__main__":
    main()
