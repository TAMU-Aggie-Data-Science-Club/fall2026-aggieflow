# Agent results (#89)

```
setup: google_genai:gemini-3.5-flash-lite at temperature 0; Atlas (aggieflow), keyword search; commit 69e9466; LangSmith tracing on
```

**Gemini 3.5 Flash Lite passes 92% (37 of 40), 95% CI [82%, 100%], with a typical answer in 1.2 seconds.** It's the agent's model now.

That's 82% (33 of 40) from the full run, plus 4 questions rerun after fixes: 3 had wrong reference answers, and the garage question's data and decline rule changed. All 4 pass (see [Rerun](#rerun-after-fixes)). The 3 that still fail are right answers that broke the strict `tool_match` rule. The comparison with 3.6 Flash below uses the original 82%, since both models ran on the same questions.

LangSmith experiments (in the `aggieflow-questions` dataset): **Gemini 3.5 Flash Lite · 40 questions · keyword · 69e9466** and **Gemini 3.6 Flash · 40 questions · keyword · 69e9466**. Runs are named `agent-<mode>-<commit>-<id>` and then renamed in LangSmith to say what they are. Command:

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
| `extra-krishjayanth-31` | **test** | Right answer. The source says a router must have its wireless off; the reference left that out, so the judge failed it. Fixed, passes. |
| `student-rules-kaushalp55-02` | **test** | Right answer: Rule 10.13.2 counts a U as an F. The reference said it vaguely and the judge misread it. Fixed, passes. |
| `transportation-krishjayanth-05` | **test** | Right answer, cited the bus service page, which has the same fare text. Added to `also_accept`, passes. |
| `student-rules-kaushalp55-05` | strict tool rule | Right answer; also searched Registrar first |
| `anex-rushilsagar-10` | strict tool rule | Right answer; also pulled grades for MATH 151 |
| `oal-klee-SAM-12` | strict tool rule | Rightly said not sure; searched transportation for "housing" first |

So **1 real wrong answer**, a data problem, not the model, and now fixed. Three are right answers that failed the strict `tool_match` rule, and 3 were test problems.

## Rerun after fixes

Experiment **Gemini 3.5 Flash Lite · rerun 4 after reference fixes · 4e20cf9** (commit `4e20cf9`; the agent changed only by the passage-id link fix):

| Question | Before | After |
|---|---|---|
| `extra-krishjayanth-31` | fail | **pass** |
| `student-rules-kaushalp55-02` | fail | **pass** |
| `transportation-krishjayanth-05` | fail | **pass** |
| `transportation-krishjayanth-10` (garage) | fail: said "364 spots" | **pass**: says it's not sure and links parking pages (experiment **Gemini 3.5 Flash Lite · rerun garage question · 4512eb2**) |

**Rule change (decided on #89):** a "not sure" answer that links related pages now counts as declining. Before, it had to cite nothing. This changes no other question in either Gemini run. The garage question also goes back to its file's default tool (`search_transportation`), since searching before declining is reasonable here.

## Bugs the graders don't catch

Both citation bugs are fixed in code, and neither changes the scores, because the graders don't read inline links.

- **`【】` links (120b):** the link regex read `】` as part of the URL, so a real link became `[link removed: not from a source]` in 12 of 36 answers. Fixed.
- **Passage ids as citations (Flash Lite):** 7 of 34 answers cite `(student-rules:rule10:13)` instead of a link. `agent/checks.py` now swaps a known passage id for its URL. Fixed.

## Cost

About 5K tokens per question. On paid Gemini Flash Lite that's a fraction of a cent, so $10 in credits covers thousands of questions. Groq's free tier is only used for the judges.

## Still to do

- ~~Real-time pages~~ **Done:** the collector skips `Parking/realtime.aspx` now, and its one passage is deleted from Atlas.
- Post Share links for a passing and a failing trace (LangSmith → Share).
- Next: #76 (vector vs keyword on Flash Lite) and #74 (failure review) build on this run.
