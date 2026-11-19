# Data

This file explains the project's **data sources** — where they come from, how to get them, and how to think about using them. It is the contextual companion to the [`data/`](data/) folder.

> **`DATA.md` is tracked in git. The `data/` folder is not.** Documentation about the data lives here, in version control, so the whole team shares one understanding. The datasets themselves live in `data/`, which is **git-ignored** — raw data is often large, private, or licensed, and must never be committed. Clone the repo, then populate `data/` locally by following the sources below.

## Where to look for sources

At the start of the project, before committing to a source, scan these in roughly this order:

1. **A source the club or a sponsor already provides.** If the project came with data, that's your primary source — document it first.
2. **Official / authoritative open data.** Government portals (e.g. data.gov), inter-governmental bodies, and official statistics agencies. Highest trust, usually well-documented, clear licensing.
3. **Curated dataset hubs.** Kaggle, Hugging Face Datasets, UCI ML Repository, Google Dataset Search, AWS/Azure open-data registries. Fast to start with; check the license and provenance.
4. **Domain-specific repositories / APIs.** Whatever is standard for the project's field (e.g. a scientific archive, a public API, a research consortium). Often the richest and most relevant.
5. **First-party collection.** Surveys, scraping (only where permitted), or instrumentation you build. Highest effort and the most responsibility — get PM sign-off first.

## How to think about using a source (high level)

Before you rely on a dataset, a member should be able to answer these — and record the answers in the source's row below:

- **License & permission.** Are we allowed to use it for this purpose, and to share results? If unclear, ask a PM before building on it.
- **Provenance.** Who produced it, when, and how? Freshness and collection method shape what conclusions are valid.
- **Fitness.** Does it actually measure what the project needs? Coverage, granularity, and sample size matter more than size.
- **Sensitivity.** Any PII, confidential, or ethically sensitive content? If yes, that dictates storage and handling — and it stays out of git regardless.
- **Reproducibility.** Can a teammate re-fetch it from your notes alone? If not, the source isn't documented well enough yet.

Choosing and vetting a source is a **judgment call** — surface it to a PM rather than deciding a major data direction alone.

## Source register

Document every source here as you adopt it. Replace these placeholders.

