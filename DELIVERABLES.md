# Deliverables & Timeline

> **How to read this file.** This is the PMs' best current estimate of what the project needs to ship and roughly when. It is a **living plan, not a contract** — deliverables will be added, dropped, split, or resequenced as the team learns more. The authoritative, up-to-the-minute picture always lives in the repo's **GitHub Issues and Project board**; this file is the high-level narrative that keeps everyone oriented.
>
> Week 1 is the week of **Oct 5, 2026**. Timing may shift based on team progress and the club's final presentation date.

## Project goal

Build an assistant that answers Texas A&M students' academic and campus questions from collected sources, with a source link on every answer (see the [`README.md`](README.md)). When no source supports an answer, it should say so instead of guessing. This is a student project, not an official TAMU service.

## Tech stack

| Layer | Technology |
|---|---|
| Data collection | Playwright (scraping source pages) |
| Storage & search | PostgreSQL with pgvector |
| Answer pipeline | RAG orchestrated with LangGraph |
| Backend API | FastAPI |
| Frontend | React |

## Where we are (Week 2)

- **Scoping is done.** The problem and example questions are in the README.
- **Sources are being collected.** The team is drafting candidates in the shared *AggieFlow Source List* sheet: 9 so far (6 official TAMU sites, Anex.us, RateMyProfessors, r/aggies). None are vetted or recorded in [`DATA.md`](DATA.md) yet.
- **No pipeline or model code yet.**

## Milestones at a glance

| # | Deliverable | Description | Owner (role) | Target | Status |
|---|-------------|-------------|--------------|--------|--------|
| 1 | Project scoping | Problem statement, audience, and example questions in the README. | PM | Week 1 | Done |
| 2 | Source list & vetting | Finish the source sheet, check each source's terms and sensitivity, and record adopted sources in [`DATA.md`](DATA.md). | PM + members | Weeks 1–3 | In progress |
| 3 | Evaluation question set | ~50 real student questions, each with the correct answer and source URL. A held-out group is set aside until final evaluation so we don't tune to it. | Members | Weeks 2–3 | Not started |
| 4 | Collection & cleaning pipeline | Reproducible Playwright scripts that fetch adopted sources into `data/raw/` and produce clean text in `data/processed/`, keeping the source URL with every passage for citations. Passages and their embeddings are loaded into PostgreSQL with pgvector. | Members | Weeks 3–4 | Not started |
| 5 | Baseline Q&A | First end-to-end RAG pipeline in LangGraph: retrieve relevant passages from pgvector, generate an answer, cite the source. Exposed through a FastAPI endpoint and scored on the question set to get a number to beat. | Members | Weeks 4–5 | Not started |
| 6 | Iteration & evaluation | Improve on the baseline and re-score after each change; review failures by source and question type. | Members + PM | Weeks 5–7 | Not started |
| 7 | Demo & final report | React interface that calls the FastAPI backend, final results on the held-out questions, and a note on known limitations. | Members + PM | Weeks 6–8 | Not started |
| 8 | Handoff & retro | Setup instructions so a new member can rebuild the data and run the system, final presentation, lessons learned. | PM | Week 8 | Not started |

## Timeline (rough)

```
Week:   1     2     3     4     5     6     7     8
        |-----|-----|-----|-----|-----|-----|-----|
Scope   ██
Sources ████████████
Eval          ████████
Pipeline            ████████████
Baseline                  ████████
Iterate                         ████████████
Demo                                  ████████████
Retro                                              ██
```

## Working agreements

- **Each deliverable maps to one or more GitHub Issues.** The board is the source of truth; this file is the summary.
- **Dates are estimates.** When reality diverges, update the issue and, if the shift is material, this file. Don't let this file quietly go stale.
- **"Done" is defined per issue** via acceptance criteria — not by a date passing.
- **Reprioritize openly.** If a deliverable changes, a PM notes why in the issue so the decision is auditable.
