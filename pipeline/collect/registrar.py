"""Collect public information from the TAMU Registrar website.

Pages come from https://registrar.tamu.edu/sitemap.xml (policies, degree
audit, grading, graduation, FERPA, curricular services and recent news).
Academic calendar events come from the Registrar's RSS feeds.

Run from the repository root:
    python pipeline/collect/registrar.py

Outputs:
    data/raw/registrar/sitemap.xml, pages/*.html, calendar-*.xml
    data/processed/registrar.jsonl
"""

import json
import re
import shutil
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup


SOURCE = "registrar"
USER_AGENT = "AggieFlowCollector/0.1 (TAMU Aggie Data Science Club student project)"
# registrar.tamu.edu returns 404 to any request that doesn't look like a
# browser, including the collector user agent above. The PM approved sending
# a browser user agent for these public pages on Nov 16, 2026 (see DATA.md).
# The calendar feeds on calendar.tamu.edu still use USER_AGENT.
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)

BASE_URL = "https://registrar.tamu.edu"
SITEMAP_URL = f"{BASE_URL}/sitemap.xml"
# Pages that are only lists of links, plus news from 2024 and earlier, which
# is out of date for student questions.
SKIP_PAGES = re.compile(
    r"^/(search\.html|news/index\.html|news/newsfeed\.html|news/20(1\d|2[0-4])/)"
)

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = REPO_ROOT / "data" / "raw" / SOURCE
PAGES_DIR = RAW_DIR / "pages"
OUT_FILE = REPO_ROOT / "data" / "processed" / f"{SOURCE}.jsonl"

MIN_WORDS = 100
MAX_WORDS = 400
TARGET_WORDS = 250

CALENDAR_PAGES = {
    "fall-2026": "https://registrar.tamu.edu/academic-calendar/fall-2026.html",
    "spring-2027": "https://registrar.tamu.edu/academic-calendar/spring-2027.html",
    "summer-2027": "https://registrar.tamu.edu/academic-calendar/summer-2027.html",
}

CALENDAR_FEEDS = {
    "fall-2026": "fall%202026",
    "spring-2027": "spring%202027",
    "summer-2027": "summer%202027",
}


def fetch_calendar():
    """Download and save the RSS feed for each semester."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    for semester, tag in CALENDAR_FEEDS.items():
        url = (
            "https://calendar.tamu.edu/live/rss/events/"
            "group/Office%20of%20the%20Registrar/"
            f"tag/{tag}/"
            "start_date/-2%20years/end_date/+2%20years"
        )

        response = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=60,
        )
        response.raise_for_status()

        # Preserve the original RSS data.
        raw_file = RAW_DIR / f"calendar-{semester}.xml"
        raw_file.write_bytes(response.content)

        print(f"Saved {raw_file.name} ({len(response.content)} bytes)")

        # Respect the minimum one-second request delay.
        time.sleep(1)


def parse_calendar(semester):
    """Extract calendar events from a saved RSS feed."""
    raw_file = RAW_DIR / f"calendar-{semester}.xml"

    tree = ET.parse(raw_file)
    root = tree.getroot()
    events = []

    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        date = (item.findtext("pubDate") or "").strip()
        description_html = item.findtext("description") or ""
        event_id = (item.findtext("guid") or "").strip()

        # Remove HTML images and extract readable descriptions.
        soup = BeautifulSoup(description_html, "html.parser")

        for element in soup.find_all(["picture", "img", "script", "style"]):
            element.decompose()

        description = soup.get_text(separator=" ", strip=True)

        if not title or not link:
            continue

        text = f"{title}. Date: {date}."

        if description:
            text += f" {description}"

        events.append({
            "id": event_id,
            "title": title,
            "text": text,
            "source_url": link,
        })

    return events


def build_calendar_passages(events, semester):
    """Group calendar events into passages of about 100–400 words."""
    passages = []
    current = []
    fetched_at = now_utc()

    for event in events:
        # Keep events together until the passage reaches its target size.
        if (
            current
            and word_count(" ".join(current)) >= MIN_WORDS
            and word_count(" ".join(current + [event["text"]])) > TARGET_WORDS
        ):
            passages.append({
                "id": f"{SOURCE}:calendar-{semester}:{len(passages) + 1}",
                "source": SOURCE,
                "title": f"Academic Calendar - {semester}",
                "text": " ".join(current),
                "source_url": CALENDAR_PAGES[semester],
                "fetched_at": fetched_at,
            })
            current = []

        current.append(event["text"])

    if current:
        passages.append({
            "id": f"{SOURCE}:calendar-{semester}:{len(passages) + 1}",
            "source": SOURCE,
            "title": f"Academic Calendar - {semester}",
            "text": " ".join(current),
            "source_url": CALENDAR_PAGES[semester],
            "fetched_at": fetched_at,
        })

    # Merge a short final passage if the combined length stays within the limit.
    if len(passages) >= 2:
        last = passages[-1]
        previous = passages[-2]
        combined_text = previous["text"] + " " + last["text"]

        if (
            word_count(last["text"]) < MIN_WORDS
            and word_count(combined_text) <= MAX_WORDS
        ):
            previous["text"] = combined_text
            passages.pop()

    return passages


def now_utc():
    """Current time in the passage format, e.g. 2026-11-16T18:04:00Z."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def page_key(url):
    """'https://registrar.tamu.edu/graduation/faqs/index.html' -> 'graduation/faqs'."""
    path = url[len(BASE_URL):].strip("/")
    path = re.sub(r"(^|/)index\.html$", "", path)
    return re.sub(r"\.html$", "", path) or "home"


