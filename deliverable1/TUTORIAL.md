# Week 1 tutorial: build a tiny AggieFlow agent

**Due Friday, October 16, 2026. About 45 minutes.**

In this tutorial you'll build a small agent with LangGraph, one piece at a time. It answers student questions with a source, or says "I'm not sure" instead of guessing. Those are the two rules the real AggieFlow agent will follow too.

## Step 0: Set up

Replace `<you>` with your GitHub username in lowercase, everywhere in this tutorial.

```bash
git clone <repo URL>
cd <repo folder>
git switch -c issue-5/<you>
pip install langgraph
```

You need Python 3.10 or newer. If `pip` or `python` isn't found, try `pip3` and `python3`.

Create an empty file called `<you>.py` inside the `deliverable1` folder. You'll build your agent in that file.

## Step 1: Describe the state

Every LangGraph agent has a **state**: a shared notepad that each step reads from and writes to. Ours holds two things, the student's question and the agent's answer.

Put this at the top of your file:

```python
from typing import TypedDict

from langgraph.graph import END, START, StateGraph


class State(TypedDict):
    question: str
    answer: str
```

`TypedDict` just says "a dictionary with these keys." Nothing runs yet.

## Step 2: Write your first node

A **node** is one step the agent takes. In LangGraph a node is a plain Python function: it receives the state and returns a dictionary with only the keys it wants to change.

Our first node looks the question up in a list of facts. Every fact carries the page it came from, so every answer can cite its source. Add this below the state:

```python
# What the agent knows. Every fact cites the page it came from.
FACTS = [
    {
        "keywords": ["q-drop", "deadline"],
        "answer": "The Fall 2026 Q-drop deadline is Monday, November 16, 2026 at 5 p.m.",
        "source": "https://registrar.tamu.edu/academic-calendar/fall-2026.html",
    },
]


def respond(state: State) -> dict:
    question = state["question"].lower()
    for fact in FACTS:
        if all(word in question for word in fact["keywords"]):
            return {"answer": f"{fact['answer']}\nSource: {fact['source']}"}
    return {"answer": "I'm not sure. Try the Registrar: https://registrar.tamu.edu"}
```

A fact matches when every one of its keywords appears in the question. If nothing matches, the agent says it isn't sure instead of making something up.

## Step 3: Connect it into a graph and run it

**Edges** decide the order the nodes run in. `START` and `END` are built-in markers for where the agent begins and stops. Add this at the bottom of your file:

```python
graph = StateGraph(State)
graph.add_node("respond", respond)
graph.add_edge(START, "respond")
graph.add_edge("respond", END)
agent = graph.compile()

result = agent.invoke({"question": "When is the Q-drop deadline?"})
print(result["answer"])
```

Here's what each part does:

- `StateGraph(State)` makes an empty graph that uses your state.
- `add_node` adds a step, and `add_edge` says what runs after what.
- `compile()` turns the graph into something you can run.
- `invoke(...)` runs the graph with a starting state and returns the final state.

Run it:

```bash
python deliverable1/<you>.py
```

You should see:

```
The Fall 2026 Q-drop deadline is Monday, November 16, 2026 at 5 p.m.
Source: https://registrar.tamu.edu/academic-calendar/fall-2026.html
```

You just built and ran an agent.

## Step 4: Try to break it

Real students don't type perfectly. Replace the last two lines of your file (`result = ...` and `print(...)`) with a few test questions:

```python
questions = [
    "When is the Q-drop deadline?",
    "when's the qdrop deadline",
    "Where are the best tacos?",
]
for q in questions:
    print("Q:", q)
    print(agent.invoke({"question": q})["answer"], "\n")
```

Run it again. The first question still works. The tacos question gets "I'm not sure," which is exactly right. But "when's the qdrop deadline" also gets "I'm not sure," because the agent doesn't know that "qdrop" means "q-drop." You'll fix that in Step 6.

