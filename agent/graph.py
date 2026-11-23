"""The AggieFlow agent graph: one agent and one tool node.

    question (+ history) -> normalize -> agent <-> tools
                               \\-> check -> END

Compiled with a checkpointer, a thread keeps its conversation between calls:
normalize trims it to earlier questions and final answers before each turn.

The agent loops until it answers or hits MAX_ROUNDS. Every tool call the model
makes in one turn runs at the same time, whatever group the tool belongs to.
"""

import json
import os

from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.runnables.config import get_executor_for_config
from langgraph.graph import END, START, StateGraph

from agent.checks import finalize, tools_called
from agent.state import State
from agent.tools import ALL_TOOLS

DEFAULT_MODEL = "google_genai:gemini-3.5-flash-lite"
MAX_ROUNDS = 4
MAX_HISTORY = 10  # earlier messages kept (5 turns); older ones are dropped

SYSTEM_PROMPT = """You are AggieFlow, an assistant for Texas A&M students.
Answer only from what your tools return. Never use outside knowledge.
After each fact, put the full source_url it came from in parentheses,
like (https://student-rules.tamu.edu/rule01/). Copy the source_url exactly;
never cite a website name like (anex.us) or a passage id instead.
Don't write a separate sources list; one is added for you.
If the tools return nothing useful, say you're not sure.
Greetings, thanks and "what can you do" need no tools. Anything else you can't
look up, including requests to write or do something for the student, gets "not sure".
Earlier messages are the conversation so far. Use them to understand
follow-ups like "what about summer?", but look facts up again with your tools.
If several things match and the conversation doesn't say which one
(for example, two professors named Kim), ask one short question instead of guessing.
For choosing or judging a professor, use both grades (anex.us) and ratings
(RateMyProfessors). Questions only about grades (grade distribution, average GPA,
percent A's, Q-drops) need grades only. Give both sides when they disagree, and say ratings
are what students say. For "easiest", rank by GPA.
When describing a professor's ratings, start with the overall verdict from the
rating and the percent who would take them again (like "students mostly rate him
below average"), then what the reviews say.
Name the professor whose grades or ratings you give at least once, by full name,
not only "he" or "she".
Keep answers short and plain."""

OUT_OF_ROUNDS = (
    "You can't call any more tools. Answer now using only the tool results above, "
    "or say you're not sure."
)

def history_messages(history: list[dict]) -> list:
    """Earlier turns as chat messages: only the question and answer text, without
    tool calls or the "Sources:" list, so follow-ups stay short."""
    messages = []
    for turn in history[-MAX_HISTORY:]:
        if turn["role"] == "user":
            messages.append(HumanMessage(turn["content"]))
        elif turn["role"] == "assistant":
            messages.append(AIMessage(turn["content"].split("\n\nSources:\n")[0]))
        else:
            raise ValueError(f"history role must be 'user' or 'assistant', not {turn['role']!r}")
    return messages


def finished_turns(messages: list) -> list:
    """Each earlier question with its final answer, oldest first. Tool calls, tool
    results and a turn that never got an answer (it failed partway) are left out."""
    kept, question = [], None
    for m in messages:
        if isinstance(m, HumanMessage):
            question = m
        elif isinstance(m, AIMessage) and not m.tool_calls and question is not None:
            kept += [question, m]
            question = None
    return kept


def normalize(state: State) -> dict:
    """Start a turn: earlier turns, then the question, with no rounds or sources
    yet, so an answer cites only what was found for it. A thread's earlier turns
    come from the checkpointer, trimmed to questions and answers (the last
    MAX_HISTORY messages); a new conversation can start from `history` instead.
    The student's words are passed on unchanged; if evals show shorthand
    (qdrop, wcl) hurting search, expand it inside agent/data.py."""
    old = state.get("messages") or []
    keep = {m.id for m in finished_turns(old)[-MAX_HISTORY:]}
    earlier = [RemoveMessage(id=m.id) for m in old if m.id not in keep]
    if not old:
        earlier = history_messages(state.get("history") or [])
    return {"messages": [*earlier, HumanMessage(state["question"])], "rounds": 0, "sources": None}


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
    """The final answer and the passages it cites. The model's reply is replaced by the
    answer as the student sees it (without the Sources list), so a thread's later turns
    read what was shown, not links that were removed."""
    reply = state["messages"][-1]
    text, cited = finalize(reply.text, state.get("sources", []), tools_called(state["messages"]))
    shown = AIMessage(text.split("\n\nSources:\n")[0], id=reply.id)
    return {"answer": text, "cited": cited, "messages": [shown]}


def build_graph(model=None, checkpointer=None):
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
    return graph.compile(checkpointer=checkpointer)