def sitemap_urls(sitemap_xml):
    """Registrar page URLs from the sitemap, minus the skipped ones."""
    root = ET.fromstring(sitemap_xml)
    urls = []
    # The sitemap uses an https:// namespace instead of the standard http://
    # one, so match <loc> in any namespace.
    for loc in root.findall(".//{*}loc"):
        url = (loc.text or "").strip()
        if not url.startswith(BASE_URL):
            continue
        if SKIP_PAGES.match(url[len(BASE_URL):]):
            continue
        urls.append(url)
    return sorted(set(urls))


def fetch_html_pages():
    """Fetch every page in the sitemap. Returns a list of (url, html, fetched_at)."""
    session = requests.Session()
    session.headers["User-Agent"] = BROWSER_USER_AGENT

    if PAGES_DIR.exists():
        shutil.rmtree(PAGES_DIR)
    PAGES_DIR.mkdir(parents=True)

    response = session.get(SITEMAP_URL, timeout=60)
    response.raise_for_status()
    (RAW_DIR / "sitemap.xml").write_bytes(response.content)
    urls = sitemap_urls(response.content)
    print(f"Fetching {len(urls)} pages from the sitemap")

    pages = []
    for url in urls:
        # Respect the minimum one-second request delay.
        time.sleep(1)
        response = session.get(url, timeout=60)
        if response.status_code == 404:
            print(f"  404, skipped: {url}")
            continue
        response.raise_for_status()

        # Preserve the original HTML.
        raw_file = PAGES_DIR / (page_key(url).replace("/", "__") + ".html")
        raw_file.write_bytes(response.content)
        pages.append((url, response.text, now_utc()))

    return pages


def page_blocks(html_text):
    """Extract headings and readable text from a saved HTML page."""
    soup = BeautifulSoup(html_text, "html.parser")

    main = soup.find("main")
    if main is None:
        main = soup.find("body")

    if main is None:
        return []

    # Remove navigation and other non-content elements.
    for element in main.find_all(
        ["script", "style", "nav", "footer", "form", "button"]
    ):
        element.decompose()

    # Remove the "Home > Academic Services > ..." breadcrumb trail.
    for element in main.select("[class*=breadcrumb]"):
        element.decompose()

    blocks = []
    tags = ["h1", "h2", "h3", "h4", "p", "li", "summary", "td", "th"]

    for element in main.find_all(True):
        # Keep each expandable FAQ question and answer in one block.
        if element.name == "details":
            question = element.find("summary")
            answer = element.find("div", class_="details__content")

            if question is not None and answer is not None:
                question_text = question.get_text(separator=" ", strip=True)
                answer_text = answer.get_text(separator=" ", strip=True)

                if question_text and answer_text:
                    blocks.append(("text", question_text + " " + answer_text))

            continue

        # Skip FAQ content already included above.
        if element.find_parent("details") is not None:
            continue

        is_faq_answer = (
            element.name == "div"
            and "details__content" in element.get("class", [])
        )

        if element.name not in tags and not is_faq_answer:
            continue

        # Avoid duplicating text from nested elements.
        if is_faq_answer and element.find(tags):
            continue

        if element.name == "li" and element.find(["p", "li"]):
            continue

        text = element.get_text(separator=" ", strip=True)

        if text:
            block_type = (
                "heading"
                if element.name in ["h1", "h2", "h3", "h4"]
                else "text"
            )
            blocks.append((block_type, text))

    return blocks


def word_count(text):
    """Count words in a text string."""
    return len(text.split())


