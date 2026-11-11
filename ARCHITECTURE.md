# AggieFlow architecture

How a student's question becomes a cited answer. The tools are **placeholders** for now: they return fake text with real-looking links so we can see the agent choose and call them. Real tools get built after the Deliverable 3 collectors land.

## The agent

One model, a loop of tool calls, and plain-code checks at the end.

```
question
   │
normalize ── expands Aggie shorthand (qdrop, msc, wcl)
   │
 agent ◄──────────────────────────────┐   picks tools, reads results, repeats
   │ tool calls?                       │   (at most 4 rounds)
   ├─ yes → policy_tools  ─────────────┤
   │        course_tools  ─────────────┤   groups run at the same time
   │        campus_tools  ─────────────┘   when a question needs more than one
   │ no
   ▼
 check ── no sources → "I'm not sure"
   │      links no tool returned → removed
   │      adds a Sources list (live data says when it was fetched)
  END
```

These follow patterns from Google Cloud's [agent design patterns guide](https://docs.cloud.google.com/architecture/choose-design-pattern-agentic-ai-system): a **single agent** with a **ReAct** tool loop, **custom logic** for the checks, and tool calls that run in **parallel**. Each tool group has its own node, so each group can have its own owner, timeouts, and caching.

## Tool groups

| Group | Tool | Gets data from | Source |
|---|---|---|---|
| `policy_tools` | `search_policies(query, source)` | Our database (pgvector), filled by the collectors | Student Rules, Registrar, Technology Services, Catalog degree plans, Transportation pages |
| `course_tools` | `get_course(code)` | Live: Catalog course-search API | catalog.tamu.edu |
| `course_tools` | `get_grades(dept, number, prof)` | Live: anex JSON feed | anex.us |
| `campus_tools` | `get_bus_routes(place)` | Live: AggieSpirit JSON | aggiespirit.ts.tamu.edu |
| `campus_tools` | `get_garage_counts()` | Live: Transportation homepage | transport.tamu.edu |

Not included yet: RateMyProfessors and Reddit (terms under review), Libraries (not mapped yet).

## One format for everything

Every tool returns a list of **passages**, the same format the collectors write to `data/processed/<source>.jsonl` (`id`, `source`, `title`, `text`, `source_url`, `fetched_at`). Live passages end their `id` with `:live`. Because database results and live results look the same, the citation check works the same for both.

## Data flow

```
collectors ─► data/raw/ ─► data/processed/*.jsonl ─► check.py ─► load.py ─► Postgres + pgvector ─► search_policies
live sites (anex, catalog API, AggieSpirit, garages) ──────────────────────────────────────────► course/campus tools
```

## Files

| Path | What it is |
|---|---|
| `agent/graph.py` | The graph: nodes, edges, system prompt |
| `agent/tools/` | One file per tool group; `__init__.py` lists the groups |
| `agent/checks.py` | Not-sure and citation checks (no model calls) |
| `agent/state.py` | `Passage` and graph state types |
| `agent/run.py` | `answer(question)` and the command line |
| `tests/test_agent.py` | Offline tests (no API key needed) |

## Run it

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then add your GROQ_API_KEY
python -m agent.run "when's q drop"
python -m pytest tests
```

The default model is `groq:openai/gpt-oss-20b`. Set `AGGIEFLOW_MODEL` to try another one.

## Adding a real tool

1. Replace the placeholder in the right `agent/tools/` file. Keep the name, arguments, and passage output.
2. Live tools: add a timeout and set `fetched_at` to the time of the fetch.
3. Run `python -m pytest tests` and a few real questions.