| Source | Origin / URL | Access method | License | Sensitivity | Notes |
|--------|--------------|---------------|---------|-------------|-------|
| _e.g. Example Open Dataset_ | `https://…` | Manual download → `data/raw/` | CC-BY-4.0 | None | Updated annually |
| TAMU Technology Services Website | `https://www.it.tamu.edu/sitemap.xml` | Manual download → `data/raw/` | © 2026 Texas A&M University | None | TBD |
| Texas A&M Student Rules | `https://student-rules.tamu.edu` | WordPress REST API (`/wp-json/wp/v2/pages?per_page=100`, one request for all 81 pages) via `python pipeline/collect/student-rules.py` → `data/raw/student-rules/`, `data/processed/student-rules.jsonl` | TBD (official public TAMU site, no license stated) | None (published policy text; the Campus Contacts page lists staff work emails and phone numbers) | Official source run by the Office of the Vice President for Student Affairs. Changes a few times a year, mostly in August; each page's `modified` date shows when. `robots.txt` sets `Crawl-delay: 10`. The `propose-revision` form page is skipped. |
| Texas A&M Academic Calendar | `https://calendar.tamu.edu/live/rss/events/group/Office%20of%20the%20Registrar/` (tags: `fall%202026`, `spring%202027`, `summer%202027`) | RSS feeds via `python pipeline/collect/registrar.py` → `data/raw/registrar/calendar-*.xml`, `data/processed/registrar.jsonl` | TBD (official public TAMU calendar; no license confirmed) | None (public academic dates and event descriptions) | Covers Fall 2026, Spring 2027, and Summer 2027. The collector downloads the original RSS files with at least one second between requests and groups events into passages of approximately 100–400 words. |
| Texas A&M Registrar Pages | `https://registrar.tamu.edu` (every page in `https://registrar.tamu.edu/sitemap.xml`) | Sitemap, then each page as HTML via `python pipeline/collect/registrar.py` → `data/raw/registrar/pages/`, `data/processed/registrar.jsonl` | TBD (official public TAMU pages; no license confirmed) | None (public policies and general contact information) | The site returns 404 to any non-browser user agent, so these requests send a browser user agent. The PM approved this on Nov 16, 2026, for public pages only (it replaces the four pages saved by hand from Chrome). `robots.txt` returns 404, so the site sets no crawl rules; the collector waits 1 second between requests. Skips the search page, news index pages and news from 2024 and earlier. About 145 pages, 3 minutes. |
| Texas A&M Course Catalog (2026-2027) | `https://catalog.tamu.edu` (sitemap: `https://catalog.tamu.edu/sitemap.xml`) | Sitemap lists every page; the collector fetches each undergraduate and graduate page as plain HTML via `python pipeline/collect/catalog.py` → `data/raw/catalog/`, `data/processed/catalog.jsonl`. Use `--limit N` to test and `--from-raw` to re-parse without fetching. | TBD (official public TAMU catalog; no license stated) | None (published course and program information) | Official CourseLeaf catalog, published once a year (new edition each spring). Course description pages become one passage per course, so most course passages are under 100 words. Degree plans keep their semester grid (one line per semester) and footnotes. Faculty and Board of Regents lists are skipped. `robots.txt` disallows `/archives/`, so only the current edition is collected. About 1,560 pages at 1 request per second, so a full run takes most of an hour; `--from-raw` re-parses in about a minute. Department pages skip their Courses and Faculty tabs, since courses come from the course description pages. |
| anex.us grade distributions | `https://anex.us/grades/` | Unofficial JSON feed the search page loads (`POST https://anex.us/grades/getData/` with `dept` and `number`), one request per course, via `python pipeline/collect/anex.py` → `data/raw/anex/`, `data/processed/anex.jsonl`. The course list comes from the undergraduate course description pages of `https://catalog.tamu.edu`. Use `--limit N` to test, `--resume` to continue a run that stopped, and `--from-raw` to re-parse without fetching. | TBD (unofficial student-built site; no license or terms of use stated; **PM sign-off needed**) | Low (grade counts per section and instructor names; no student information) | Unofficial site, not run by TAMU, and it doesn't say where its data comes from (it matches the Registrar's grade reports). Data from Spring 2015 to the last finished semester; changes about three times a year. Each course gets one summary passage (all semesters, plus a ranking of professors since 2023 with at least 30 graded students) and one passage per professor who taught it since 2023 (set by `RECENT_SINCE_YEAR`), so passages are often under 100 words. 5,230 undergraduate courses (197 catalog subjects) at one request every 2 seconds, so a full run takes about three hours. anex.us stopped answering after about 45 requests at 1 per second, so the collector waits 2 seconds between requests, backs off for up to about 20 minutes when requests fail, and stops after 3 courses in a row fail; `--resume` then continues without re-fetching. Courses with no data return broken JSON (`{"classes":]}`) and are skipped. **The agent fetches grades live** (`get_course_grades`, `get_professor_grades`), one course at a time with a one-day cache, so anex.us data isn't loaded into the database; the collector is for offline runs and its passage format is what the live tools reuse. |
| Texas A&M Transportation Services | `https://transport.tamu.edu` | No sitemap (`sitemap.xml` and `robots.txt` return the site's "Webpage Not Found" page), so `python pipeline/collect/transportation.py` starts at the hub pages (home, parking, transit, events, alternative transportation, fleet, about, football) and follows links on the same site, one request per second → `data/raw/transportation/pages/`, `data/processed/transportation.jsonl`. Use `--from-raw` to re-parse without fetching. | TBD (official public TAMU site, no license stated) | Low (public parking, transit and gameday information; a few contact pages list staff work emails and phone numbers) | Official site of Texas A&M Transportation Services. About 190 pages and 540 passages, about 4 minutes. Static pages only: parking rules and permits, AggieSpirit transit service, gameday, bikes and micromobility, fleet and projects. Live bus times (aggiespirit.ts.tamu.edu) and live garage counts are skipped, since they go out of date within minutes. Also skipped: news archives (`/About/news/`), the job and fleet portals (`/MIS/`, `/MyFleet`), login pages on myparking.tamu.edu, and pages with fewer than 25 words (forms only). Most pages show no last-updated date; break and gameday pages change each term. |

### Registrar collector

Run from the repository root:

```bash
python pipeline/collect/registrar.py
```

The collector reads the Registrar sitemap, downloads each page (about 145, one per second), downloads the three academic calendar RSS feeds, and writes passages to `data/processed/registrar.jsonl`. Each record contains `id`, `source`, `title`, `text`, `source_url`, and `fetched_at`. No manual steps are needed.

Keep all raw and processed data local; the `data/` directory is git-ignored.

## Local layout convention

The `data/` folder is git-ignored, but keep a consistent structure inside it so everyone's local copy matches:

```
data/
├── raw/          # exactly as downloaded — never edit by hand
├── interim/      # partially processed, intermediate outputs
└── processed/    # analysis-ready, produced by the cleaning pipeline
```

Because `data/` isn't in git, the **pipeline that fetches and builds these folders** is what must be committed and reproducible — not the data itself.
