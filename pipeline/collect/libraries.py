"""Collect Texas A&M University Libraries pages (https://library.tamu.edu).

The site's sitemap.xml lists every page (286 on Nov 11, 2026) and the page text
is in the HTML, so this script reads the sitemap and fetches the student-facing
sections one request per second: borrowing (loan periods, renewals, returns,
fines, Get It For Me), services (the Tech Bar's rules, printing, AskUs), spaces
and room reservations, and the branch libraries. It skips the hours pages, whose
times load with JavaScript (the agent gets hours live from LibCal instead), and
the special collections, archives and annual reports. Passages are split the same
way as Transportation's, with that collector's own code.

Run from the repo root:
    uv run python pipeline/collect/libraries.py              # fetch and rebuild everything
    uv run python pipeline/collect/libraries.py --from-raw   # re-parse saved pages, no requests
    uv run python pipeline/load.py --source libraries        # then load into Atlas

Writes:
    data/raw/libraries/sitemap.xml            the sitemap as fetched
    data/raw/libraries/pages/<page>.html      exactly what each page returned
    data/raw/libraries/pages.json             URL and fetch time of each saved page
    data/processed/libraries.jsonl            one passage per line
"""

import argparse
import importlib.util
import json
import re
import shutil
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlsplit

import requests
from bs4 import BeautifulSoup

SOURCE = "libraries"
HOST = "library.tamu.edu"
BASE_URL = f"https://{HOST}"
SITEMAP_URL = f"{BASE_URL}/sitemap.xml"
USER_AGENT = "AggieFlowCollector/0.1 (TAMU Aggie Data Science Club student project)"
REQUEST_DELAY_SECONDS = 1.0
TIMEOUT_SECONDS = 30
MAX_PAGES = 200  # safety limit; about 90 sitemap pages are kept

# Sections students ask about, by path. Not kept: about/ (annual reports, policies),
# cushing/ and university-archives/ (special collections), collections/,
# digital-collections/, instruction/, research-scholarship/, open-ed/ and the
# search-pages/ (catalog search boxes), plus the forms in service-forms/.
KEEP_PATHS = re.compile(
    r"^/(borrowing|services|spaces|wcl|galveston)/"
    r"|^/medical-sciences/(about|borrowing|services|spaces)/"
    r"|^/(askus|undergrad-info|grad-info|unaffiliated|contact-us)\.html$"
)
SKIP_PATHS = re.compile(r"/hours\.html$")  # times load with JavaScript; LibCal has them

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = REPO_ROOT / "data" / "raw" / SOURCE
PAGES_DIR = RAW_DIR / "pages"
INDEX_FILE = RAW_DIR / "pages.json"
OUT_FILE = REPO_ROOT / "data" / "processed" / f"{SOURCE}.jsonl"
MIN_PAGE_WORDS = 25  # pages with less text are only a form or a heading


