# AggieFlow architecture

How a student's question becomes a cited answer. The tools get passages through `agent/data.py`: from MongoDB Atlas when `MONGODB_URI` is set (Atlas Search for the search tools), otherwise from the collectors' files in `data/processed/`. Grades are fetched live from anex.us.

## The agent

One model, a loop of tool calls, and plain-code checks at the end.

```
question
   │
normalize ── starts the run (question becomes the first message)
   │
 agent ◄──────────────┐   picks tools, reads results, repeats
   │ tool calls?       │   (at most 4 rounds)
   ├─ yes → tools ─────┘   every call from one turn runs at the same time,
   │                       across categories ("is CHEM 107 hard and when's Q-drop")
   │ no
   ▼
 check ── no sources → "I'm not sure"
   │      links no tool returned → removed
   │      adds a Sources list (live data says when it was fetched)
  END
```

These follow patterns from Google Cloud's [agent design patterns guide](https://docs.cloud.google.com/architecture/choose-design-pattern-agentic-ai-system): a **single agent** with a **ReAct** tool loop, **custom logic** for the checks, and tool calls that run in **parallel**. One `tools` node runs every call the model makes in a turn at the same time, so a question that spans categories doesn't wait on each one in turn. The groups below are only how the code is organized (one file each) and how traces label calls; timeouts and caching live in `agent/data.py` and the tool files.

## Tools

Each tool does one job, and every passage is reachable through exactly one tool, so the model never chooses between two tools that overlap. Search tools return the top 5 passages; lookups return only the matching ones.

| Group | Tool | One job | Data |
|---|---|---|---|
| `policy_tools` | `search_student_rules(query)` | University rules: Q-drops, absences, grading, finals, conduct | `student-rules.jsonl` |
| `policy_tools` | `search_registrar(query)` | Registration, academic calendar, deadlines, transcripts, graduation | `registrar.jsonl` |
| `policy_tools` | `search_tech_help(query)` | Wi-Fi, VPN, accounts, software, printing, IT policy | `oal.jsonl` |
| `policy_tools` | `search_degree_plans(query)` | Degree plans, program requirements, core curriculum, catalog policies | `catalog.jsonl` (all pages except individual courses) |
| `course_tools` | `get_course(course)` | One course's title, hours, description, prerequisites | `catalog.jsonl` course pages |
| `course_tools` | `get_course_grades(course)` | A course's grade distribution and professors ranked by GPA | Live: anex.us feed |
| `course_tools` | `get_professor_grades(course, professor)` | One professor's grade history in one course | Live: anex.us feed |

Course tools take a code like `"CSCE 121"`. Search is keyword ranking (BM25) in plain Python for now; Atlas Search and Vector Search replace it inside `agent/data.py`.

Not included yet: Transportation (#36, becomes `search_transportation`), live bus and garage data, RateMyProfessors and Reddit (terms under review), Libraries (mapped, no collector yet). Grades are fetched live from anex.us when a question needs them, not stored: one request at a time, at least a second apart, and each course is cached for a day (grades change about three times a year). The passage text comes from the anex collector's own code, so it matches what the eval answers were written from.

## One format for everything

Every tool returns a list of **passages**, the same format the collectors write to `data/processed/<source>.jsonl` (`id`, `source`, `title`, `text`, `source_url`, `fetched_at`). Live passages end their `id` with `:live`. Because database results and live results look the same, the citation check works the same for both.

## Data flow

```
collectors ─► data/raw/ ─► data/processed/*.jsonl ─► agent/data.py ─► policy and course tools
                                     └─► check.py ─► load.py ─► MongoDB Atlas   (agent/data.py reads here when MONGODB_URI is set)
anex.us feed (live, cached a day) ───────────────► agent/data.py ─► grade tools
```

## Files

| Path | What it is |
|---|---|
| `agent/graph.py` | The graph: nodes, edges, system prompt |
| `agent/tools/` | One file per tool group; `__init__.py` lists the groups |
| `agent/data.py` | Loads passages, keyword search, course and grade lookups |
| `agent/checks.py` | Not-sure and citation checks (no model calls) |
| `agent/state.py` | `Passage` and graph state types |
| `agent/run.py` | `answer(question)` and the command line |
| `tests/test_agent.py` | Offline tests (no API key needed), using sample passages in `tests/fixtures/processed/` |

## Run it

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then add your GROQ_API_KEY
python pipeline/collect/student-rules.py   # and the other collectors, to fill data/processed/
python -m agent.run "when's q drop"
python -m pytest tests
```

The default model is `groq:openai/gpt-oss-20b`. Set `AGGIEFLOW_MODEL` to try another one.

## Adding a tool

1. Give it one job that no other tool covers, and say in its description when *not* to use it.
2. Put the data access in `agent/data.py` and keep the tool a thin wrapper that returns passages.
3. Add it to the right file's `TOOLS` list in `agent/tools/`.
4. Run `python -m pytest tests` and a few real questions.
