# Deliverables & Timeline

> **How to read this file.** This is the PMs' best current estimate of what the project needs to ship and roughly when. It is a **living plan, not a contract** — deliverables will be added, dropped, split, or resequenced as the team learns more. The authoritative, up-to-the-minute picture always lives in the repo's **GitHub Issues and Project board**; this file is the high-level narrative that keeps everyone oriented.
>
> Week 1 is the week of **Oct 5, 2026**. Timing may shift based on team progress and the club's final presentation date.

## Project goal

Build an assistant that answers Texas A&M students' academic and campus questions from collected sources, with a source link on every answer (see the [`README.md`](README.md)). When no source supports an answer, it should say so instead of guessing. This is a student project, not an official TAMU service.

## Tech stack

| Layer | Technology |
|---|---|
| Data collection | Collector scripts (`requests` + BeautifulSoup, Playwright only for JavaScript-only pages) |
| Storage & search | MongoDB Atlas (free M0 cluster) with Atlas Search and Atlas Vector Search, for the policy and document sources |
| Live data | Agent tools that call source APIs at question time (course catalog, grades, bus routes) |
| Answer pipeline | LangGraph agent: retrieval from Atlas plus live tools, with a citation on every answer |
| Backend API | FastAPI |
| Frontend | React |

**Why Atlas instead of PostgreSQL + pgvector (changed Nov 16).** The database only needs to hold the document sources (Student Rules, Registrar, Technology Services, Libraries). Most course, grade, and bus data will be fetched live by tools. Atlas is hosted from day one, so nobody has to run Docker. The passages store as documents as they are, and keyword search and vector search work on the same collection. The free tier fits our data and outlasts the semester, so the next team doesn't inherit a bill. PMs and the core team set up and manage the cluster. Members get a database user and a connection string in `.env`.

## Where we are (Week 7)

- **Scoping is done.** The problem and example questions are in the README.
- **All 9 sources are mapped.** [Deliverable 2](deliverable2/README.md) has reports for Course Catalog, Registrar, Student Rules, Technology Services, Transportation, Anex.us, Libraries, RateMyProfessors, and r/aggies. Reddit and RateMyProfessors are still **on hold** while PMs review their terms of use.
- **Deliverable 3 is partly in.** [Deliverable 3](deliverable3/README.md) was due Nov 15.
  - **Merged:** collectors for Student Rules, Registrar, and Technology Services; the format checker and the eval scorer; and 42 evaluation questions.
  - **Still open, with no owner:** collectors for Course Catalog (#32), anex.us (#31), and Transportation (#36); the database (#37) and the loader (#38).
- **The agent skeleton is merged.** It has a router and three tool groups (policy, courses, campus), but the tools still return placeholder text until the database and loader land.
- **Two weeks left.** Week 8 includes Thanksgiving (Nov 26), so we're aiming to wrap up by about Nov 29.

## Milestones at a glance

| # | Deliverable | Description | Owner (role) | Target | Status |
|---|-------------|-------------|--------------|--------|--------|
| 1 | Project scoping | Problem statement, audience, and example questions in the README. | PM | Week 1 | Done |
| 2 | Source list & vetting | Finish the source sheet, check each source's terms and sensitivity, and record adopted sources in [`DATA.md`](DATA.md). | PM + members | Weeks 1–7 | In progress (all 9 sources mapped; Reddit and RateMyProfessors on hold; 4 sources recorded in [`DATA.md`](DATA.md)) |
| 3 | Evaluation question set | ~50 real student questions, each with the correct answer and source URL, including some the sources can't answer. A held-out group is set aside until final evaluation so we don't tune to it. Folded into Deliverable 3, since the source reports already drafted most questions. Extended into Week 7 because only 4 of the question files came in by Nov 15. | Members | Weeks 5–7 | In progress (42 merged) |
| 4 | Collection & cleaning pipeline | Reproducible collector scripts that fetch adopted sources into `data/raw/` and produce clean passages in `data/processed/`, keeping the source URL with every passage for citations. The loader puts passages and their embeddings into MongoDB Atlas. Atlas replaced PostgreSQL + pgvector on Nov 16 (see Tech stack). Extended into Week 7 because the database, loader, and three collectors were unclaimed at the Deliverable 3 due date. | Core team + members | Weeks 5–7 | In progress (3 of 6 collectors, checker, and scorer merged) |
| 5 | Baseline Q&A | First end-to-end pipeline in LangGraph: search passages in Atlas or call a live tool, generate an answer, and cite the source. Exposed through a FastAPI endpoint and scored on the question set to get a number to beat. The agent skeleton is merged; its tools need to be connected to Atlas and the live sources. Moved to Week 7 because it depends on the database and loader. | Core team | Week 7 | In progress (skeleton merged) |
| 6 | Iteration & evaluation | Improve on the baseline and re-score after each change; review failures by source and question type. Shortened to Week 8 to keep the end date. | Members + PM | Week 8 | Not started |
| 7 | Demo & final report | React interface that calls the FastAPI backend, final results on the held-out questions, and a note on known limitations. | Members + PM | Weeks 7–8 | Not started |
| 8 | Handoff & retro | Setup instructions so a new member can rebuild the data and run the system, final presentation, lessons learned. | PM | Week 8 | Not started |

## Timeline (rough)

```
Week:   1     2     3     4     5     6     7     8
        |-----|-----|-----|-----|-----|-----|-----|
Scope   ██
Sources ██████████████████████████████████████████
Eval                            ██████████████████
Pipeline                        ██████████████████
Baseline                                    ██████
Iterate                                           ██████
Demo                                        ████████████
Retro                                             ██████
```

Week 7 starts Nov 16 and Week 8 starts Nov 23. Thanksgiving (Nov 26) falls in Week 8.

## Working agreements

- **Each deliverable maps to one or more GitHub Issues.** The board is the source of truth; this file is the summary.
- **Dates are estimates.** When reality diverges, update the issue and, if the shift is material, this file. Don't let this file quietly go stale.
- **"Done" is defined per issue** via acceptance criteria — not by a date passing.
- **Reprioritize openly.** If a deliverable changes, a PM notes why in the issue so the decision is auditable.
