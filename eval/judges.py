"""LLM judges for AggieFlow answers (#71).

Each judge checks one thing and has the shape LangSmith's evaluate() accepts:

    judge(inputs, outputs, reference_outputs) -> {"key", "score", "comment"}

    inputs            {"question": ...}
    outputs           agent.run.answer() result: {"answer", "documents", ...}
    reference_outputs {"answer": ...}  (the eval question's answer, or "NOT_SURE")

score is 1 (yes), 0 (no) or None (the judge couldn't tell); comment is its reasoning.

The judge model is Qwen, not the agent's Gemini model, so the agent doesn't grade
itself. (gpt-oss-120b was tried as the judge first, but a calibration run used up most of its
200k-token daily limit on Groq's free tier.) Check the judges against your own labels with eval/calibrate.py.
"""

from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field

from agent.checks import NOT_SURE as DECLINE  # the agent's exact text when it can't answer

JUDGE_MODEL = "groq:qwen/qwen3.8-27b"
TEMPERATURE = 0
NOT_SURE = "NOT_SURE"
SCORES = {"yes": 1, "no": 0, "unknown": None}


class Verdict(BaseModel):
    reasoning: str = Field(description="Think it through first, in a few sentences.")
    verdict: Literal["yes", "no", "unknown"] = Field(
        description='"unknown" only if you truly cannot tell from what you were given.')


@lru_cache(maxsize=1)
def judge_model():
    from dotenv import load_dotenv
    from langchain.chat_models import init_chat_model

    load_dotenv()
    # json_schema, not the default forced tool call: gpt-oss answered in prose instead of calling it.
    # strict only takes effect on gpt-oss models (langchain-groq ignores it otherwise); there it
    # stopped gpt-oss echoing the schema back instead of filling it in.
    return init_chat_model(JUDGE_MODEL, temperature=TEMPERATURE).with_structured_output(
        Verdict, method="json_schema", strict=True)


def _judge(key: str, prompt: str) -> dict:
    for attempt in range(3):
        try:
            v = judge_model().invoke(prompt)
            break
        except Exception as err:
            # Groq sometimes returns an empty generation ("json_validate_failed") for a prompt
            # that works on the next try; the parser can fail the same way. Anything else is real.
            flaky = "json_validate_failed" in str(err) or type(err).__name__ == "OutputParserException"
            if not flaky or attempt == 2:
                raise
    return {"key": key, "score": SCORES[v.verdict], "comment": v.reasoning}


def _passages(documents: list[dict]) -> str:
    return "\n\n".join(
        f"[{i}] {d.get('title', '')} ({d.get('source_url', '')})\n{d.get('text', '')}"
        for i, d in enumerate(documents, start=1))


def correctness(inputs: dict, outputs: dict, reference_outputs: dict) -> dict:
    reference = reference_outputs["answer"]
    if reference == NOT_SURE:
        rule = ("Our sources can't answer this question. The answer is correct only if it "
                "declines (says it is not sure or doesn't know) instead of giving facts.")
        reference = "(none: the assistant should say it is not sure)"
    else:
        rule = ("The answer is correct if it gives the same facts as the reference: same "
                "numbers, dates, names and conclusion. Extra detail is fine if it doesn't "
                "contradict the reference. Wording doesn't matter. Saying it is not sure is incorrect.")
    return _judge("correctness", f"""You grade a Texas A&M student-help assistant.

{rule}

Question: {inputs["question"]}

Reference answer: {reference}

Assistant's answer: {outputs["answer"]}

Is the assistant's answer correct?""")


def relevance(inputs: dict, outputs: dict, reference_outputs: dict | None = None) -> dict:
    return _judge("relevance", f"""You grade a Texas A&M student-help assistant.

Does the answer address what the student asked? Ignore whether it is factually right.
"yes" if it answers the question asked (or clearly says it can't). "no" if it answers a
different question, goes off topic, or buries the answer in unrelated text.

Question: {inputs["question"]}

Answer: {outputs["answer"]}

Is the answer relevant to the question?""")


def groundedness(inputs: dict, outputs: dict, reference_outputs: dict | None = None) -> dict:
    documents = outputs.get("documents") or []
    answer = outputs["answer"]
    # A full decline makes no claims (the model ignored this rule in a prompt). Only the exact
    # decline: a hedged answer ("not sure about summer, but in fall...") still makes claims.
    if answer.strip() == DECLINE:
        return {"key": "groundedness", "score": 1, "comment": "answer declined, so it makes no claims"}
    if not documents:
        return {"key": "groundedness", "score": 0, "comment": "no passages retrieved, but the answer made claims"}
    return _judge("groundedness", f"""You grade a Texas A&M student-help assistant.

Is every factual claim in the answer supported by the passages below? Ignore whether
the passages themselves are right, and ignore links and citations formatting. "no" if
any claim (a number, date, name, rule) is missing from or contradicts the passages.

Passages:
{_passages(documents)}

Answer: {answer}

Is the answer grounded in the passages?""")


def retrieval_relevance(inputs: dict, outputs: dict, reference_outputs: dict | None = None) -> dict:
    documents = outputs.get("documents") or []
    if not documents:
        return {"key": "retrieval_relevance", "score": None, "comment": "no passages retrieved"}
    return _judge("retrieval_relevance", f"""You grade the search step of a Texas A&M student-help assistant.

Do the retrieved passages contain the information needed to answer the question?
"yes" if at least one passage answers it, even if others are off topic. "no" if none do.

Question: {inputs["question"]}

Passages:
{_passages(documents)}

Do the passages answer the question?""")


JUDGES = [correctness, relevance, groundedness, retrieval_relevance]
