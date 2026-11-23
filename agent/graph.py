"""The AggieFlow agent graph: one agent and one tool node.

    question (+ history) -> normalize -> agent <-> tools
                                         <-> ask    (ask_user: the student picks an option)
                                          \\-> check -> END

Compiled with a checkpointer, a thread keeps its conversation between calls:
normalize trims it to earlier questions and final answers before each turn, and
ask pauses the turn (interrupt) until the student answers. Without one, ask ends
the turn with the question as the answer.

The agent loops until it answers or hits MAX_ROUNDS. Every tool call the model
makes in one turn runs at the same time, whatever group the tool belongs to.
"""

import json
import os

from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.runnables.config import get_executor_for_config
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from pydantic import BaseModel, Field

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
When the answer depends on something the student didn't say and you can't
briefly cover every case, call ask_user instead of guessing: two professors named
Kim, "the minor" without saying which, a rule that differs for undergrad and grad
students when the answer would be long. Look things up first when that shows the
choices. If a short answer can cover every case (each semester's deadline, on- and
off-campus parking), give it and don't ask. Never ask when the question already
names the course, minor or full name, or when only one option exists: answer for it.
For choosing or judging a professor, use both grades (anex.us) and ratings
(RateMyProfessors). Questions only about grades (grade distribution, average GPA,
percent A's, Q-drops) need grades only. Give both sides when they disagree, and say ratings
are what students say. For "easiest", rank by GPA.
When describing a professor's ratings, start with the overall verdict from the
rating and the percent who would take them again (like "students mostly rate him
below average"), then what the reviews say.
Name the professor whose grades or ratings you give at least once, by full name,
not only "he" or "she".
Keep answers short and plain, but never leave out a case, condition or exception
the page gives: both undergraduate and graduate rules, who can get something and for
how long, which lots or times are exceptions, who to contact for extra time or help (like
temporary access for up to two years).
If a rule covers the student's situation (a refund "before the census date" covers
the first week), answer from it instead of saying you're not sure."""

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
    return {"messages": [*earlier, HumanMessage(state["question"])], "rounds": 0, "sources": None,
            "asked": None}


class ask_user(BaseModel):
    """Ask the student one short question when the answer depends on something they
    didn't say and the cases can't all be covered briefly: which of several professors
    with the same name, which minor, undergrad or grad rules. Don't ask when a short
    answer covers every case. The student picks an option or types a reply."""

    prompt: str = Field(description="The question, like 'Which Professor Leyk?' or 'Which minor?'")
    options: list[str] = Field(default_factory=list,
                               description="2 to 6 short choices, like 'Teresa Leyk (Computer Science)'. "
                               "Leave empty for an open question like 'Which minor?'")


ASK = "ask_user"
MAX_OPTIONS = 6
NOT_ASKED = "Not asked: ask_user can't run with other tools. Use their results first."
ONE_OPTION = "Not asked: there is only one option ({}). Answer for it without asking."


def question_of(call: dict) -> dict:
    """The question an ask_user call asks: {"prompt", "options"}."""
    args = call.get("args") or {}
    options = [str(o).strip() for o in args.get("options") or [] if str(o).strip()]
    return {"prompt": str(args.get("prompt") or "Which one do you mean?").strip(),
            "options": list(dict.fromkeys(options))[:MAX_OPTIONS]}


def single_option(call: dict) -> bool:
    """An ask_user call with exactly one option: nothing to choose, so it isn't asked."""
    return call["name"] == ASK and len(question_of(call)["options"]) == 1


def question_text(question: dict) -> str:
    """The question as plain text, for callers that can't show buttons."""
    return "\n".join([question["prompt"], *(f"- {o}" for o in question["options"])])


# 0 so the same question gets the same answer, and eval runs can be compared.
TEMPERATURE = 0


def model_name() -> str:
    return os.environ.get("AGGIEFLOW_MODEL", DEFAULT_MODEL)


def default_model():
    from langchain.chat_models import init_chat_model

    return init_chat_model(model_name(), temperature=TEMPERATURE)


def make_agent_node(model):
    with_tools = model.bind_tools([*ALL_TOOLS, ask_user])

    def agent(state: State) -> dict:
        messages = [SystemMessage(SYSTEM_PROMPT), *state["messages"]]
        rounds = state.get("rounds", 0)
        if rounds < MAX_ROUNDS:
            reply = with_tools.invoke(messages)
            looked_up = any(c["name"] != ASK or single_option(c) for c in reply.tool_calls)  # asking isn't a round
            return {"messages": [reply], "rounds": rounds + looked_up}

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
    """Run tools if the model asked for any, ask the student if it only called ask_user,
    otherwise finish."""
    calls = getattr(state["messages"][-1], "tool_calls", None)
    if not calls:
        return "check"
    return "ask" if all(c["name"] == ASK and not single_option(c) for c in calls) else "tools"


def make_tools_node():
    tools = {t.name: t for t in ALL_TOOLS}

    def run_one(call: dict) -> tuple[ToolMessage, list]:
        if call["name"] == ASK:  # with other tools, or one option: the question isn't asked
            note = ONE_OPTION.format(question_of(call)["options"][0]) if single_option(call) else NOT_ASKED
            return ToolMessage(note, tool_call_id=call["id"], name=ASK), []
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


def make_ask_node(pause: bool):
    def ask(state: State) -> dict:
        """Ask the first ask_user call's question. pause (a checkpointer): wait for the
        student's reply, then let the agent go on with it. Otherwise end the turn with
        the question as the answer."""
        calls = state["messages"][-1].tool_calls
        question = question_of(calls[0])
        if not pause:
            text = question_text(question)
            return {"messages": [AIMessage(text)], "answer": text, "cited": [], "asked": question}
        reply = interrupt(question)
        return {"messages": [ToolMessage(f"The student answered: {reply}" if i == 0 else NOT_ASKED,
                                         tool_call_id=c["id"], name=ASK)
                             for i, c in enumerate(calls)]}

    return ask


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
    graph.add_node("ask", make_ask_node(pause=checkpointer is not None))
    graph.add_edge("ask", "agent" if checkpointer is not None else END)

    graph.add_edge(START, "normalize")
    graph.add_edge("normalize", "agent")
    graph.add_conditional_edges("agent", route, ["tools", "ask", "check"])
    graph.add_edge("check", END)
    return graph.compile(checkpointer=checkpointer)
