from typing import TypedDict

from langgraph.graph import END, START, StateGraph

class State(TypedDict):
    question: str
    answer: str

# agents know this
FACTS = [
    {
        "keywords": ["q-drop", "deadline"],
        "answer": "The Fall 2026 Q-drop deadline is Monday, November 16, 2026 at 5 p.m.",
        "source": "https://registrar.tamu.edu/academic-calendar/fall-2026.html",
    },
    {
        "keywords": ["free", "download", "solidworks"],
        "answer": "You can download and get a subscription to SOLIDWORKS Student Edition for free if you are a TAMU student.",
        "source": "https://software.tamu.edu/public/AvailableSoftware.aspx",
    },
    {
        "keywords": ["computing services center", "printer"],
        "answer": "The Computing Services Center has a printer in room CSC00.",
        "source": "https://service.tamu.edu/TDClient/36/Portal/KB/Article/809/TAMU-OAL-OAL-Printer-Locations",
    }
]

def respond(state: State) -> dict:
    question = state["question"].lower()
    for fact in FACTS:
        if all(word in question for word in fact["keywords"]):
            return { "answer" : f"{fact['answer']}\nSource: {fact['source']}" }
    return {"answer" : "I'm not sure. Try the Registrar: https://registrar.tamu.edu"}

ALIASES = {
    "qdrop": "q-drop",
    "wcl": "west campus library",
    "csc": "computing services center",
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
    "Where is the sauce?",
    "Can I download SOLIDWORKS, for freeeee?",
    "Where can I find the printer in the Computing Services Center?",
    "printer csc building where?"
]
for q in questions:
    print("Q:", q)
    print(agent.invoke({"question": q})["answer"], '\n')