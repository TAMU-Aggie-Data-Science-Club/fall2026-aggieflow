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
   - `GOOGLE_API_KEY`: required for the agent (Gemini). Ask a PM, or use your own billed key.
   - `GROQ_API_KEY`: for the eval judges. Get a free key at [console.groq.com](https://console.groq.com).
   - `MONGODB_URI`: ask a PM for an Atlas database user. Leave it empty to search the local files in `data/processed/` instead (fill them by running the collectors, e.g. `uv run python pipeline/collect/student-rules.py`).
   - `VOYAGE_API_KEY` (optional): reranks hybrid search results with Voyage. Get a free Model API key in Atlas under AI Model APIs.
   - LangSmith (optional): set `LANGSMITH_TRACING=true` and your own `LANGSMITH_API_KEY` to see every run's tool calls.
4. Try it:

```bash
uv run python -m agent.run "when's q drop"   # ask a question
uv run pytest                                # offline tests, no API key needed
uv run python eval/score.py                  # score against eval/questions/
```

To add a package, run `uv add <package>` and commit both `pyproject.toml` and `uv.lock`. More detail in [`ARCHITECTURE.md`](ARCHITECTURE.md).

## Run the API

```bash
uv run uvicorn api.main:app --reload
```

Then open http://localhost:8000/docs to try it in the browser.

| Endpoint | What it does |
|---|---|
| `POST /chat` | Send `{"question": "..."}`. Returns the `answer`, its `sources`, the `tools` the agent called, and `grades` (grade counts by professor for each course it looked up). |
| `POST /chat/stream` | Same body, but streams the answer as an [AI SDK UI message stream](https://ai-sdk.dev/docs/ai-sdk-ui/stream-protocol). This is what the UI uses. |
| `GET /health` | Health check. |

Send the same `thread_id` to continue a conversation. To let a frontend on another address call the API, set `ALLOWED_ORIGINS` in `.env` (comma-separated, default `http://localhost:5173`).

## Run the UI

The chat interface is a Vite + React app in `web/`. It needs Node.js 18 or newer, and the API running.

```bash
cd web && npm install && npm run dev
```

Then open http://localhost:5173. To point it at another API address, copy `web/.env.example` to `web/.env` and set `VITE_API_URL`.

## Run with Docker

One image serves the UI and the API together at the same address, for deploying.

```bash
docker build -t aggieflow .
docker run --env-file .env -p 8000:8000 aggieflow
```

Then open http://localhost:8000. Notes:

- Set `MONGODB_URI`: the image has no local data files.
- Keys are read from the environment and never copied into the image.
- The server listens on `PORT` if the host sets it.
- To keep chats across restarts, set `AGGIEFLOW_CHECKPOINTS=atlas` (needs a database user that can write). Otherwise chats live in memory.

## Tech stack

| Layer | Technology |
|---|---|
| Agent | LangGraph and LangChain, running Gemini 3.5 Flash Lite |
| Search | MongoDB Atlas (free M0 cluster): keyword, vector (Voyage embeddings) and hybrid search, reranked with Voyage |
| Live data | Agent tools that call anex.us (grades) and RateMyProfessors at question time |
| Data collection | Python collectors (`requests`, BeautifulSoup) |
| API | FastAPI |
| Frontend | React + Vite, with the AI SDK (`useChat`) |
| Evaluation | LangSmith, with LLM judges running on Groq |
| Tooling | uv for packages, pytest, GitHub Actions CI |

## Testing

Test-driven development was essential to keeping our agent reliable across iterations and in prod. The repo has 453 pytest tests: 259 offline and 194 live (these call real model APIs and run with `uv run pytest -m live`). The offline tests run on every pull request through GitHub Actions CI.

## Scope and limits

We prioritized the core agent, so some planned features were deferred, the biggest being login (auth). Chats are multi-turn and kept per thread: in memory by default, or in Atlas for a week with `AGGIEFLOW_CHECKPOINTS=atlas`. There's no chat history list in the UI yet.

The main focus of this project was thoroughly evaluating the agent: behavior, tool choice and retrieval. Eval results are in [`eval/RESULTS.md`](eval/RESULTS.md).
