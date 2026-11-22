# Agent results (#89)

```
setup: google_genai:gemini-3.5-flash-lite at temperature 0; Atlas (aggieflow), keyword search; commit 69e9466; LangSmith tracing on
```

**Gemini 3.5 Flash Lite passes 82% (33 of 40), 95% CI [70%, 92%], with a typical answer in 1.2 seconds.** It's the agent's model now.

LangSmith experiments: `agent-keyword-69e9466-2c690832` (Flash Lite), `agent-keyword-69e9466-752f8042` (3.6 Flash). Command:

```
AGGIEFLOW_MODEL=google_genai:gemini-3.5-flash-lite uv run python eval/run_eval.py --ids eval/sample-40.txt --judges correctness --repetitions 1
```

## How we got here

1. **gpt-oss-120b on Groq** (commit `829045b`): 58% (21 of 36). Its failures led to the routing fixes and the two citation-link fixes below. We dropped it: on Groq's free tier, answers waited on rate limits, and the daily limit ran out after about 37 questions.
2. **Fixes** (commit `69e9466`): sharper tool descriptions (graduation and Q-drop deadline → Registrar, ICD/CD → degree plans, "easiest" = highest GPA, misspelled professor names), and 5 broken test questions fixed.
3. **Gemini 3.6 Flash vs 3.5 Flash Lite**, same 40 questions, same commit. Flash Lite won.

The model and the fixes changed together, so these results don't show how much the fixes alone helped.

## What's different from the plan in #89

- **40 questions, not 127.** `eval/sample-40.txt` covers every source file and tag, `NOT_SURE` and grade questions, the tasks #92 fixed, and the failures #92 left for #74. It leaves out the 3 questions too large for Groq's free tier and the known-gap question.
- **1 run per question.** pass^3 and flaky questions weren't measured.
- **Only the `correctness` judge.** It's the only judge in the pass rule, so `passed` is the same. `relevance`, `groundedness` and `retrieval_relevance` weren't measured.

## The two Gemini models

From `eval/compare.py --allow-setup-change`, paired over the same 40 questions:

| | 3.6 Flash | 3.5 Flash Lite | Lite − 3.6 (95% CI) |
|---|---|---|---|
| **Passed** | 72% | **82%** | +10 pts [−3, +23] |
| Latency p50 / p95 | 4.3 s / 8.1 s | **1.2 s / 2.1 s** | −3.4 s [−3.9, −2.9] |
| Answered a `NOT_SURE` question | 3 of 7 | **1 of 7** | |
| Said "not sure" on an answerable question | 0 of 33 | 0 of 33 | |
| `cited_page` | 97% | 97% | |
| `correctness` | 88% | 91% | |
| `tool_match` | 80% | 90% | |
| Tool calls per question | 1.45 | 1.12 | −0.33 [−0.55, −0.12] |

Lite won 5 questions, lost 1 and tied 34. The pass difference is within noise (the CI crosses 0), but Lite is clearly faster and never worse, so it's the pick.

## Flash Lite by source

| Source | Questions | Passed |
|---|---|---|
| anex | 4 | 3 |
| catalog | 4 | 4 |
| extra | 10 | 9 |
| oal | 4 | 3 |
| registrar | 6 | 6 |
| student-rules | 8 | 6 |
| transportation | 4 | 2 |

With 4–10 questions per source, don't rank sources from this.

## Flash Lite's 7 failures

| Question | Step | What happened |
|---|---|---|
| `transportation-krishjayanth-10` | **data** | "how many open spots in west campus garage right now": answered "364" from the real-time garage page, which we collected once. The number is a stale snapshot. |
| `extra-krishjayanth-31` | generation or test | Wi-Fi/router answer the judge failed (120b failed it too). Check the reference. |
| `student-rules-kaushalp55-02` | judge? | S/U answer looks right. The judge objected to "U counts like an F in your GPA", which the reference seems to agree with. Check. |
| `transportation-krishjayanth-05` | citation | Right answer (buses are free), cited the bus service page, not "how to ride" |
| `student-rules-kaushalp55-05` | strict tool rule | Right answer; also searched Registrar first |
| `anex-rushilsagar-10` | strict tool rule | Right answer; also pulled grades for MATH 151 |
| `oal-klee-SAM-12` | strict tool rule | Rightly said not sure; searched transportation for "housing" first |

So **1 real wrong answer**, a data problem, not the model. Three are right answers that failed the strict `tool_match` rule, and 2–3 may be test or judge problems.

## Bugs the graders don't catch

Both citation bugs are fixed in code, and neither changes the scores, because the graders don't read inline links.

- **`【】` links (120b):** the link regex read `】` as part of the URL, so a real link became `[link removed: not from a source]` in 12 of 36 answers. Fixed.
- **Passage ids as citations (Flash Lite):** 7 of 34 answers cite `(student-rules:rule10:13)` instead of a link. `agent/checks.py` now swaps a known passage id for its URL. Fixed.

## Cost

About 5K tokens per question. On paid Gemini Flash Lite that's a fraction of a cent, so $10 in credits covers thousands of questions. Groq's free tier is only used for the judges.

## Still to do

- ~~Real-time pages~~ **Done:** the collector skips `Parking/realtime.aspx` now, and its one passage is deleted from Atlas. The agent now says it's not sure, but it cites pages while saying so, which `not_sure_correct` still fails. Decide whether a "not sure, but see these pages" answer should count.
- Check the references for `extra-krishjayanth-31` and `student-rules-kaushalp55-02`, and add the bus service page to `transportation-krishjayanth-05`'s `also_accept`.
- Post Share links for a passing and a failing trace (LangSmith → Share).
- Next: #76 (vector vs keyword on Flash Lite) and #74 (failure review) build on this run.
