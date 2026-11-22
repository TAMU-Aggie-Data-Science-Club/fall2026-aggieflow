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
| Live data | Agent tools that call anex.us (grades) and RateMyProfessors (ratings) at question time |
| Answer pipeline | LangGraph agent on Gemini 3.5 Flash Lite: searches Atlas (hybrid by default) and calls the live tools, with a citation on every answer. Follow-up questions use the earlier turns. |
| Backend API | FastAPI (`POST /chat`) |
| Frontend | React (in progress) |
| Evaluation | LangSmith, with LLM judges on Groq's free tier |

**Why Atlas instead of PostgreSQL + pgvector (changed Nov 16).** The database only needs to hold the document sources (Student Rules, Registrar, Technology Services, Libraries). Most course, grade, and bus data will be fetched live by tools. Atlas is hosted from day one, so nobody has to run Docker. The passages store as documents as they are, and keyword search and vector search work on the same collection. The free tier fits our data and outlasts the semester, so the next team doesn't inherit a bill. PMs and the core team set up and manage the cluster. Members get a database user and a connection string in `.env`.

## Where we are (end of Week 7)

- **The data pipeline is done.** Six collectors are merged: Student Rules, Registrar (pages and the academic calendar), Technology Services, Course Catalog, anex.us and Transportation. Five of them load into MongoDB Atlas, which supports keyword, vector and hybrid search. anex.us grades and RateMyProfessors ratings are fetched live instead. Libraries and r/aggies weren't collected.
- **The agent answers end to end.** It's a LangGraph agent with real tools for every source, on Gemini 3.5 Flash Lite. Gemini replaced Groq's gpt-oss models, which were too slow and ran out of free tokens. It handles follow-up questions (#99) and is served over FastAPI (#103).
- **The agent has been evaluated** ([`eval/RESULTS.md`](eval/RESULTS.md)).
  - **Questions and tools:** 130 eval questions, a full-loop runner in LangSmith, LLM judges, and routing tests.
  - **Score:** on a 40-question sample that covers every source and question type, the agent passes **95% (38 of 40, 95% CI 88–100%)** and gives the same result on all 3 repeats. A typical answer takes about 1.3 seconds.
  - **Search mode:** hybrid search is the default (#76). All three modes tied on pass rate, and hybrid held up best on poorly worded queries.
- **Still open:**
  - The React chat interface (#104).
  - RateMyProfessors questions and a pre-demo check (#96, #98, #83).
  - Multi-turn eval questions (#100).
  - Groundedness and retrieval judges (#101, results in review).
  - The failure review (#74).
- **One week left.** Week 8 includes Thanksgiving (Nov 26), so we're aiming to wrap up by about Nov 29.

## Milestones at a glance

| # | Deliverable | Description | Owner (role) | Target | Status |
|---|-------------|-------------|--------------|--------|--------|
| 1 | Project scoping | Problem statement, audience, and example questions in the README. | PM | Week 1 | Done |
| 2 | Source list & vetting | Finish the source sheet, check each source's terms and sensitivity, and record adopted sources in [`DATA.md`](DATA.md). | PM + members | Weeks 1–7 | Done (7 sources in use: 6 collected and RateMyProfessors fetched live; Libraries and r/aggies not used). RateMyProfessors still needs a row in [`DATA.md`](DATA.md). |
| 3 | Evaluation question set | ~50 real student questions, each with the correct answer and source URL, including some the sources can't answer. A held-out group is set aside until final evaluation so we don't tune to it. Folded into Deliverable 3, since the source reports already drafted most questions. Extended into Week 7 because only 4 of the question files came in by Nov 15. | Members | Weeks 5–7 | Done (130 questions; no held-out group was set aside, so results use a 40-question sample of all files) |
| 4 | Collection & cleaning pipeline | Reproducible collector scripts that fetch adopted sources into `data/raw/` and produce clean passages in `data/processed/`, keeping the source URL with every passage for citations. The loader puts passages and their embeddings into MongoDB Atlas. Atlas replaced PostgreSQL + pgvector on Nov 16 (see Tech stack). Extended into Week 7 because the database, loader, and three collectors were unclaimed at the Deliverable 3 due date. | Core team + members | Weeks 5–7 | Done (6 collectors, the checker and the loader; Atlas with keyword, vector and hybrid search) |
| 5 | Baseline Q&A | First end-to-end pipeline in LangGraph: search passages in Atlas or call a live tool, generate an answer, and cite the source. Exposed through a FastAPI endpoint and scored on the question set to get a number to beat. The agent skeleton is merged; its tools need to be connected to Atlas and the live sources. Moved to Week 7 because it depends on the database and loader. | Core team | Week 7 | Done (first full run 58%, on gpt-oss-120b; FastAPI `/chat` merged) |
| 6 | Iteration & evaluation | Improve on the baseline and re-score after each change; review failures by source and question type. Shortened to Week 8 to keep the end date. | Members + PM | Week 8 | In progress (95% on the 40-question sample after the model switch, routing and citation fixes, and the search-mode comparison; #74, #96, #100 and #101 open) |
| 7 | Demo & final report | React interface that calls the FastAPI backend, final results on the held-out questions, and a note on known limitations. | Members + PM | Weeks 7–8 | In progress (results in [`eval/RESULTS.md`](eval/RESULTS.md); React interface #104 open) |
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
