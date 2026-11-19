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
        "keywords": ["study", "pod"],
        "answer": "Reservable study pods with seating, a desk, and power outlets are available on the first floor of Evans Library and West Campus Library.",
        "source": "https://library.tamu.edu/spaces/individual.html",
    }
]

ALIASES = {
    "qdrop": "q-drop",
    "wcl": "west campus library",
}



def respond(state: State) -> dict:
    question = state["question"].lower()

    for fact in FACTS:
        if all(word in question for word in fact["keywords"]):
            return {"answer": f"{fact['answer']}\nSource: {fact['source']}"}

    return {"answer": "I'm not sure."}


def expand_aliases(state: State) -> dict:
    question = state["question"].lower()
    for short, full in ALIASES.items():
        question = question.replace(short, full)

    return {"question": question}



graph = StateGraph(State)
graph.add_node("respond", respond)
graph.add_node("expand_aliases", expand_aliases)
graph.add_edge(START, "expand_aliases")
graph.add_edge("expand_aliases", "respond")
graph.add_edge("respond", END)
agent = graph.compile()


questions = [
    "When is the qdrop deadline?",
    "Where can I find a study pod?",
    "when's the qdrop deadline",
    "Where are the best tacos?",
]

for q in questions:
    print("Q:", q)
    print(agent.invoke({"question": q})["answer"], "\n")

