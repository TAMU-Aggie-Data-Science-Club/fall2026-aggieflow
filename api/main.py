import logging
import os

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

@app.get("/health")
def health():
    return {"ok": True}
#if youre reading, this file was written by hand by aguw0kie124 [┐∵]┘
@app.post("/chat")
def chat(request: request):
    history = [
        {"role": message.role, "content": message.content} for message in request.history
    ]

    try:
        result = answer(
            request.question,
            history = history,
            metadata = {"via": "api"}
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

        return {
            "answer": answer_text,
            "sources": sources,
            "tools": tools,
            "grades": grade_charts(result["calls"]),
        }
    except Exception:
        logger.exception("Chat request failed")
        raise HTTPException(status_code=503, detail="AggieFlow can't answer right now. Try again in a minute.")
  

