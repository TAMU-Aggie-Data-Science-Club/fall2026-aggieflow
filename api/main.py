import logging
import os
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI()

from agent import data
from agent.run import answer

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

#a thumbs up (1) or down (0) on one answer, by the run_id /chat returned with it
class feedback(BaseModel):
    run_id: uuid.UUID
    score: int = Field(ge=0, le=1)

#the feedback key in LangSmith, next to the answer's run
FEEDBACK_KEY = "user_score"


def feedback_enabled() -> bool:
    """Answers only reach LangSmith when tracing is on, so feedback needs the same settings."""
    return bool(os.getenv("LANGSMITH_API_KEY")) and os.getenv("LANGSMITH_TRACING", "").lower() == "true"


def send_feedback(run_id: str, score: int) -> None:
    from langsmith import Client

    #the answer is the root run of its trace, so both ids are the same
    Client().create_feedback(run_id=run_id, trace_id=run_id, key=FEEDBACK_KEY, score=score)

@app.get("/health")
def health():
    return {"ok": True}
#if youre reading, this file was written by hand by aguw0kie124 [┐∵]┘
@app.post("/chat")
def chat(request: request):
    history = [
        {"role": message.role, "content": message.content} for message in request.history
    ]

    thread_id = str(request.thread_id or uuid.uuid4())

    try:
        result = answer(
            request.question,
            history = history,
            metadata = {"via": "api"},
            thread_id = thread_id,
        )

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
            #send it back to /feedback with a thumbs up or down on this answer
            "run_id": result.get("run_id"),
            #set when the agent asks which one the student means: {prompt, options}; reply with the same thread_id
            "question": result.get("question"),
        }
    except Exception:
        logger.exception("Chat request failed")
        raise HTTPException(status_code=503, detail="AggieFlow can't answer right now. Try again in a minute.")


@app.post("/feedback")
def rate(feedback: feedback):
    if not feedback_enabled():
        raise HTTPException(status_code=503, detail="Feedback isn't turned on for this server.")
    try:
        send_feedback(str(feedback.run_id), feedback.score)
    except Exception:
        logger.exception("Feedback failed")
        raise HTTPException(status_code=503, detail="Couldn't send your feedback. Try again in a minute.")
    return {"ok": True}
