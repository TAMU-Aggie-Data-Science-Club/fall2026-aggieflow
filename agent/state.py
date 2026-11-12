"""Shared types for the AggieFlow agent."""

import operator
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


class State(TypedDict, total=False):
    question: str
    messages: Annotated[list[AnyMessage], add_messages]
    # Every passage any tool returned. Tool groups can run in parallel,
    # so this list is merged with + instead of overwritten.
    sources: Annotated[list[Passage], operator.add]
    rounds: int  # how many times the agent has asked for tools
    answer: str


class GroupInput(TypedDict):
    """What the dispatcher sends to one tool-group node."""

    calls: list[dict]
