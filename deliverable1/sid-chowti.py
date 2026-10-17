from typing import TypedDict

from langgraph.graph import END, START, StateGraph


class State(TypedDict):
    question: str
    answer: str


FACTS = [
    {
        "keywords": ["q-drop", "deadline"],
        "answer": "The Fall 2026 Q-drop deadline is Monday, November 16, 2026 at 5 p.m.",
        "source": "https://registrar.tamu.edu/academic-calendar/fall-2026.html",
    },
    {
        "keywords": ["absence", "documentation"],
        "answer": "You have 3 business days after your last missed class to turn in documentation for an excused absence.",
        "source": "https://student-rules.tamu.edu/rule07/",
    },
]


def respond(state: State) -> dict:
    question = state["question"].lower()
    for fact in FACTS:
        if all(word in question for word in fact["keywords"]):
            return {"answer": f"{fact['answer']}\nSource: {fact['source']}"}
    return {"answer": "I'm not sure. Try the Registrar: https://registrar.tamu.edu"}


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
graph.add_node("respond", respond)
graph.add_edge(START, "expand_aliases")
graph.add_edge("expand_aliases", "respond")
graph.add_edge("respond", END)
agent = graph.compile()

questions = [
    "When is the Q-drop deadline?",
    "when's the qdrop deadline",
    "Where are the best tacos?",
    "how long do i have to turn in documentation for an absence",
]
for q in questions:
    print("Q:", q)
    print(agent.invoke({"question": q})["answer"], "\n")
