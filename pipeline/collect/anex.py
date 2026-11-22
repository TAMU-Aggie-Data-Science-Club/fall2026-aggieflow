"""Collect Texas A&M grade distributions from anex.us (https://anex.us/grades/).

anex.us is an unofficial, student-built site. Its search page loads grades
from one JSON feed: POST https://anex.us/grades/getData/ with dept and
number. The feed returns every section of that course since Spring 2015,
with the professor and the count of each grade, but it has no list of
courses. So this script:

1. Reads the list of undergraduate courses from the TAMU Course Catalog
   (one index page, then one page per subject).
2. Asks the anex.us feed for each course, waiting between requests.
3. Turns the numbers into short sentences:
   - one summary passage per course (all semesters, plus the professors
     who taught it recently, ranked by average GPA)
   - one passage per professor who taught the course recently, with
     their grades semester by semester.

Run from the repo root:
    python pipeline/collect/anex.py              # every course, about three hours
    python pipeline/collect/anex.py --limit 20   # first 20 courses, for testing
    python pipeline/collect/anex.py --resume     # continue a run that stopped
    python pipeline/collect/anex.py --from-raw   # re-parse saved files, no requests

anex.us sometimes stops answering for a while if it gets many requests in a
row. When that happens the script waits and retries for up to about 20
minutes, then skips that course. If several courses in a row fail, it stops
and tells you to run it again later with --resume, which keeps every course
already fetched.

Writes:
    data/raw/anex/catalog/<page>.html     catalog pages used for the course list
    data/raw/anex/grades/<DEPT>-<NUM>.json exactly what the feed returned
    data/processed/anex.jsonl             one passage per line
"""

import argparse
import json
import random
import re
import shutil
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import requests

SOURCE = "anex"
FEED_URL = "https://anex.us/grades/getData/"
PAGE_URL = "https://anex.us/grades/?dept={dept}&number={number}"
CATALOG_INDEX = "https://catalog.tamu.edu/undergraduate/course-descriptions/"
CATALOG_BASE = "https://catalog.tamu.edu"
USER_AGENT = "AggieFlowCollector/0.1 (TAMU Aggie Data Science Club student project)"
DELAY_SECONDS = 2  # team rule is at least 1 second; anex.us cut us off at 1
# After a failed request, wait this many seconds before each retry.
RETRY_WAITS = [30, 60, 120, 300, 600]
# Stop the run after this many courses in a row fail every retry.
MAX_FAILED_IN_A_ROW = 3

# Only professors who taught the course in this year or later get their own
# passage. Older professors still count toward the course summary.
RECENT_SINCE_YEAR = 2023
# A professor needs this many graded students to appear in the summary's ranking.
MIN_RANKED_STUDENTS = 30
MAX_WORDS = 400

GRADES = ["A", "B", "C", "D", "F"]
POINTS = {"A": 4, "B": 3, "C": 2, "D": 1, "F": 0}
TERM_ORDER = {"SPRING": 1, "SUMMER": 2, "FALL": 3}
COURSE_TITLE = re.compile(r"^([A-Z]{3,4})\s(\d{3})[A-Z]?\b")

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = REPO_ROOT / "data" / "raw" / SOURCE
CATALOG_RAW = RAW_DIR / "catalog"
GRADES_RAW = RAW_DIR / "grades"
OUT_FILE = REPO_ROOT / "data" / "processed" / f"{SOURCE}.jsonl"


# --- Fetching -------------------------------------------------------------

def now_utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Fetcher:
    """Waits DELAY_SECONDS between requests and retries failures."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self.last = 0.0

    def request(self, method, url, **kwargs):
        for attempt in range(len(RETRY_WAITS) + 1):
            wait = DELAY_SECONDS - (time.monotonic() - self.last)
            if wait > 0:
                time.sleep(wait)
            self.last = time.monotonic()
            try:
                resp = self.session.request(method, url, timeout=30, **kwargs)
                resp.raise_for_status()
                return resp.text
            except requests.RequestException as err:
                if attempt == len(RETRY_WAITS):
                    raise
                pause = RETRY_WAITS[attempt]
                print(f"  {url} failed ({type(err).__name__}); waiting {pause}s before retrying",
                      file=sys.stderr)
                time.sleep(pause)


def subject_pages(index_html):
    """Links to each subject's course list, like .../course-descriptions/csce/."""
    from bs4 import BeautifulSoup  # only the course list needs it; the agent's live grades don't

    soup = BeautifulSoup(index_html, "html.parser")
    paths = []
    for a in soup.select('a[href*="/undergraduate/course-descriptions/"]'):
        href = a.get("href", "")
        if re.fullmatch(r"/undergraduate/course-descriptions/[a-z]+/", href) and href not in paths:
            paths.append(href)
    return paths


