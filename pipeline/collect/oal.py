#!/usr/bin/env python3
from collections import deque
import hashlib
import json
import re
import shutil
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag

# Configuration
SOURCE_NAME = "oal"
BASE_URL = "https://www.it.tamu.edu"
ROBOTS_URL = f"{BASE_URL}/robots.txt"
SITEMAP_XML_URL = f"{BASE_URL}/sitemap.xml"
SITEMAP_HTML_URL = f"{BASE_URL}/sitemap.html"

REQUEST_DELAY_SEC = 1.0
REQUEST_TIMEOUT_SEC = 20
# Arbitrary safety limit. 
MAX_PAGES = 500

MIN_CHUNK_WORDS = 100
MAX_CHUNK_WORDS = 400

RAW_DIR = Path(f"data/raw/{SOURCE_NAME}")
PROCESSED_FILE = Path(f"data/processed/{SOURCE_NAME}.jsonl")

# Use a standard browser User-Agent, because 404 to custom bot User-Agents
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

SKIP_EXTENSIONS = (
    ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp",
    ".xml", ".json", ".zip", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
)


# Making a web scraper from scratch doesn't seem too impressive anymore. Unfortunate.
# This script is AI-assisted.


# Fetching & URL Helpers

def get_utc_timestamp() -> str:
    """Return current UTC timestamp in ISO 8601 format (YYYY-MM-DDTHH:MM:SSZ)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_url(href: str, base: str = BASE_URL) -> str | None:
    """Resolve relative links, strip fragments/queries, and keep only public it.tamu.edu pages."""
    if not href or href.startswith(("mailto:", "tel:", "javascript:", "#")):
        return None

    full_url, _ = urldefrag(urljoin(base, href.strip()))
    parsed = urlparse(full_url)

    if parsed.netloc.lower() not in {"www.it.tamu.edu", "it.tamu.edu"}:
        return None

    path = parsed.path or "/"
    if any(path.lower().endswith(ext) for ext in SKIP_EXTENSIONS):
        return None

    return f"{BASE_URL}{path}"


def url_to_page_key(url: str) -> str:
    """
    Convert a URL into a stable, filesystem-safe slug for IDs and filenames.
    Example:
      https://www.it.tamu.edu/services/services-by-category/infrastructure/eduroam.html
      -> services--services-by-category--infrastructure--eduroam
    """
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    if path.endswith(".html") or path.endswith(".htm"):
        path = path.rsplit(".", 1)[0]
    if path.endswith("/index"):
        path = path[: -len("/index")]
    if not path or path == "index":
        return "home"

    slug = re.sub(r"[^a-zA-Z0-9_-]+", "--", path).strip("-")
    if len(slug) > 140:
        digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:8]
        slug = f"{slug[:130]}-{digest}"
    return slug


def parse_xml_sitemap(xml_bytes: bytes, session: requests.Session) -> list[str]:
    root = ET.fromstring(xml_bytes)

    urls: list[str] = []

    # Use wildcard namespace matching ({*}) so <loc> tags match regardless of xmlns.
    sitemap_locs = root.findall(".//{*}sitemap/{*}loc")
    if sitemap_locs:
        for loc in sitemap_locs:
            sub_url = (loc.text or "").strip()
            if not sub_url:
                continue
            time.sleep(REQUEST_DELAY_SEC)
            try:
                resp = session.get(sub_url, timeout=REQUEST_TIMEOUT_SEC)
                if resp.status_code == 200:
                    urls.extend(parse_xml_sitemap(resp.content, session))
            except (requests.RequestException, ET.ParseError):
                # Skip a broken sub-sitemap instead of aborting all sibling sitemaps.
                continue
        return list(dict.fromkeys(urls))

    for loc in root.findall(".//{*}url/{*}loc"):
        norm = normalize_url((loc.text or "").strip())
        if norm:
            urls.append(norm)

    return list(dict.fromkeys(urls))


# (used for footer sitemap discovery & BFS crawl)
def extract_internal_links(html_text: str, page_url: str) -> list[str]:
    soup = BeautifulSoup(html_text, "html.parser")
    links: list[str] = []
    for a_tag in soup.find_all("a", href=True):
        norm = normalize_url(a_tag["href"], base=page_url)
        if norm:
            links.append(norm)
    return list(dict.fromkeys(links))


def get_seed_urls(session: requests.Session) -> list[str]:
    seeds: list[str] = [
        f"{BASE_URL}/",
        f"{BASE_URL}/services/services-a-z/index.html",
        f"{BASE_URL}/services/services-by-category/index.html",
        f"{BASE_URL}/security-and-policy/index.html",
        f"{BASE_URL}/about/news/index.html",
    ]
    xml_candidates = [SITEMAP_XML_URL, SITEMAP_HTML_URL]

    # 1. Check robots.txt for any declared Sitemap URL
    try:
        robots_resp = session.get(ROBOTS_URL, timeout=REQUEST_TIMEOUT_SEC)
        if robots_resp.status_code == 200:
            (RAW_DIR / "robots.txt").write_bytes(robots_resp.content)
            for line in robots_resp.text.splitlines():
                if line.lower().startswith("sitemap:"):
                    declared = line.split(":", 1)[1].strip()
                    if declared and (declared not in xml_candidates):
                        xml_candidates.insert(0, declared)
        time.sleep(REQUEST_DELAY_SEC)
    except requests.RequestException:
        pass

    # 2. Try XML sitemap candidates if they exist
    for xml_url in xml_candidates:
        try:
            resp = session.get(xml_url, timeout=REQUEST_TIMEOUT_SEC)
            if resp.status_code == 200 and (b"<urlset" in resp.content or b"<sitemapindex" in resp.content):
                # Parse first, only write/log sitemap.xml once xml_urls is non-empty.
                xml_urls = parse_xml_sitemap(resp.content, session)
                if xml_urls:
                    print(f"[{SOURCE_NAME}] Using XML sitemap: {xml_url}")
                    (RAW_DIR / "sitemap.xml").write_bytes(resp.content)
                    return xml_urls
        except (requests.RequestException, ET.ParseError):
            pass
        time.sleep(REQUEST_DELAY_SEC)

    # 3. Otherwise, seed from homepage (which includes the live footer Sitemap link & nav)
    print(f"[{SOURCE_NAME}] No XML sitemap found; discovering pages starting from {BASE_URL}/")
    return list(dict.fromkeys(seeds))


# HTML Cleaning & Section Extraction

def clean_whitespace(text: str) -> str:
    """Turn whitespace and newlines into single spaces."""
    return re.sub(r"\s+", " ", text).strip()


def extract_main_container(soup: BeautifulSoup) -> Tag:
    """Strip boilerplate from pages."""
    for tag in soup(["script", "style", "noscript", "svg", "iframe", "nav", "header", "footer", "aside", "form"]):
        tag.decompose()

    main = (
        soup.find("main")
        or soup.find(id="main-content")
        or soup.find(id="content")
        or soup.find("article")
        or soup.find(class_=re.compile(r"(main-content|page-content|content-area)", re.I))
        or soup.body
        or soup
    )

    for noisy in main.find_all(
        attrs={
            "class": re.compile(
                r"(breadcrumb|sidebar|side-nav|subnav|footer|social|share|last-modified|skip-link)",
                re.I,
            )
        }
    ):
        noisy.decompose()

    return main


def extract_page_title(soup: BeautifulSoup, main: Tag) -> str:
    """From <h1> or <title>"""
    h1 = main.find("h1") or soup.find("h1")
    if h1:
        title = clean_whitespace(h1.get_text(" ", strip=True))
        if title:
            return title

    if soup.title and soup.title.string:
        raw_title = clean_whitespace(soup.title.string)
        raw_title = re.split(r"\s*[\|\-–—]\s*(?:Technology Services|Texas A&M)", raw_title)[0]
        if raw_title:
            return raw_title

    return "Texas A&M Technology Services"


def extract_sections(html: str) -> tuple[str, list[tuple[str, str]]]:
    """
    Return (page_title, [(section_title, section_text), ...]).
    """
    soup = BeautifulSoup(html, "html.parser")
    main = extract_main_container(soup)
    page_title = extract_page_title(soup, main)

    sections: list[tuple[str, list[str]]] = []
    current_heading = page_title
    current_blocks: list[str] = []

    block_tags = {"h1", "h2", "h3", "h4", "p", "li", "td", "th", "blockquote", "pre"}
    seen_texts: set[str] = set()

    for el in main.find_all(block_tags):
        if any(parent.name in {"li", "td", "th", "blockquote"} for parent in el.parents if parent != main):
            continue

        text = clean_whitespace(el.get_text(" ", strip=True))
        if not text:
            continue

        if el.name == "h1":
            continue

        if el.name in {"h2", "h3"}:
            if current_blocks:
                sections.append((current_heading, current_blocks))
                current_blocks = []
            current_heading = f"{page_title} - {text}" if text.lower() != page_title.lower() else page_title
            seen_texts.clear()
            continue

        if el.name == "li":
            text = f"- {text}"

        if text not in seen_texts:
            current_blocks.append(text)
            seen_texts.add(text)

    if current_blocks:
        sections.append((current_heading, current_blocks))

    rendered_sections = [(title, " ".join(blocks)) for title, blocks in sections if blocks]
    return page_title, rendered_sections


# Sentence-Safe Chunking (100 - 400 words)

def split_into_sentences(text: str) -> list[str]:
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z0-9"\'\(\-])', text)
    return [s.strip() for s in sentences if s.strip()]


def chunk_sections(
    page_title: str,
    sections: list[tuple[str, str]],
    min_words: int = MIN_CHUNK_WORDS,
    max_words: int = MAX_CHUNK_WORDS,
) -> list[tuple[str, str]]:
    raw_chunks: list[tuple[str, str]] = []

    for sec_title, sec_text in sections:
        words = sec_text.split()
        if len(words) <= max_words:
            raw_chunks.append((sec_title, sec_text))
            continue

        sentences = split_into_sentences(sec_text)
        buf: list[str] = []
        buf_words = 0

        for sentence in sentences:
            s_words = len(sentence.split())
            if buf and (buf_words + s_words > max_words):
                raw_chunks.append((sec_title, " ".join(buf)))
                buf = [sentence]
                buf_words = s_words
            else:
                buf.append(sentence)
                buf_words += s_words

        if buf:
            raw_chunks.append((sec_title, " ".join(buf)))

    merged: list[tuple[str, str]] = []
    for title, text in raw_chunks:
        if not merged:
            merged.append((title, text))
            continue

        prev_title, prev_text = merged[-1]
        prev_wc = len(prev_text.split())
        curr_wc = len(text.split())

        if (prev_wc < min_words or curr_wc < min_words) and (prev_wc + curr_wc <= max_words):
            combined_title = prev_title if prev_title == title else page_title
            merged[-1] = (combined_title, f"{prev_text} {text}")
        else:
            merged.append((title, text))

    return merged


# Main Pipeline

def main():
    if RAW_DIR.exists():
        shutil.rmtree(RAW_DIR)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_FILE.parent.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers.update(HEADERS)

    seed_urls = get_seed_urls(session)
    queue: deque[str] = deque(seed_urls)
    queued_or_visited: set[str] = set(seed_urls)
    used_xml_sitemap = (RAW_DIR / "sitemap.xml").exists()

    total_passages = 0
    fetched_pages = 0
    skipped_pages = 0

    # BFS
    with PROCESSED_FILE.open("w", encoding="utf-8") as out_f:
        while queue and fetched_pages < MAX_PAGES:
            url = queue.popleft()
            time.sleep(REQUEST_DELAY_SEC)
            page_key = url_to_page_key(url)

            try:
                resp = session.get(url, timeout=REQUEST_TIMEOUT_SEC, allow_redirects=True)
                if resp.status_code == 404:
                    print(f"  SKIP 404: {url}")
                    skipped_pages += 1
                    continue
                resp.raise_for_status()
            except requests.RequestException as exc:
                print(f"  WARN failed to fetch {url}: {exc}")
                skipped_pages += 1
                continue

            final_host = urlparse(resp.url).netloc.lower()
            if "cas.tamu.edu" in final_host or "login" in final_host:
                print(f"  SKIP gated login redirect: {url}")
                skipped_pages += 1
                continue

            # Mark resolved final URL as visited too so redirects aren't fetched twice
            norm_final = normalize_url(resp.url)
            if norm_final:
                queued_or_visited.add(norm_final)

            content_type = resp.headers.get("Content-Type", "").lower()
            if "text/html" not in content_type:
                skipped_pages += 1
                continue

            fetched_at = get_utc_timestamp()
            fetched_pages += 1

            raw_path = RAW_DIR / f"{page_key}.html"
            raw_path.write_bytes(resp.content)

            if not used_xml_sitemap:
                for link in extract_internal_links(resp.text, resp.url):
                    if link not in queued_or_visited:
                        queued_or_visited.add(link)
                        queue.append(link)

            # Parse, clean, and chunk
            page_title, sections = extract_sections(resp.text)
            chunks = chunk_sections(page_title, sections)

            for chunk_num, (chunk_title, chunk_text) in enumerate(chunks, start=1):
                if len(chunk_text.split()) < 15:
                    continue

                record = {
                    "id": f"{SOURCE_NAME}:{page_key}:{chunk_num}",
                    "source": SOURCE_NAME,
                    "title": chunk_title,
                    "source_url": norm_final or url,
                    "fetched_at": fetched_at,
                    "text": chunk_text,
                }
                out_f.write(json.dumps(record, ensure_ascii=False) + "\n")
                total_passages += 1

            if fetched_pages % 25 == 0:
                print(
                    f"  Fetched {fetched_pages} pages | Queue: {len(queue)} | "
                    f"Passages written: {total_passages}"
                )

    print(
        f"[{SOURCE_NAME}] Done. Fetched {fetched_pages} pages, wrote {total_passages} passages "
        f"to {PROCESSED_FILE} (skipped {skipped_pages} URLs)."
    )


if __name__ == "__main__":
    main()