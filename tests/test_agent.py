"""Offline tests for the agent: no API key or network needed.

Run from the repo root:  python -m pytest tests
"""

from langchain_core.messages import AIMessage

from agent.checks import NOT_SURE, finalize
from agent.graph import build_graph
from agent.run import answer

RULE = {
    "id": "student-rules:rule01:4",
    "source": "student-rules",
    "title": "Rule 1",
    "text": "Four Q-drops.",
    "source_url": "https://student-rules.tamu.edu/rule01/",
    "fetched_at": "2026-11-06T00:00:00Z",
}


class ScriptedModel:
    """Stands in for the LLM: returns the given replies in order."""

    def __init__(self, replies):
        self.replies = list(replies)

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        return self.replies.pop(0)


def call(name, args, id):
    return {"name": name, "args": args, "id": id, "type": "tool_call"}


# --- checks ---------------------------------------------------------------

def test_no_sources_means_not_sure():
    text, cited = finalize("You get four Q-drops.", [])
    assert text == NOT_SURE and cited == []


def test_link_not_from_a_source_is_removed():
    text, cited = finalize(
        "Four (https://student-rules.tamu.edu/rule01/). See https://made-up.example.com/x.",
        [RULE],
    )
    assert "made-up.example.com" not in text
    assert "link removed" in text
    assert [p["source_url"] for p in cited] == [RULE["source_url"]]


def test_uncited_answer_still_lists_sources():
    text, cited = finalize("You get four.", [RULE])
    assert "Sources:" in text and RULE["source_url"] in text
    assert cited == [RULE]


# --- graph ----------------------------------------------------------------

def test_groups_run_in_one_round_and_answer_cites_them():
    model = ScriptedModel([
        AIMessage("", tool_calls=[
            call("get_grades", {"dept": "CSCE", "number": "121"}, "1"),
            call("get_garage_counts", {}, "2"),
        ]),
        AIMessage("Grades are here (https://anex.us/grades/?dept=CSCE&number=121)."),
    ])
    result = answer("is csce 121 hard and where can i park", graph=build_graph(model))
    assert result["trace"] == [[
        'course_tools.get_grades({"dept": "CSCE", "number": "121"})',
        "campus_tools.get_garage_counts({})",
    ]]
    assert "as of" in result["answer"]  # live data is time-stamped
    assert [p["source"] for p in result["sources"]] == ["anex"]


def test_empty_search_gives_not_sure():
    model = ScriptedModel([
        AIMessage("", tool_calls=[call("search_policies", {"query": "1998 football game"}, "1")]),
        AIMessage("The Aggies won."),
    ])
    result = answer("who won the 1998 game", graph=build_graph(model))
    assert result["answer"] == NOT_SURE


def test_round_limit_falls_back_when_model_errors():
    class Stubborn(ScriptedModel):
        """Always calls a tool; errors if asked to answer without tools."""

        def __init__(self):
            super().__init__([])
            self.bound = False

        def bind_tools(self, tools):
            bound = Stubborn()
            bound.bound = True
            return bound

        def invoke(self, messages):
            if not self.bound:
                raise RuntimeError("Tool choice is none, but model called a tool")
            return AIMessage("", tool_calls=[call("search_policies", {"query": "q-drop"}, "x")])

    result = answer("how many q drops", graph=build_graph(Stubborn()))
    assert len(result["trace"]) == 4  # stopped at MAX_ROUNDS
    assert result["answer"].startswith("I'm not sure.")
    assert "rule01" in result["answer"]  # still shows what it found


def test_unknown_tool_is_reported_not_crashed():
    model = ScriptedModel([
        AIMessage("", tool_calls=[call("get_weather", {}, "1")]),
        AIMessage("Not sure."),
    ])
    result = answer("weather?", graph=build_graph(model))
    assert result["answer"] == NOT_SURE