def courses_on_page(subject_html):
    """Course codes on one subject page, as (DEPT, NUMBER) pairs."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(subject_html, "html.parser")
    found = []
    for title in soup.select(".courseblocktitle"):
        text = title.get_text(" ").replace("\xa0", " ").strip()
        match = COURSE_TITLE.match(text)
        if match and match.groups() not in found:
            found.append(match.groups())
    return found


def fetch_course_list(fetcher):
    CATALOG_RAW.mkdir(parents=True, exist_ok=True)
    index_html = fetcher.request("GET", CATALOG_INDEX)
    (CATALOG_RAW / "index.html").write_text(index_html, encoding="utf-8")
    courses = []
    pages = subject_pages(index_html)
    for i, path in enumerate(pages, start=1):
        html_text = fetcher.request("GET", CATALOG_BASE + path)
        name = path.rstrip("/").rsplit("/", 1)[-1]
        (CATALOG_RAW / f"{name}.html").write_text(html_text, encoding="utf-8")
        for course in courses_on_page(html_text):
            if course not in courses:
                courses.append(course)
        if i % 25 == 0:
            print(f"  catalog: {i}/{len(pages)} subjects, {len(courses)} courses so far")
    return courses


def course_list_from_raw():
    courses = []
    for page in sorted(CATALOG_RAW.glob("*.html")):
        if page.name == "index.html":
            continue
        for course in courses_on_page(page.read_text(encoding="utf-8")):
            if course not in courses:
                courses.append(course)
    return courses


def raw_grades_path(dept, number):
    return GRADES_RAW / f"{dept}-{number}.json"


def fetch_grades(fetcher, courses):
    """Fetch each course not already saved. Returns True if every course was
    fetched, False if the run stopped early because anex.us stopped answering."""
    GRADES_RAW.mkdir(parents=True, exist_ok=True)
    todo = [c for c in courses if not raw_grades_path(*c).exists()]
    if len(todo) < len(courses):
        print(f"  {len(courses) - len(todo)} courses already saved, {len(todo)} to go")
    failed_in_a_row, skipped = 0, []
    for i, (dept, number) in enumerate(todo, start=1):
        try:
            # The feed needs an uppercase department and only accepts POST.
            body = fetcher.request("POST", FEED_URL, data={"dept": dept.upper(), "number": number})
        except requests.RequestException:
            skipped.append(f"{dept} {number}")
            failed_in_a_row += 1
            print(f"  skipped {dept} {number} after every retry failed", file=sys.stderr)
            if failed_in_a_row >= MAX_FAILED_IN_A_ROW:
                print(f"\nanex.us stopped answering. {i - len(skipped)} of {len(todo)} courses "
                      "fetched this run and saved. Try again later with --resume.", file=sys.stderr)
                return False
            continue
        failed_in_a_row = 0
        raw_grades_path(dept, number).write_text(body, encoding="utf-8")
        if i % 100 == 0:
            print(f"  anex: {i}/{len(todo)} courses fetched")
    if skipped:
        print(f"  {plural(len(skipped), 'course')} skipped; run with --resume to retry: {', '.join(skipped)}")
    return not skipped


# --- Turning numbers into passages ----------------------------------------

def load_sections(body):
    """Parse a feed response. A course with no data comes back as broken
    JSON ({"classes":]}), which counts as no sections."""
    try:
        return json.loads(body).get("classes") or []
    except json.JSONDecodeError:
        return []


def term_key(year, term):
    return (int(year), TERM_ORDER.get(term, 0))


def term_name(year, term):
    return f"{term.title()} {year}"


class Tally:
    """Grade counts for a group of sections."""

    def __init__(self):
        self.counts = defaultdict(int)
        self.sections = 0
        self.honors = 0

    def add(self, section):
        self.sections += 1
        if str(section.get("section", "")).startswith("2"):
            self.honors += 1
        for grade in GRADES + ["Q"]:
            try:
                self.counts[grade] += int(section.get(grade) or 0)
            except ValueError:
                pass

    @property
    def graded(self):
        return sum(self.counts[g] for g in GRADES)

    @property
    def gpa(self):
        if not self.graded:
            return None
        return sum(POINTS[g] * self.counts[g] for g in GRADES) / self.graded

    def pct(self, grade):
        return round(100 * self.counts[grade] / self.graded) if self.graded else 0

    def describe(self):
        """'82 students, average GPA 3.12, 41% A, 30% B, 18% C, 6% D, 5% F, 3 Q-drops'"""
        if not self.graded:
            return f"no letter grades recorded, {self.counts['Q']} Q-drops"
        letters = ", ".join(f"{self.pct(g)}% {g}" for g in GRADES)
        return (f"{self.graded} students, average GPA {self.gpa:.2f}, {letters}, "
                f"{plural(self.counts['Q'], 'Q-drop')}")


def plural(n, word):
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def term_span(first, last):
    """'in Fall 2023' or 'from Fall 2023 to Fall 2025'."""
    return f"in {first}" if first == last else f"from {first} to {last}"


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def ranked_professors(sections):
    """[(professor, Tally)] for professors who taught since RECENT_SINCE_YEAR, counting
    only those sections, with at least MIN_RANKED_STUDENTS graded students; highest
    GPA first (ties by name). The course summary's ranking and the UI's grade chart
    both come from this, so they always agree."""
    recent = defaultdict(Tally)
    for s in sections:
        year = str(s.get("year", ""))
        if year.isdigit() and int(year) >= RECENT_SINCE_YEAR:
            recent[(s.get("prof") or "UNKNOWN").strip()].add(s)
    ranked = [(p, t) for p, t in recent.items() if t.graded >= MIN_RANKED_STUDENTS]
    return sorted(ranked, key=lambda pt: (-pt[1].gpa, pt[0]))


def course_passages(dept, number, sections, fetched_at):
    code = f"{dept} {number}"
    url = PAGE_URL.format(dept=dept, number=number)
    course_slug = f"{dept.lower()}-{number}"

    overall = Tally()
    by_prof = defaultdict(Tally)
    by_prof_term = defaultdict(lambda: defaultdict(Tally))
    terms = set()
    for s in sections:
        year, term, prof = s.get("year", ""), s.get("semester", ""), (s.get("prof") or "UNKNOWN").strip()
        overall.add(s)
        by_prof[prof].add(s)
        by_prof_term[prof][(year, term)].add(s)
        terms.add((year, term))
    if not terms:
        return []

    ordered = sorted(terms, key=lambda t: term_key(*t))
    first, last = term_name(*ordered[0]), term_name(*ordered[-1])
    recent = sorted(
        (p for p in by_prof if any(int(y) >= RECENT_SINCE_YEAR for y, _ in by_prof_term[p])),
    )

    # Course summary.
    lines = [
        f"Grade distribution for {code} at Texas A&M from anex.us, {term_span(first, last)}: "
        f"{plural(overall.sections, 'section')} taught by {plural(len(by_prof), 'professor')}. "
        f"Overall: {overall.describe()}."
    ]
    ranked = ranked_professors(sections)
    if ranked:
        parts = [f"{p} {t.gpa:.2f} ({t.graded} students)" for p, t in ranked]
        lines.append(
            f"Average GPA by professor since {RECENT_SINCE_YEAR} (professors with at least "
            f"{MIN_RANKED_STUDENTS} graded students), highest first: " + "; ".join(parts) + "."
        )
    summary = trim_words("\n".join(lines))
    passages = [{
        "id": f"{SOURCE}:{course_slug}:1",
        "source": SOURCE,
        "title": f"{code} grade distribution (all professors)",
        "text": summary,
        "source_url": url,
        "fetched_at": fetched_at,
    }]

    # One passage per recent professor, newest semester first.
    for prof in recent:
        tally = by_prof[prof]
        terms_taught = sorted(by_prof_term[prof], key=lambda t: term_key(*t), reverse=True)
        span = term_span(term_name(*terms_taught[-1]), term_name(*terms_taught[0]))
        head = (f"{code} with {prof} at Texas A&M (grades from anex.us): "
                f"{plural(tally.sections, 'section')} {span}. Overall: {tally.describe()}.")
        if tally.honors:
            head += f" {tally.honors} of these sections were honors sections."
        sem_lines = []
        for t in terms_taught:
            st = by_prof_term[prof][t]
            sem_lines.append(f"{term_name(*t)}: {plural(st.sections, 'section')}, {st.describe()}.")
        chunks = pack(head, sem_lines)
        prof_slug = f"{course_slug}-{slug(prof)}"
        for i, text in enumerate(chunks, start=1):
            passages.append({
                "id": f"{SOURCE}:{prof_slug}:{i}",
                "source": SOURCE,
                "title": f"{code} grades with {prof}",
                "text": text,
                "source_url": url,
                "fetched_at": fetched_at,
            })
    return passages


def words(text):
    return len(text.split())


def trim_words(text):
    """Keep a summary under MAX_WORDS by dropping the lowest-ranked professors."""
    while words(text) > MAX_WORDS and "; " in text:
        text = text.rsplit("; ", 1)[0] + "."
    return text


def pack(head, lines):
    """Head plus as many semester lines as fit; the rest continue in more
    passages that repeat the head, so each one reads on its own."""
    chunks, cur = [], [head]
    for line in lines:
        if words("\n".join(cur + [line])) > MAX_WORDS and len(cur) > 1:
            chunks.append("\n".join(cur))
            cur = [head + " (continued)"]
        cur.append(line)
    chunks.append("\n".join(cur))
    return chunks


def build_passages(courses, fetched_at):
    passages, with_data = [], 0
    for dept, number in courses:
        path = raw_grades_path(dept, number)
        if not path.exists():
            continue
        made = course_passages(dept, number, load_sections(path.read_text(encoding="utf-8")), fetched_at)
        if made:
            with_data += 1
        passages.extend(made)
    return passages, with_data


def write_passages(passages):
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with OUT_FILE.open("w", encoding="utf-8") as f:
        for p in passages:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--limit", type=int, help="only fetch the first N courses")
    parser.add_argument("--resume", action="store_true",
                        help="keep saved files and fetch only the courses still missing")
    parser.add_argument("--from-raw", action="store_true", help="re-parse saved files, no requests")
    args = parser.parse_args()

    stamp = RAW_DIR / "fetched_at.txt"
    complete = True
    if args.from_raw:
        courses = course_list_from_raw()
        fetched_at = stamp.read_text().strip() if stamp.exists() else now_utc()
    else:
        fetcher = Fetcher()
        if args.resume and stamp.exists() and (CATALOG_RAW / "index.html").exists():
            courses = course_list_from_raw()
            fetched_at = stamp.read_text().strip()
            print(f"Resuming the run started {fetched_at} ({len(courses)} courses in the list)")
        else:
            if RAW_DIR.exists():
                shutil.rmtree(RAW_DIR)
            RAW_DIR.mkdir(parents=True)
            fetched_at = now_utc()
            stamp.write_text(fetched_at)
            print("Reading the course list from the catalog...")
            courses = fetch_course_list(fetcher)
        if args.limit:
            courses = courses[: args.limit]
        print(f"Fetching grades for {len(courses)} courses from anex.us...")
        complete = fetch_grades(fetcher, courses)
    if args.limit:
        courses = courses[: args.limit]

    passages, with_data = build_passages(courses, fetched_at)
    write_passages(passages)

    counts = [words(p["text"]) for p in passages] or [0]
    print(f"Courses checked: {len(courses)}, with grade data: {with_data}")
    print(f"Wrote {len(passages)} passages to {OUT_FILE.relative_to(REPO_ROOT)}")
    print(f"Words per passage: min {min(counts)}, median {sorted(counts)[len(counts) // 2]}, max {max(counts)}")
    if passages:
        print("Three random passages:")
        for p in random.sample(passages, min(3, len(passages))):
            print(f"  {p['id']}  {p['title']}  ({words(p['text'])} words)")
    if not complete:
        print("\nNot finished: some courses are missing. Run again with --resume.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