## Step 5: Teach it a fact of your own

Find something a student would actually ask, on an official tamu.edu page: the [course catalog](https://catalog.tamu.edu/undergraduate/), the [Registrar](https://registrar.tamu.edu/academic-calendar/fall-2026.html), [Student Rules](https://student-rules.tamu.edu/) or the [Libraries](https://library.tamu.edu/).

Add it to `FACTS`, with:

- **keywords:** one or two words that will appear in the question, in lowercase
- **answer:** the answer in your own words (don't copy-paste from the page)
- **source:** the exact page you used

For example:

```python
    {
        "keywords": ["calculator", "borrow"],
        "answer": "You can borrow one from the Tech Bar at West Campus Library or the Evans Annex.",
        "source": "https://library.tamu.edu/services/techbar.html",
    },
```

Then add your question to the `questions` list and run the file. Your question should get your answer with your source.

## Step 6: Add a second node for Aggie shorthand

The fix for "qdrop" is a new node that rewrites shorthand before `respond` sees the question. This is how agents are built: small steps, each with one job, connected in order.

Add this above your graph code. Keep `qdrop`, and add at least two shorthands of your own (MSC, Zach, WCL, whatever you actually type):

```python
ALIASES = {
    "qdrop": "q-drop",
    "wcl": "west campus library",
}


def expand_aliases(state: State) -> dict:
    question = state["question"].lower()
    for short, full in ALIASES.items():
        question = question.replace(short, full)
    return {"question": question}
```

Notice that this node returns a new `question`. LangGraph writes it into the state, so the next node reads the rewritten version.

Now connect it. Change your graph code so it runs `START -> expand_aliases -> respond -> END`:

```python
graph = StateGraph(State)
graph.add_node("expand_aliases", expand_aliases)
graph.add_node("respond", respond)
graph.add_edge(START, "expand_aliases")
graph.add_edge("expand_aliases", "respond")
graph.add_edge("respond", END)
agent = graph.compile()
```

Run it again. "when's the qdrop deadline" now gets an answer with a source.

<details>
<summary>Lost? Here's the whole file at this point</summary>

```python
from typing import TypedDict

from langgraph.graph import END, START, StateGraph


class State(TypedDict):
    question: str
    answer: str


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
    "Can I borrow a calculator?",
]
for q in questions:
    print("Q:", q)
    print(agent.invoke({"question": q})["answer"], "\n")
```

</details>

## Step 7: Submit it

```bash
git add deliverable1/<you>.py
git commit -m "Add <you>'s week 1 agent (#5)"
git push -u origin issue-5/<you>
```

On GitHub, open a pull request from `issue-5/<you>` into `main`. A PM will review and merge it.

## Done when

- [ ] Your own question gets your answer with its source
- [ ] "when's the qdrop deadline" gets an answer with a source
- [ ] The tacos question still gets "I'm not sure"
- [ ] Your pull request is open by Friday

## Bonus (optional): let the graph choose its path

So far the graph always runs the same steps in the same order. Real agents make choices. Here `respond` is split into three nodes: `find_fact` looks for a match, and then the graph picks either `cite` or `not_sure`. That choice is a **conditional edge**.

First, change `State` so it can also hold the matching fact. `total=False` means not every key has to be filled in:

```python
class State(TypedDict, total=False):
    question: str
    answer: str
    fact: dict
```

Then replace `respond` with these nodes, plus a small function that picks the next one:

```python
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
```

And wire it up. `add_conditional_edges` calls `pick_next` after `find_fact`, and runs whichever node name it returns:

```python
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
```

Run it again. Your output should be exactly the same as before.

## How this connects to AggieFlow

The real agent has the same shape, just bigger. The shorthand node grows into matching program, building and professor names. The fact list becomes a search over the catalog, Registrar pages and grade data. And it keeps the same two rules: cite a source, or say "I'm not sure."
