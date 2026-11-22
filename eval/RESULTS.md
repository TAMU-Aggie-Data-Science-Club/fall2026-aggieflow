# Agent results (#89)

```
setup: google_genai:gemini-3.5-flash-lite at temperature 0; Atlas (aggieflow), keyword search; commit c16110e; LangSmith tracing on
```

**The agent (Gemini 3.5 Flash Lite, keyword search) passes 95% (38 of 40), 95% CI [88%, 100%], with a typical answer in 1.3 seconds.** Both failures are right answers that made an extra tool call. No answer in the sample is wrong.

**It's consistent too: pass^3 is 95%.** Run 3 times each, every question gave the same result all 3 times. No question is flaky (see [Reliability](#reliability-pass3)).

**Every answer:** [`eval/flash-lite-40.csv`](flash-lite-40.csv) has one row per question: the question, the expected and actual answer, pages cited, tools called, every score, the latency and the experiment it came from. Open it in Excel or Google Sheets and filter on `passed`.

LangSmith experiments, in the `aggieflow-questions` dataset:
- **Gemini 3.5 Flash Lite · 40 questions · citation fix · c16110e**: the run above
- **Gemini 3.5 Flash Lite · rerun 3 after grader fixes · fb3e7f6**: 3 questions rerun after the fixes in [Test and grader fixes](#test-and-grader-fixes). All 3 pass.

Runs are named `agent-<mode>-<commit>-<id>` and renamed in LangSmith afterward to say what they are. Command:

```
uv run python eval/run_eval.py --ids eval/sample-40.txt --judges correctness --repetitions 1
```

## How we got here

| Step | Commit | pass@1 | What changed |
|---|---|---|---|
| gpt-oss-120b on Groq | `829045b` | 58% (21 of 36) | First run. Dropped: too slow on the free tier, and the daily limit ran out after about 37 questions. |
| Gemini 3.6 Flash | `69e9466` | 72% | After the routing fixes and 5 broken questions |
| Gemini 3.5 Flash Lite | `69e9466` | 82% | Same questions and commit as 3.6 Flash. Picked as the model. |
| Flash Lite + citation fix | `c16110e` | 88%, then **95%** after fixing 3 test problems | The prompt now requires full links |

The model and the fixes changed together, so these numbers don't show how much each fix helped on its own. Only the 3.6 Flash vs Flash Lite row is a clean comparison.

**Fixes made along the way:**
- **Routing:** graduation and the Q-drop deadline go to `search_registrar`, ICD/CD lists to `search_degree_plans`, "easiest professor" means the highest GPA, and a misspelled professor name falls back to `get_course_grades`.
- **Data:** the collector had saved the real-time garage-count page, and the agent quoted a stale "364 open spots". The page is now skipped and was deleted from Atlas.
- **Citations:** see [Bugs the graders don't catch](#bugs-the-graders-dont-catch).

## What's different from the plan in #89

- **40 questions, not 127.** `eval/sample-40.txt` covers every source file and tag, `NOT_SURE` and grade questions, the tasks #92 fixed, and the failures #92 left for #74.
- **pass^3 without the judge.** The headline is 1 run per question, with the judge. The 3-run check used the code graders only (see [Reliability](#reliability-pass3)).
- **Only the `correctness` judge.** It's the only judge in the pass rule, so `passed` is the same. `relevance`, `groundedness` and `retrieval_relevance` weren't measured.
- **Decline rule (decided on #89):** a "not sure" answer that links related pages counts as declining. Before, it had to cite nothing.

## Current agent: details

From the `c16110e` run, before the 3 reruns, so these slightly understate the current agent:

| Metric | Result |
|---|---|
| `cited_page` | 97% |
| `correctness` (judge) | 97% |
| `tool_match` | 95% |
| Said "not sure" on an answerable question | 0 of 33 |
| Answered a `NOT_SURE` question | 0 of 7 |
| Answers with an inline link | 34 of 34 |
| Latency p50 / p95 | 1.3 s / 2.2 s |

**The 2 failures**, both right answers that failed the strict `tool_match` rule:
- `anex-rushilsagar-10` ("is professor kim a good teacher"): also pulled MATH 151 grades, which made the answer better.
- `student-rules-kaushalp55-05` (withdrawing after Q-drop day): searched Registrar as well as Student Rules.

## Reliability (pass^3)

The 40 questions, 3 runs each, with code graders only (`cited_page`, `tool_match`, `numbers_match`, `not_sure_correct`; no judge). Commit `aa05068`, with the same agent as `fb3e7f6`. Experiment: **Gemini 3.5 Flash Lite · 40 questions × 3 (pass^3) · no judge · aa05068**.

| | Result |
|---|---|
| pass@1 | 95% [88%, 100%] |
| **pass^3** (passed all 3 runs) | **95%** |
| Flaky questions (passed 1 or 2 of 3) | **0** |
| Same tool calls in all 3 runs | 39 of 40 |
| Identical answer wording in all 3 runs | 11 of 40 |
| Said "not sure" on an answerable question / answered a `NOT_SURE` question | 0 of 99 / 0 of 21 |
| Latency p50 / p95 | 1.2 s / 2.1 s |

The same 2 questions fail every time: `anex-rushilsagar-10` and `student-rules-kaushalp55-05`, both for an extra tool call. The wording changes from run to run even at temperature 0 (Gemini isn't fully deterministic), but the facts, links and scores don't. The one question whose tool calls changed ("my grandpa passed away…") searched Student Rules twice in one run and still passed.

## The two Gemini models

Paired over the same 40 questions on commit `69e9466` (before the citation fix), from `eval/compare.py --allow-setup-change`:

| | 3.6 Flash | 3.5 Flash Lite | Lite − 3.6 (95% CI) |
|---|---|---|---|
| **Passed** | 72% | **82%** | +10 pts [−3, +23] |
| Latency p50 / p95 | 4.3 s / 8.1 s | **1.2 s / 2.1 s** | −3.4 s [−3.9, −2.9] |
| Answered a `NOT_SURE` question | 3 of 7 | **1 of 7** | |
| `tool_match` | 80% | 90% | |
| Tool calls per question | 1.45 | 1.12 | −0.33 [−0.55, −0.12] |

Lite won 5 questions, lost 1 and tied 34. The pass difference is within noise, but Lite is clearly faster and never worse.

## Search mode (#76, partly done)

All 102 search questions, on the same commit (`c16110e`), with **no judge**, so `passed` = `cited_page` + `tool_match` (+ `numbers_match`). No vector or hybrid query fell back to keyword.

| | keyword | vector | hybrid |
|---|---|---|---|
| **Passed** | **75%** [66, 82] | 72% [63, 80] | 74% [65, 82] |
| Cited the expected page | **80%** | 76% | 79% |
| Said "not sure" on an answerable question | **2 of 97** | 7 of 97 | 3 of 97 |
| Latency p50 / p95 | **1.3 / 2.8 s** | 1.4 / 3.1 s | 1.5 / 4.0 s |

| Paired difference | passed | wins / losses / ties |
|---|---|---|
| vector − keyword | −3 pts [−10, +4] | 5 / 8 / 89 |
| hybrid − keyword | −1 pt [−6, +4] | 3 / 4 / 95 |
| hybrid − vector | +2 pts [−4, +9] | 6 / 4 / 92 |

**Decision: keep keyword.** The modes tie on pass@1, and keyword is never worse. Vector adds false "not sure" answers (+5 pts, CI [0, +10]). Hybrid is slower (+0.35 s, CI [+0.17, +0.52]).

#75 found vector best on retrieval alone. But that test searched with the student's raw question. The agent rewrites questions into keyword-style queries ("Q-drop deadline Spring 2027") before searching, which closes the gap.

Experiments: **#76 keyword / vector / hybrid · 102 search questions · no judge · c16110e**.

These runs predate the fix that stops `numbers_match` from reading list markers like "1." as numbers. It affects all three modes alike.

**Left for #76:** the judge columns (`correctness`, `groundedness`, `retrieval_relevance`), reading 3 questions where the modes differ, and step 6: retrieval with the agent's own queries, reformulation lift and precision@5.

## Test and grader fixes

The eval was wrong more often than the agent. Every fix below turned a failure on a correct answer into a pass:

| Question | Problem | Fix |
|---|---|---|
| `extra-krishjayanth-31` | The reference left out that a router needs its wireless off | Reference matches the source |
| `student-rules-kaushalp55-02` | The reference was vague about U grades counting as F | Reference says it plainly (Rule 10.13.2) |
| `extra-krishjayanth-17` | The reference said "Yes" to "will that hurt my grade" | Now "No, as long as…" |
| `transportation-krishjayanth-05`, `registrar-08` | A second page states the same fact | Added to `also_accept` |
| `anex-rushilsagar-03` | `numbers_match` read "1. 2. 3." list markers as numbers | Grader skips list markers |
| `transportation-krishjayanth-10`, `student-rules-rafperez010-10` | `NOT_SURE` tasks had the wrong expected tools | Fixed |
| `catalog-aguw0kie124-03`, `anex-rushilsagar-10` | The references asked for facts the question didn't | Trimmed |
| `registrar-06` | Student Rule 1 says the same as the expected page | Added to `also_accept` |

## Bugs the graders don't catch

All fixed in `agent/checks.py` or the system prompt. The graders don't read inline links, so none of these changed a score.

- **`【】` links (gpt-oss-120b):** the link regex read `】` as part of the URL, so real links became `[link removed: not from a source]` in 12 of 36 answers.
- **Passage ids as citations (Flash Lite):** `(student-rules:rule10:13)` instead of a link, in 7 of 34 answers. Known ids are now swapped for their URL.
- **Missing inline links (Flash Lite):** 15 of 33 answers had no inline link, so every search result was listed as a source, including unrelated news pages. After the prompt fix, it's 0 of 34. Bare site names like `(anex.us)` also become the link when only one source is from that site.

## Example traces

From the experiments above; the full rows are in the CSV.

**A. Pass: "how do i get my laptop, xbox and tv all online in my room at the commons"**
- Tool: `search_tech_help`, which returned the On-Campus Resident Resources page among others.
- Answer: TAMU_WiFi or Ethernet for the laptop; TAMU_IoT, with the registration steps, for the Xbox and TV; and a router only with its wireless off.

**B. Fail with a right answer: "is professor kim a good teacher for math 151"**
- Tools: `get_course_grades` and `get_professor_ratings`.
- Answer: rated 4.7/5, over 90% would take him again, and a 3.18 average GPA.
- Failed only `tool_match`, because just the ratings tool was expected.

**C. A real wrong answer, now fixed: "how many open spots are in west campus garage right now"**
- Before: "There are 364 open spots", from a stale snapshot of the real-time page.
- After removing the page: says it's not sure and links the parking pages. Passes.

## Cost

About 5K tokens per question: a fraction of a cent on paid Gemini Flash Lite, so $10 in credits covers thousands of questions. Groq's free tier is only used for the judge.

## Not measured

- **pass^3 with the judge:** the 3-run check used code graders only.
- **Judges outside the pass rule:** `relevance`, `groundedness`, `retrieval_relevance`.
- **The rest of #76:** see above. #74 (failure review) can build on this file's failure list.
