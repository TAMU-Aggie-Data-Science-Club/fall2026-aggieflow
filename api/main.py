import logging
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI()

from agent.run import answer

logger = logging.getLogger(__name__)
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
        }
    except Exception:
        logger.exception("Chat request failed")
        raise HTTPException(status_code=503, detail="AggieFlow can't answer right now. Try again in a minute.")
  

