from typing import TypedDict

from langgraph.graph import END, START, StateGraph

class State(TypedDict, total=False):
    question: str
    answer: str
    fact: dict

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
    return {"answer" : "I'm not sure. Try the Registrar: https://registrar.tamu.edu"}

def pick_next(state: State) -> str:
    return "cite" if "fact" in state else "not_sure"

"""
def respond(state: State) -> dict:
    question = state["question"].lower()
    for fact in FACTS:
        if all(word in question for word in fact["keywords"]):
            return { "answer" : f"{fact['answer']}\nSource: {fact['source']}" }
    return {"answer" : "I'm not sure. Try the Registrar: https://registrar.tamu.edu"}
"""

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
    "Where is the sauce?",
    "Can I download SOLIDWORKS, for freeeee?",
    "Where can I find the printer in the Computing Services Center?",
    "printer csc building where?"
]
for q in questions:
    print("Q:", q)
    print(agent.invoke({"question": q})["answer"], '\n')