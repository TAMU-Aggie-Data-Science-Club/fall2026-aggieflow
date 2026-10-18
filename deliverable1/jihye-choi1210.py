from typing import TypedDict
from langgraph.graph import END, START, StateGraph

class State(TypedDict, total=False):
    question: str
    answer: str
    fact: dict

# What the agent knows. Every fact cites the page it came from.
FACTS = [
    {
        "keywords": ["q-drop", "deadline"],
        "answer": "The Fall 2026 Q-drop deadline is Monday, November 16, 2026 at 5 p.m.",
        "source": "https://registrar.tamu.edu/academic-calendar/fall-2026.html",
    },
    {
        "keywords": ["calculator", "borrow"],
        "answer": "You can borrow one from the Tech Bar at West Campus Library or the Evans Annex.",
        "source": "https://library.tamu.edu/services/techbar.html",
    },   
    {
        "keywords": ["group study room", "advance"],
        "answer": "You can reserve a group study room up to one week in advance, for up to four hours per day.",
        "source": "https://library.tamu.edu/about/policies/room-policy.html",
    },
]

def find_fact(state: State) -> dict:
    question = state["question"].lower()
    for fact in FACTS:
        if all(word in question for word in fact["keywords"]):
            return {"fact": fact}
    return {}

def cite(state: State) -> dict:
    fact = state["fact"]
    return {"answer": f"{fact['answer']}\nSource: {fact['source']}"}

def not_sure(state: State) -> dict:
    return {"answer": "I'm not sure. Try the Registrar: https://registrar.tamu.edu"}

def pick_next(state: State) -> str:
    return "cite" if "fact" in state else "not_sure"

ALIASES = {
    "qdrop": "q-drop",
    "wcl": "west campus library",
    "msc": "memorial student center",
    "zach": "zachry",
}

def expand_aliases(state: State) -> dict:
    question = state["question"].lower()
    for short, full in ALIASES.items():
        question = question.replace(short, full)
    return {"question": question}

graph = StateGraph(State)
graph.add_node("expand_aliases", expand_aliases)
graph.add_node("find_fact", find_fact)
graph.add_node("cite", cite)
graph.add_node("not_sure", not_sure)
graph.add_edge(START, "expand_aliases")
graph.add_edge("expand_aliases", "find_fact")
graph.add_conditional_edges("find_fact", pick_next, ["cite", "not_sure"])
graph.add_edge("cite", END)
graph.add_edge("not_sure", END)
agent = graph.compile()

questions = [
    "When is the Q-drop deadline?",
    "when's the qdrop deadline",
    "Where are the best tacos?",
    "Where can I borrow a calculator?",
    "How far in advance can I reserve a group study room?",
]
for q in questions:
    print("Q:", q)
    print(agent.invoke({"question": q})["answer"], "\n")