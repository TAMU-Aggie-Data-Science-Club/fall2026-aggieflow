import json
import logging
import os
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

app = FastAPI()

from agent import data
from agent.run import answer, answer_stream

logger = logging.getLogger(__name__)
# Only course lookups: get_professor_grades answers with all-time numbers, the chart is since 2023.
GRADE_TOOLS = {"get_course_grades"}


def grade_charts(calls: list[dict]) -> list[dict]:
    """One grade chart (data.grade_chart) per course the agent looked up on anex.us, in
    the order it looked them up. The tool already fetched and cached the course, so this
    makes no new request. A chart that can't be built is skipped: it never fails the answer."""
    charts, seen = [], set()
    for call in calls:
        course = call["args"].get("course") if call["name"] in GRADE_TOOLS and not call.get("error") else None
        if not isinstance(course, str):
            continue
        try:
            key = data.parse_course(course)
            if key in seen:
                continue
            seen.add(key)
            chart = data.grade_chart(course)
        except Exception:
            logger.warning("No grade chart for %r", course, exc_info=True)
            continue
        if chart:
            charts.append(chart)
    return charts
#cosr
origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

#pydantic models
class message(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str

#hard 20 message limit for demo, will probably improve later on with summarization or compacting
class request(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    history: list[message] = Field(default = [], max_length=20)
    #the conversation to continue; leave it out to start one (the reply has its id)
    thread_id: uuid.UUID | None = None

@app.get("/health")
def health():
    return {"ok": True}
#if youre reading, this file was written by hand by aguw0kie124 [┐∵]┘
UNAVAILABLE = "AggieFlow can't answer right now. Try again in a minute."


def reply(result: dict, thread_id: str) -> dict:
    """The JSON both /chat and /chat/stream send for one answer."""
    answer_text = result["answer"].split("\nSources:")[0].strip()

    sources = []
    seen = set()

    for source in result["sources"]:
        url = source["source_url"]

        if url not in seen:
            seen.add(url)
            sources.append({
                "title": source["title"],
                "source_url": url,
                "source": source["source"],
            })

    tools = list(dict.fromkeys([call["name"] for call in result["calls"]]))

    #every lookup in order, for the UI's tool steps (ask_user is shown as the question instead)
    steps = [
        {"name": call["name"], "args": call["args"], "error": call["error"]}
        for call in result["calls"]
        if call["name"] != "ask_user"
    ]

    return {
        "answer": answer_text,
        "sources": sources,
        "tools": tools,
        "steps": steps,
        "grades": grade_charts(result["calls"]),
        "thread_id": thread_id,
        #set when the agent asks which one the student means: {prompt, options}; reply with the same thread_id
        "question": result.get("question"),
    }


def turn(request: request) -> tuple[str, dict]:
    """The question's keyword arguments for answer() / answer_stream(), and its thread id."""
    history = [
        {"role": message.role, "content": message.content} for message in request.history
    ]
    thread_id = str(request.thread_id or uuid.uuid4())
    return thread_id, {"history": history, "metadata": {"via": "api"}, "thread_id": thread_id}


@app.post("/chat")
def chat(request: request):
    thread_id, kwargs = turn(request)
    try:
        return reply(answer(request.question, **kwargs), thread_id)
    except Exception:
        logger.exception("Chat request failed")
        raise HTTPException(status_code=503, detail=UNAVAILABLE)


def sse(event: str, data: dict) -> str:
    """One Server-Sent Event."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.post("/chat/stream")
def chat_stream(request: request):
    """/chat as Server-Sent Events (#142), so the UI can show each lookup while the agent
    works: one `step` event per tool call as it starts ({name, args}), then `done` with
    exactly the JSON /chat returns, or `error` ({detail}) if the agent fails."""
    thread_id, kwargs = turn(request)

    def events():
        try:
            for kind, value in answer_stream(request.question, **kwargs):
                yield sse("step", value) if kind == "step" else sse("done", reply(value, thread_id))
        except Exception:
            logger.exception("Chat stream failed")
            yield sse("error", {"detail": UNAVAILABLE})

    # no-cache and X-Accel-Buffering: no, so proxies pass each event on as it comes
    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# The built UI (cd web && npm run build), served at / when it exists, as in the Docker
# image. WEB_DIST picks another folder. Keep this at the end of the file: a mount at /
# catches every path, so routes added after it would never be reached.
WEB_DIST = Path(os.getenv("WEB_DIST", Path(__file__).resolve().parent.parent / "web" / "dist"))
if (WEB_DIST / "index.html").is_file():
    app.mount("/", StaticFiles(directory=WEB_DIST, html=True), name="web")
