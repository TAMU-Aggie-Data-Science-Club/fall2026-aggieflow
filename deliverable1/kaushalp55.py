import re
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
        "keywords": ["forward", "email"],
        "answer": "Yes, you can have your TAMU email forwarded automatically, but you still have to "
                  "check your official TAMU account often, and the university isn't responsible for "
                  "mail once it leaves your TAMU mailbox.",
        "source": "https://student-rules.tamu.edu/rule61/",
    },
    {
        "keywords": ["skateboard"],
        "answer": "Not inside campus buildings, and not on benches, steps or walls. That goes for "
                  "scooters and rollerblades too.",
        "source": "https://student-rules.tamu.edu/rule38/",
    },
]


# Aggie shorthand -> the words the facts use. Matched as whole words only, so "zach"
# does not turn "zachary" into "zachary engineering education complexary".
ALIASES = {
    "qdrop": "q-drop",
    "wcl": "west campus library",
    "msc": "memorial student center",
    "zach": "zachary engineering education complex",
    "sk8": "skateboard",
}


def expand_aliases(state: State) -> dict:
    question = state["question"].lower()
    for short, full in ALIASES.items():
        question = re.sub(rf"\b{re.escape(short)}\b", full, question)
    return {"question": question}


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

if __name__ == "__main__":
    questions = [
        "When is the Q-drop deadline?",
        "when's the qdrop deadline",
        "Where are the best tacos?",
        "can i forward my tamu email to gmail",
        "can i ride my sk8 board to class",
        "is zachary open late",
    ]
    for q in questions:
        print("Q:", q)
        print(agent.invoke({"question": q})["answer"], "\n")
