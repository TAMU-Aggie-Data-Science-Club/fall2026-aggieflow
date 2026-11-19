# AggieFlow
 
An AI platform that helps Texas A&M students discover any campus-related information they need, along with planning their academics.

## The problem
 
The answers students need are scattered across various official and unofficial sources: course catalogs, degree plan pages, policy pages, Rate My Professors, forums like Reddit, etc. Finding one specific fact means digging through several sites. AggieFlow brings them together and answers with a source link on every response.
 
## Example questions
 
1. "Best CSCE 120 prof/section?"
2. "Which classes satisfy the KICD requirement?"
3. "What's the easiest Science elective?"
4. "Can I return a calculator checked out at West Campus Library to Evans?"
 
## Setup

1. Install [uv](https://docs.astral.sh/uv/): `brew install uv` or `curl -LsSf https://astral.sh/uv/install.sh | sh`.
2. In the repo, run `uv sync`. This installs Python 3.14 and the exact package versions in `uv.lock` into `.venv/`. No `pip install` needed.
3. Run `cp .env.example .env` and fill it in:
   - `GROQ_API_KEY`: required. Get a free key at [console.groq.com](https://console.groq.com).
   - `MONGODB_URI`: ask a PM for an Atlas database user. Leave it empty to search the local files in `data/processed/` instead (fill them by running the collectors, e.g. `uv run python pipeline/collect/student-rules.py`).
   - LangSmith (optional): set `LANGSMITH_TRACING=true` and your own `LANGSMITH_API_KEY` to see every run's tool calls.
4. Try it:

```bash
uv run python -m agent.run "when's q drop"   # ask a question
uv run pytest                                # offline tests, no API key needed
uv run python eval/score.py                  # score against eval/questions/
```

To add a package, run `uv add <package>` and commit both `pyproject.toml` and `uv.lock`. More detail in [`ARCHITECTURE.md`](ARCHITECTURE.md).

## Repo guide
 
See [`CONTRIBUTING.md`](CONTRIBUTING.md) for how we work, [`DELIVERABLES.md`](DELIVERABLES.md) for the timeline, [`DATA.md`](DATA.md) for data sources, and [`CODEOWNERS`](CODEOWNERS) for the team.

## Team

The current PMs and members for this project are listed in [`CODEOWNERS`](CODEOWNERS). PMs listed there are the code owners for PRs into `main`.
