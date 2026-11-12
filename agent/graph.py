"""The AggieFlow agent graph (Option A: one agent, one node per tool group).

    question -> normalize -> agent -> [policy_tools | course_tools | campus_tools] -> agent ...
                                   \\-> check -> END

The agent loops until it answers or hits MAX_ROUNDS. When it calls tools from
more than one group, those group nodes run in parallel.
"""

import json
import os
import re

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from agent.checks import finalize
from agent.state import GroupInput, State
from agent.tools import ALL_TOOLS, GROUP_OF, GROUPS

DEFAULT_MODEL = "groq:openai/gpt-oss-20b"
MAX_ROUNDS = 4

SYSTEM_PROMPT = """You are AggieFlow, an assistant for Texas A&M students.
Answer only from what your tools return. Never use outside knowledge.
After each fact, put the source_url it came from in parentheses.
Don't write a separate sources list; one is added for you.
If the tools return nothing useful, say you're not sure.
Keep answers short and plain."""

OUT_OF_ROUNDS = (
    "You can't call any more tools. Answer now using only the tool results above, "
    "or say you're not sure."
)

# Aggie shorthand -> the words the sources use (same idea as Deliverable 1).
ALIASES = {
    "qdrop": "Q-drop",
    "q drop": "Q-drop",
    "wcl": "West Campus Library",
    "msc": "Memorial Student Center (MSC)",
    "evans": "Evans Library",
}


def normalize(state: State) -> dict:
    question = state["question"]
    for short, full in ALIASES.items():
        question = re.sub(rf"\b{re.escape(short)}\b", full, question, flags=re.IGNORECASE)
    return {"messages": [HumanMessage(question)], "rounds": 0, "sources": []}


def default_model():
    from langchain.chat_models import init_chat_model

    return init_chat_model(os.environ.get("AGGIEFLOW_MODEL", DEFAULT_MODEL))


def make_agent_node(model):
    with_tools = model.bind_tools(ALL_TOOLS)

    def agent(state: State) -> dict:
        messages = [SystemMessage(SYSTEM_PROMPT), *state["messages"]]
        rounds = state.get("rounds", 0)
        if rounds < MAX_ROUNDS:
            reply = with_tools.invoke(messages)
            return {"messages": [reply], "rounds": rounds + (1 if reply.tool_calls else 0)}

        # Out of rounds: answer with what we have. Some models still try to
        # call a tool here and the API rejects it, so fall back to "not sure".
        messages.append(HumanMessage(OUT_OF_ROUNDS))
        try:
            reply = model.invoke(messages)
        except Exception:
            reply = None
        if reply is None or reply.tool_calls or not reply.text.strip():
            reply = AIMessage("I'm not sure.")
        return {"messages": [reply]}

    return agent


def dispatch(state: State):
    """Send each tool call to its group's node. Groups run in parallel."""
    last = state["messages"][-1]
    if not getattr(last, "tool_calls", None):
        return "check"
    by_group: dict[str, list[dict]] = {}
    for call in last.tool_calls:
        # Unknown tool names go to the first group, which reports the error.
        group = GROUP_OF.get(call["name"], next(iter(GROUPS)))
        by_group.setdefault(group, []).append(call)
    return [Send(group, {"calls": calls}) for group, calls in by_group.items()]


def make_group_node(group: str):
    tools = {t.name: t for t in GROUPS[group]}

    def run_group(payload: GroupInput) -> dict:
        messages, sources = [], []
        for call in payload["calls"]:
            tool = tools.get(call["name"])
            try:
                if tool is None:
                    raise ValueError(f"unknown tool {call['name']!r}")
                passages = tool.invoke(call["args"])
                sources.extend(passages)
                content = json.dumps(passages, ensure_ascii=False) if passages else "No results."
            except Exception as err:  # report errors to the model instead of crashing
                content = f"Error: {err}"
            messages.append(ToolMessage(content, tool_call_id=call["id"], name=call["name"]))
        return {"messages": messages, "sources": sources}

    return run_group


def check(state: State) -> dict:
    text, _ = finalize(state["messages"][-1].text, state.get("sources", []))
    return {"answer": text}


def build_graph(model=None):
    model = model or default_model()
    graph = StateGraph(State)
    graph.add_node("normalize", normalize)
    graph.add_node("agent", make_agent_node(model))
    for group in GROUPS:
        graph.add_node(group, make_group_node(group), input_schema=GroupInput)
        graph.add_edge(group, "agent")
    graph.add_node("check", check)

    graph.add_edge(START, "normalize")
    graph.add_edge("normalize", "agent")
    graph.add_conditional_edges("agent", dispatch, [*GROUPS, "check"])
    graph.add_edge("check", END)
    return graph.compile()
