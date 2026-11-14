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
| Texas A&M Student Rules | `https://student-rules.tamu.edu` | WordPress REST API (`/wp-json/wp/v2/pages?per_page=100`, one request for all 81 pages) via `python pipeline/collect/student-rules.py` → `data/raw/student-rules/`, `data/processed/student-rules.jsonl` | TBD (official public TAMU site, no license stated) | None (published policy text; the Campus Contacts page lists staff work emails and phone numbers) | Official source run by the Office of the Vice President for Student Affairs. Changes a few times a year, mostly in August; each page's `modified` date shows when. `robots.txt` sets `Crawl-delay: 10`. The `propose-revision` form page is skipped. |
| Texas A&M Academic Calendar | `https://calendar.tamu.edu/live/rss/events/group/Office%20of%20the%20Registrar/` (tags: `fall%202026`, `spring%202027`, `summer%202027`) | RSS feeds via `python pipeline/collect/registrar.py` → `data/raw/registrar/calendar-*.xml`, `data/processed/registrar.jsonl` | TBD (official public TAMU calendar; no license confirmed) | None (public academic dates and event descriptions) | Covers Fall 2026, Spring 2027, and Summer 2027. The collector downloads the original RSS files with at least one second between requests and groups events into passages of approximately 100–400 words. |
| Texas A&M Registrar Pages | `https://registrar.tamu.edu` (Q-Drops, Graduation FAQs, Grading, Registration & Scheduling) | Save pages in Chrome as HTML Only → `data/raw/registrar/`; process with `python pipeline/collect/registrar.py` → `data/processed/registrar.jsonl` | TBD (official public TAMU pages; no license confirmed) | None (public policies and general contact information) | Direct Python requests to the Registrar HTML pages returned 404/S3 errors, although the pages loaded in Chrome. PM approved manually saving four public HTML pages. The collector reads these snapshots locally; they must be refreshed manually when the source changes. |

### Registrar collector

Run from the repository root:

```bash
python pipeline/collect/registrar.py
```

Before running, save these four public Registrar pages from Chrome using **Save Page As → Webpage, HTML Only**, with the following filenames in `data/raw/registrar/`:

- `grading.html` — https://registrar.tamu.edu/academic-services/grading/index.html
- `graduation-faqs.html` — https://registrar.tamu.edu/graduation/faqs/index.html
- `q-drops.html` — https://registrar.tamu.edu/academic-services/records-administration-archives/q-drops.html
- `registration.html` — https://registrar.tamu.edu/registration-scheduling-and-analytics/index.html

The collector downloads the three academic calendar RSS feeds automatically, processes the saved HTML pages, and writes passages to `data/processed/registrar.jsonl`. Each record contains `id`, `source`, `title`, `text`, `source_url`, and `fetched_at`.

The HTML files are manually captured snapshots, so `fetched_at` reflects processing time rather than the original Chrome download time. The collector checks that all four HTML files exist and validates the output format. Keep all raw and processed data local; the `data/` directory is git-ignored.

## Local layout convention

The `data/` folder is git-ignored, but keep a consistent structure inside it so everyone's local copy matches:

```
data/
├── raw/          # exactly as downloaded — never edit by hand
├── interim/      # partially processed, intermediate outputs
└── processed/    # analysis-ready, produced by the cleaning pipeline
```

Because `data/` isn't in git, the **pipeline that fetches and builds these folders** is what must be committed and reproducible — not the data itself.
