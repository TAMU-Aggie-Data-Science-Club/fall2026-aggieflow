"""Shared types for the AggieFlow agent."""

from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph import add_messages


class Passage(TypedDict):
    """One piece of evidence. Same format as data/processed/*.jsonl (Deliverable 3).

    Every tool returns a list of these, whether the data comes from the
    database or from a live fetch. Live passages end their id with ":live".
    """

    id: str
    source: str
    title: str
    text: str
    source_url: str
    fetched_at: str


def add_sources(old: list[Passage] | None, new: list[Passage] | None) -> list[Passage]:
    """Merge passages with +, so every round's are kept. None clears them: a new turn
    starts with none, even when a checkpointer keeps the previous turn's state."""
    return [] if new is None else (old or []) + new


class State(TypedDict, total=False):
    question: str
    # Earlier turns, oldest first: [{"role": "user" | "assistant", "content": str}].
    # Starts a conversation; once a thread has messages, the checkpointer keeps them instead.
    history: list[dict]
    messages: Annotated[list[AnyMessage], add_messages]
    # Every passage any tool returned this turn, across all rounds.
    sources: Annotated[list[Passage], add_sources]
    rounds: int  # how many times the agent has asked for tools
    answer: str
    cited: list[Passage]  # the passages the answer cites