def _load_transportation():
    """The Transportation collector, for its block and chunking code (one way to split pages)."""
    path = Path(__file__).resolve().parent / "transportation.py"
    spec = importlib.util.spec_from_file_location("transportation_collect", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


transportation = _load_transportation()
now_utc = transportation.now_utc
word_count = transportation.word_count


def keep(url):
    """True for a library page in a section students ask about."""
    parts = urlsplit(url.strip())
    if parts.netloc.lower() != HOST:
        return False
    path = parts.path or "/"
    return bool(KEEP_PATHS.match(path)) and not SKIP_PATHS.search(path)


def page_key(url):
    """'https://library.tamu.edu/services/techbar.html' -> 'services/techbar';
    '.../borrowing/index.html' -> 'borrowing'."""
    path = urlsplit(url).path.strip("/").lower()
    path = re.sub(r"\.html?$", "", path)
    return re.sub(r"(^|/)index$", "", path) or "home"


def sitemap_urls(xml_bytes):
    """Kept page URLs from the sitemap, in its order, without repeats."""
    root = ET.fromstring(xml_bytes)
    urls = [(loc.text or "").strip() for loc in root.iter() if loc.tag.endswith("loc")]
    return list(dict.fromkeys(u for u in urls if keep(u)))


def fetch():
    """Fetch the sitemap and every kept page. Returns [(url, html, fetched_at)]."""
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    response = session.get(SITEMAP_URL, timeout=TIMEOUT_SECONDS)
    if response.status_code != 200:
        sys.exit(f"{SITEMAP_URL} answered {response.status_code}; nothing was changed. "
                 "If it's 403, the site is refusing this connection: try again later or from another network.")
    if PAGES_DIR.exists():
        shutil.rmtree(PAGES_DIR)
    PAGES_DIR.mkdir(parents=True)
    (RAW_DIR / "sitemap.xml").write_bytes(response.content)

    urls = sitemap_urls(response.content)[:MAX_PAGES]
    print(f"{len(urls)} pages to fetch")
    pages, index, failed = [], [], []
    for url in urls:
        time.sleep(REQUEST_DELAY_SECONDS)
        try:
            response = session.get(url, timeout=TIMEOUT_SECONDS)
        except requests.RequestException as err:
            print(f"  failed: {url} ({type(err).__name__})")
            failed.append(url)
            continue
        if response.status_code in (403, 429) or response.status_code >= 500:
            print(f"  failed ({response.status_code}): {url}")
            failed.append(url)
            continue
        if response.status_code != 200 or not keep(response.url):
            print(f"  not a page ({response.status_code}), skipped: {url}")
            continue
        fetched_at = now_utc()
        name = page_key(response.url).replace("/", "__") + ".html"
        (PAGES_DIR / name).write_bytes(response.content)
        index.append({"url": response.url, "file": name, "fetched_at": fetched_at})
        pages.append((response.url, response.text, fetched_at))
    if failed:
        # load.py deletes passages missing from the file, so a partial run would wipe good ones
        sys.exit(f"{len(failed)} of {len(urls)} pages failed, so libraries.jsonl was not changed. "
                 "Try again later or from another network.")
    INDEX_FILE.write_text(json.dumps(index, indent=1), encoding="utf-8")
    print(f"Saved {len(pages)} pages")
    return pages


def saved_pages():
    """The pages from the last run, read from data/raw/ instead of the site."""
    index = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    return [(e["url"], (PAGES_DIR / e["file"]).read_text(encoding="utf-8"), e["fetched_at"])
            for e in index]


def main_content(soup):
    """The page's own text: <main>, without the menus, breadcrumbs, scripts or forms."""
    main = soup.find("main") or soup.find(id="content") or soup.body
    if main is None:
        return None
    for element in main.select("script, style, noscript, nav, header, footer, aside, form, button, "
                               ".breadcrumb, .breadcrumbs"):
        element.decompose()
    return main


def page_title(soup, fallback):
    """The page's <h1>, or its <title> without ' | University Libraries'."""
    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        return " ".join(h1.get_text(" ", strip=True).split())
    if soup.title and soup.title.get_text(strip=True):
        return " ".join(soup.title.get_text().split(" | ")[0].split())
    return fallback


def build_passages(pages):
    passages, seen = [], set()
    for url, html, fetched_at in pages:
        key = page_key(url)
        if key in seen:  # / and /index.html, or a redirect to a page already saved
            continue
        seen.add(key)
        soup = BeautifulSoup(html, "html.parser")
        title = page_title(soup, key)
        main = main_content(soup)
        if main is None:
            continue
        chunks = transportation.chunk_page(transportation.page_blocks(main))
        if word_count(" ".join(chunks)) < MIN_PAGE_WORDS:
            continue
        for i, chunk in enumerate(chunks, start=1):
            passages.append({
                "id": f"{SOURCE}:{key}:{i}",
                "source": SOURCE,
                "title": title,
                "text": chunk,
                "source_url": f"{BASE_URL}{urlsplit(url).path}",
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
                        help="re-parse the pages saved by the last run, with no requests")
    args = parser.parse_args()
    pages = saved_pages() if args.from_raw else fetch()
    write_passages(build_passages(pages))


if __name__ == "__main__":
    main()
