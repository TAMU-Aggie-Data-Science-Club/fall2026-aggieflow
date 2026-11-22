"""The AggieFlow agent graph: one agent and one tool node.

    question -> normalize -> agent <-> tools
                               \\-> check -> END

The agent loops until it answers or hits MAX_ROUNDS. Every tool call the model
makes in one turn runs at the same time, whatever group the tool belongs to.
"""

import json
import os

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.runnables.config import get_executor_for_config
from langgraph.graph import END, START, StateGraph

from agent.checks import finalize
from agent.state import State
from agent.tools import ALL_TOOLS

DEFAULT_MODEL = "google_genai:gemini-3.5-flash-lite"
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

def normalize(state: State) -> dict:
    """Start a run: the question becomes the first message, with no rounds or
    sources yet. The student's words are passed on unchanged; if evals show
    shorthand (qdrop, wcl) hurting search, expand it inside agent/data.py."""
    return {"messages": [HumanMessage(state["question"])], "rounds": 0, "sources": []}


# 0 so the same question gets the same answer, and eval runs can be compared.
TEMPERATURE = 0


def model_name() -> str:
    return os.environ.get("AGGIEFLOW_MODEL", DEFAULT_MODEL)


def default_model():
    from langchain.chat_models import init_chat_model

    return init_chat_model(model_name(), temperature=TEMPERATURE)


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


def route(state: State) -> str:
    """Run tools if the model asked for any, otherwise finish."""
    return "tools" if getattr(state["messages"][-1], "tool_calls", None) else "check"


def make_tools_node():
    tools = {t.name: t for t in ALL_TOOLS}

    def run_one(call: dict) -> tuple[ToolMessage, list]:
        tool = tools.get(call["name"])
        try:
            if tool is None:
                raise ValueError(f"unknown tool {call['name']!r}")
            passages = tool.invoke(call["args"])
            content = json.dumps(passages, ensure_ascii=False) if passages else "No results."
        except Exception as err:  # report errors to the model instead of crashing
            passages, content = [], f"Error: {err}"
        return ToolMessage(content, tool_call_id=call["id"], name=call["name"]), passages

    def run_tools(state: State, config: RunnableConfig) -> dict:
        """Run every tool call from the model's last message in parallel."""
        calls = state["messages"][-1].tool_calls
        with get_executor_for_config(config) as pool:
            results = list(pool.map(run_one, calls))  # keeps the calls' order
        return {
            "messages": [message for message, _ in results],
            "sources": [p for _, passages in results for p in passages],
        }

    return run_tools


def check(state: State) -> dict:
    text, _ = finalize(state["messages"][-1].text, state.get("sources", []))
    return {"answer": text}


def build_graph(model=None):
    model = model or default_model()
    graph = StateGraph(State)
    graph.add_node("normalize", normalize)
    graph.add_node("agent", make_agent_node(model))
    graph.add_node("tools", make_tools_node())
    graph.add_edge("tools", "agent")
    graph.add_node("check", check)

    graph.add_edge(START, "normalize")
    graph.add_edge("normalize", "agent")
    graph.add_conditional_edges("agent", route, ["tools", "check"])
    graph.add_edge("check", END)
    return graph.compile()
