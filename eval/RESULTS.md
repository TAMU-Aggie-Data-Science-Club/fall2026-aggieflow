# Agent results (#89)

```
setup: groq:openai/gpt-oss-120b at temperature 0; Atlas (aggieflow), keyword search; commit 829045b; LangSmith tracing on
```

LangSmith experiment: `agent-keyword-829045b-74bb57e7`. Command:

```
uv run python eval/run_eval.py --mode keyword --repetitions 1 --ids eval/sample-40.txt --judges correctness
```

## What changed from the plan in #89

- **Model: gpt-oss-120b, not 20b.** We switched the agent's default before this run, so these are the first results on the model we plan to use.
- **40 questions, not 127.** One person, one free Groq key (200K tokens a day, about 40 runs). `eval/sample-40.txt` covers every source file, every tag, `NOT_SURE` and grade questions, the 8 tasks #92 fixed, and the failures #92 left for #74. It leaves out the 3 questions too large for the free tier (`catalog-aguw0kie124-04`, `catalog-aguw0kie124-05`, `student-rules-rushilsagar-05`) and the known-gap question.
- **1 run per question.** pass^3 and flaky questions weren't measured.
- **Only the `correctness` judge.** It's the only judge in the pass rule, so `passed` is unchanged. `relevance`, `groundedness` and `retrieval_relevance` weren't measured.
- **4 questions still need a run.** They hit the daily token limit (the error says "tokens per day"), so they aren't agent failures: `student-rules-rushilsagar-09`, `transportation-krishjayanth-01`, `-05` and `-08`. The numbers below leave them out.

## Headline

**pass@1: 58% (21 of 36), 95% CI [42%, 75%].**

5 of the 15 failures are test problems, not agent mistakes (see [Failures](#failures)). With those fixed, the agent passes 25 of 36 (69%).

## By source

| Source | Questions | Passed |
|---|---|---|
| anex | 4 | 2 |
| catalog | 4 | 2 |
| extra | 10 | 5 |
| oal | 4 | 3 |
| registrar | 6 | 4 |
| student-rules | 7 | 5 |
| transportation | 1 | 0 |

With 1–10 questions per group, the CIs cover most of 0–100%, so don't rank sources from this run.

## Answer quality and scope

| Metric | Result |
|---|---|
| `cited_page` (cited the expected page) | 83% |
| `correctness` (judge, non-grade questions) | 79% |
| `numbers_match` (grade questions) | 86% |
| False refusals: said "not sure" on an answerable question | 3 of 29 |
| False answers: answered a `NOT_SURE` question | 0 of 7 |

## Tools

| Metric | Result |
|---|---|
| `tool_match` (called only the expected tools) | 75% |
| Mean rounds / tool calls | 1.47 / 1.47 |
| Hit the 4-round limit | 14% |
| Tool error rate | 1% |
| Recovered after a tool error (recovery tasks) | 1 of 2 |

## Speed and cost

- **Tokens:** about 5.4K per run on 120b (200K daily limit used up after about 37 runs).
- **Latency: not measured reliably.** The runner reported p50 22.5 s and p95 130 s, but that includes the Groq client's own waits on the 8K-tokens-a-minute limit, which the runner can't separate out. One question run with no throttling took 2.1 s end to end. A clean latency number needs a paid-tier key or runs spaced a minute apart.

## Failures

Each failure gets one cause (the first thing that went wrong). #74 goes deeper.

**Test problems (5).** The agent's behavior was fine.

| Question | What happened | Fix |
|---|---|---|
| `transportation-krishjayanth-10`, `student-rules-rafperez010-10` | `NOT_SURE` question picked up its file's default tool. The agent rightly declined without searching. | `"tools": []`, as #92 did for others |
| `registrar-06` | Right answer (four Q-drops), cited Student Rule 1, which says the same thing | add rule01 to `also_accept` |
| `catalog-aguw0kie124-03` | Right prerequisite. The reference also lists credit hours, which the question didn't ask for. | trim the reference |
| `anex-rushilsagar-10` | Answer matches the reference ("either profile counts"), but the judge failed it | check the judge on this one |

**Agent mistakes (10).**

| Question | Step | What happened |
|---|---|---|
| `anex-rushilsagar-03` | generation | Called the professor with the *lowest* GPA the "easiest" |
| `registrar-08` | tool selection | Searched Student Rules 4 times, never Registrar, then said not sure |
| `extra-krishjayanth-37` | tool selection | "is engl 206 an icd": searched Student Rules 4 times, not degree plans |
| `student-rules-kaushalp55-08` | retrieval | Right tool, 3 searches, never found Rule 36 (animals) |
| `oal-klee-SAM-03` | citation | Right phone and email, but cited news pages instead of Contact Us |
| `extra-krishjayanth-31` | generation | Wi-Fi steps for the wrong question; judge failed it |
| `extra-krishjayanth-13` | tool selection | Right answer after a misspelled name, but detoured through Student Rules |
| `extra-krishjayanth-25` | tool selection | Right date, but searched Student Rules before Registrar |
| `extra-krishjayanth-34` | tool selection | Right answer, plus an extra degree-plan search |
| `catalog-aguw0kie124-10` | tool selection | Rightly said not sure, but also called `get_course_grades` |

The last four are right answers that failed the strict `tool_match` rule.

## A bug the graders don't catch

120b often puts citations in full-width brackets: `【https://…】`. The link regex in `agent/checks.py` doesn't stop at `】`, so it reads the bracket as part of the URL. The URL then doesn't match any source, and a real link gets replaced with `[link removed: not from a source]`. **12 of 36 answers** show that text to the student. The sources list added at the end is still correct, so `cited_page` passes and no grader caught it. **Fixed in the same PR as this file:** the `URL` regex now stops at `【】`. The numbers above were measured before the fix, and since none of the graders read the inline links, the fix doesn't change them.

## Top 3 fixes

1. **Citation links:** stop the `URL` regex at `【】` (the bug above; done in this PR).
2. **Tool descriptions:** make `search_registrar` and `search_degree_plans` clearly own graduation, calendar and ICD/core questions. 5 failures started by searching Student Rules first.
3. **Grade wording:** say in `get_course_grades`'s description (or the prompt) that "easiest" means the *highest* average GPA.

## Still to do

- Run the 4 capped questions after the daily limit resets, merge with `eval/summarize.py`, and update the numbers.
- Fix the 5 test problems in the question files.
- Publish Share links for one passing and one failing trace (LangSmith → Share).
