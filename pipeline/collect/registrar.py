"""Collect public information from the TAMU Registrar website.

Run from the repository root:
    python pipeline/collect/registrar.py

Outputs:
    data/raw/registrar/
    data/processed/registrar.jsonl
"""

import json
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup


SOURCE = "registrar"
USER_AGENT = "AggieFlowCollector/0.1 (TAMU Aggie Data Science Club student project)"

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = REPO_ROOT / "data" / "raw" / SOURCE
OUT_FILE = REPO_ROOT / "data" / "processed" / f"{SOURCE}.jsonl"

MIN_WORDS = 100
MAX_WORDS = 400
TARGET_WORDS = 250

# Original URLs for the HTML pages manually saved from Chrome.
PAGE_URLS = {
    "grading.html": "https://registrar.tamu.edu/academic-services/grading/index.html",
    "graduation-faqs.html": "https://registrar.tamu.edu/graduation/faqs/index.html",
    "q-drops.html": "https://registrar.tamu.edu/academic-services/records-administration-archives/q-drops.html",
    "registration.html": "https://registrar.tamu.edu/registration-scheduling-and-analytics/index.html",
}

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
    fetched_at = datetime.now(timezone.utc).isoformat()

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


def load_html_pages():
    """Read the Registrar HTML pages manually saved from Chrome."""
    pages = []

    # All four HTML snapshots are required for the complete dataset.
    for filename in PAGE_URLS:
        if not (RAW_DIR / filename).is_file():
            raise FileNotFoundError(
                f"Missing {filename}. Save the Registrar page from Chrome first."
            )

    for file in sorted(RAW_DIR.glob("*.html")):
        html_text = file.read_text(encoding="utf-8")
        pages.append((file.name, html_text))

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

    for block_type, text in blocks:
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

    return chunks


def build_passages(pages):
    """Convert saved HTML pages into structured passage records."""
    passages = []
    fetched_at = datetime.now(timezone.utc).isoformat()

    for filename, html_text in pages:
        source_url = PAGE_URLS[filename]
        page_key = Path(filename).stem

        blocks = page_blocks(html_text)
        chunks = chunk_page(blocks)

        title = blocks[0][1] if blocks else page_key

        for i, chunk in enumerate(chunks, start=1):
            passages.append({
                "id": f"{SOURCE}:{page_key}:{i}",
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

            words = word_count(passage.get("text", ""))
            if not MIN_WORDS <= words <= MAX_WORDS:
                errors.append(f"Line {line_number}: {words} words")

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

    print(f"Validated {count} passages.")

    if errors:
        for error in errors:
            print(f"FAIL: {error}")

        raise ValueError("Passage validation failed.")
    else:
        print("PASS: All passages satisfy the format checks.")


def main():
    # Download the latest RSS feeds for all three semesters.
    fetch_calendar()

    # Process the locally saved HTML pages.
    pages = load_html_pages()
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