def chunk_page(blocks):
    """Combine HTML text blocks into passages of about 100–400 words."""
    chunks = []
    current = []

    # Split any single block longer than MAX_WORDS (a long table or list)
    # into MAX_WORDS-sized pieces so no passage is oversized.
    sized = []
    for block_type, text in blocks:
        tokens = text.split()
        if block_type == "text" and len(tokens) > MAX_WORDS:
            for start in range(0, len(tokens), TARGET_WORDS):
                sized.append(("text", " ".join(tokens[start:start + TARGET_WORDS])))
        else:
            sized.append((block_type, text))

    for block_type, text in sized:
        # Keep headings with the following section.
        if block_type == "heading":
            current.append(text)
            continue

        if (
            current
            and word_count(" ".join(current)) >= MIN_WORDS
            and word_count(" ".join(current + [text])) > TARGET_WORDS
        ):
            chunks.append(" ".join(current))
            current = []

        current.append(text)

    if current:
        chunks.append(" ".join(current))

    # Merge a short final chunk if the combined length stays within the limit.
    if len(chunks) >= 2 and word_count(chunks[-1]) < MIN_WORDS:
        combined = chunks[-2] + " " + chunks[-1]
        if word_count(combined) <= MAX_WORDS:
            chunks[-2:] = [combined]

    return chunks


def page_title(html_text, fallback):
    """The page's h1, or its <title> without the site name."""
    soup = BeautifulSoup(html_text, "html.parser")
    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        return " ".join(h1.get_text(" ", strip=True).split())
    if soup.title:
        title = " ".join(soup.title.get_text().split()).split(" | ")[0]
        if title:
            return title
    return fallback


def build_passages(pages):
    """Convert fetched HTML pages into structured passage records."""
    passages = []

    for source_url, html_text, fetched_at in pages:
        key = page_key(source_url)

        blocks = page_blocks(html_text)
        chunks = chunk_page(blocks)

        title = page_title(html_text, key)

        for i, chunk in enumerate(chunks, start=1):
            passages.append({
                "id": f"{SOURCE}:{key}:{i}",
                "source": SOURCE,
                "title": title,
                "text": chunk,
                "source_url": source_url,
                "fetched_at": fetched_at,
            })

    return passages


def write_passages(passages):
    """Write processed passages to a JSONL file."""
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with OUT_FILE.open("w", encoding="utf-8") as file:
        for passage in passages:
            file.write(json.dumps(passage, ensure_ascii=False) + "\n")

    print(f"Saved {len(passages)} passages to {OUT_FILE.relative_to(REPO_ROOT)}")


def validate_passages():
    """Check that every processed passage has the required format."""
    required = {
        "id", "source", "title", "text", "source_url", "fetched_at"
    }
    seen_ids = set()
    errors = []
    warnings = 0
    count = 0

    with OUT_FILE.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            passage = json.loads(line)
            count += 1

            if set(passage) != required:
                errors.append(f"Line {line_number}: incorrect fields")

            # Each passage must have a unique identifier.
            passage_id = passage.get("id", "")
            if not passage_id or passage_id in seen_ids:
                errors.append(f"Line {line_number}: missing or duplicate ID")
            seen_ids.add(passage_id)

            if passage.get("source") != SOURCE:
                errors.append(f"Line {line_number}: incorrect source")

            if not passage.get("title") or not passage.get("text"):
                errors.append(f"Line {line_number}: empty title or text")

            # Short or long passages are worth a look but allowed, as in
            # pipeline/check.py (some Registrar pages are only a few lines).
            words = word_count(passage.get("text", ""))
            if not MIN_WORDS <= words <= MAX_WORDS:
                warnings += 1

            url = passage.get("source_url", "")
            if not url.startswith("https://"):
                errors.append(f"Line {line_number}: invalid source URL")

            # Ensure fetched_at is a timezone-aware timestamp.
            try:
                timestamp = datetime.fromisoformat(passage["fetched_at"])
                if timestamp.utcoffset() is None:
                    errors.append(f"Line {line_number}: missing timezone")
            except (ValueError, KeyError, TypeError):
                errors.append(f"Line {line_number}: invalid timestamp")

    print(f"Validated {count} passages ({warnings} outside {MIN_WORDS}-{MAX_WORDS} words).")

    if errors:
        for error in errors:
            print(f"FAIL: {error}")

        raise ValueError("Passage validation failed.")
    else:
        print("PASS: All passages satisfy the format checks.")


def main():
    # Download the latest RSS feeds for all three semesters.
    fetch_calendar()

    # Fetch every Registrar page listed in the sitemap.
    pages = fetch_html_pages()
    html_passages = build_passages(pages)

    # Process each semester's calendar events.
    calendar_passages = []

    for semester in CALENDAR_FEEDS:
        events = parse_calendar(semester)
        semester_passages = build_calendar_passages(events, semester)

        calendar_passages.extend(semester_passages)

        print(
            f"{semester}: {len(events)} events, "
            f"{len(semester_passages)} passages"
        )

    # Combine HTML and calendar passages.
    passages = html_passages + calendar_passages
    write_passages(passages)

    print(f"\nHTML passages: {len(html_passages)}")
    print(f"Calendar passages: {len(calendar_passages)}")
    print(f"Total passages: {len(passages)}")

    validate_passages()


if __name__ == "__main__":
    main()
