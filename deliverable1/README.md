# Deliverable 1: Build a tiny AggieFlow agent

**Issue:** [#5](https://github.com/TAMU-Aggie-Data-Science-Club/fall2026-aggieflow/issues/5) · **Due:** Friday, October 16, 2026 · **Time:** about 45 minutes

Build a small agent with [LangGraph](https://langchain-ai.github.io/langgraph/) that answers student questions with a source, or says "I'm not sure" instead of guessing. Those are the two rules the real AggieFlow agent will follow too.

You'll learn the three ideas LangGraph is built on (**state**, **nodes**, and **edges**) and open your first pull request in this repo. No API keys or AI models are needed: the agent looks answers up in a small list of facts you write.

**Follow the full step-by-step walkthrough in [`TUTORIAL.md`](TUTORIAL.md).**

## What you'll do

1. **Set up:** clone the repo, create a branch named `issue-5/<you>`, run `pip install langgraph` (Python 3.10+), and create `deliverable1/<you>.py`.
2. **Describe the state:** the shared data each step reads and writes (the question and the answer).
3. **Write a node:** a function that looks the question up in a list of facts, each with a source URL.
4. **Connect it into a graph** with `START` and `END`, then run it.
5. **Try to break it** with messy questions, such as "when's the qdrop deadline".
6. **Teach it a fact of your own** from an official tamu.edu page, with the answer in your own words and the exact source URL.
7. **Add a second node** that expands Aggie shorthand (`qdrop`, `wcl`, plus at least two of your own) before answering.
8. **Submit:** commit your file, push, and open a pull request into `main`. A PM reviews and merges it.

Replace `<you>` with your GitHub username in lowercase.

## Done when

- [ ] Your own question gets your answer with its source
- [ ] "when's the qdrop deadline" gets an answer with a source
- [ ] "Where are the best tacos?" still gets "I'm not sure"
- [ ] Your pull request is open by Friday

**Bonus (optional):** split the answer step into `find_fact`, `cite`, and `not_sure`, and use a conditional edge to choose between them.

Stuck? Post the command you ran and the full error in the team chat.
