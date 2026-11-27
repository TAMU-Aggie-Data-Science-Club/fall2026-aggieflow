# Agent results

**The agent passes 90.5% of the eval (162 of 179 questions), 95% CI [86%, 94%].** That's 8 points above the release run. It never answered a question it should have declined, and a typical answer takes 2.9 s.

**Decision: ready to ship.** These result files are now the regression baseline. Two of the 17 failures were fixed after the run (see [Failures](#failures)). Retrieval on the catalog is the weakest area left.

How we got here, and the side experiments (models, search mode, reranking, judges), are in [HISTORY.md](HISTORY.md).

## Setup

| | |
|---|---|
| Model | `google_genai:gemini-3.5-flash-lite`, temperature 0 (Gemini ignores the temperature setting, so wording varies from run to run) |
| Search | Atlas (`aggieflow`), hybrid: keyword + vector. Reranking (#153) came later and isn't in this run; with the agent's queries it made no difference. |
| Commit | `ae6f39a` (after #139), Nov 22, 2026 |
| Questions | All 179 in `eval/questions/` on that date, each run once. The 15 Libraries questions were added the next day and haven't been run yet. |
| Judge | `correctness` only (the only judge in the pass rule) |
| Result files | `eval/results/release-final-part1.jsonl` to `part4.jsonl` |

**The questions:**

| Kind | Count |
|---|---|
| Single-turn | 145 |
| Ask (the agent should or shouldn't ask "which one?") | 16 |
| Multi-turn (follow-ups, corrections, topic switches) | 18 |
| Should say "not sure" (`NOT_SURE`) | 18 of 179 |

**What counts as a pass:** every grader that applies passes:
- **The source:** the answer cites the expected page (`cited_page`), or it says "not sure" when it should (`not_sure_correct`).
- **The answer:** the judge says it's correct (`correctness`), or every number matches the grade data (`numbers_match`).
- **Asking:** on ask questions, it asks exactly when it should (`asked_right`).

`tool_match` is recorded but never fails a question, because an extra tool call can still give a right answer.

## Results

| | Release run (`8d659b9`, baseline) | **Final run (`ae6f39a`)** |
|---|---|---|
| **Passed** | 83% (148 of 179) | **90.5% (162 of 179)**, CI [86%, 94%] |
| Cited the expected page / judge says correct | 88% / 87% | 96% / 92% |
| Answered a question it should have declined | 3 of 18 | **0 of 18** |
| Said "not sure" when it shouldn't have | 2 of 160 | 1 of 161 |
| Asked when it shouldn't / didn't ask when it should | 1 of 10 / 0 of 6 | 0 of 10 / 0 of 6 |
| Latency p50 / p95 | 2.8 s / 5.8 s | 2.9 s / 5.6 s |

Compared question by question (`compare.py`): **+8 points, 95% CI [+2, +13]**. 21 questions went from fail to pass, and 7 went from pass to fail.

**By source:**

| Source | Questions | Passed |
|---|---|---|
| anex (grades) | 12 | 100% |
| RateMyProfessors | 14 | 100% |
| Registrar | 20 | 100% |
| Multi-turn | 18 | 100% |
| Student Rules | 30 | 93% |
| Ask | 16 | 88% |
| Extra (mixed) | 37 | 86% |
| Transportation | 10 | 80% |
| OAL (IT help) | 12 | 75% |
| Catalog | 10 | 70% |

Sources with 10 to 16 questions have wide CIs (catalog's is [40%, 100%]).

**Reranking (#153):** added after this run, with Voyage `rerank-2.5` on hybrid search. It was measured on search alone (no agent), commits `95f8b71` and `41ee048`:

| Hybrid search | Questions | hit@1 | hit@5 | MRR@10 |
|---|---|---|---|---|
| Raw questions, no rerank | 99 | 0.57 | 0.75 | 0.64 |
| Raw questions, rerank | 99 | **0.68** | **0.86** | **0.76** |
| Agent's queries, no rerank | 83 | 0.72 | 0.86 | 0.78 |
| Agent's queries, rerank | 83 | 0.70 | 0.88 | 0.78 |

- **Reranking helps on questions as students type them.** On raw questions it gains about 11 points at hit@1, mostly on paraphrased questions and Student Rules.
- **With the agent's queries it makes no difference.** The agent rewrites questions into keywords before searching, which already does most of what reranking does. So the gain mostly doesn't reach users today.
- **It stays on.** It helps when a query is poorly worded, at the cost of one Voyage call per search. To turn it off, leave `VOYAGE_API_KEY` empty.
- **Catalog is still the weakest source** at hit@1 with or without reranking.

The full breakdown, by source and against keyword and vector search, is in [HISTORY.md](HISTORY.md#reranking-153).

**Cost:** about 5K tokens per question, a fraction of a cent on paid Gemini Flash Lite. This is an estimate; tokens weren't logged per run. The judge ran on Groq's free tier.

## Failures

17 questions failed. Each is grouped by the first step that went wrong. Causes come from one extra diagnostic run per question, because result files don't save answer text.

| Cause | Count | Share |
|---|---|---|
| Flaky: passed on a rerun | 8 | 47% |
| Answer: right page, incomplete answer | 4 | 24% |
| Citation | 2 | 12% |
| Tool choice | 1 | 6% |
| Conversation | 1 | 6% |
| Retrieval | 1 | 6% |

**Answer (4):** each found the right page but left out a detail.
- `extra-krishjayanth-32` (Google Drive after graduation): left out the two-year temporary access.
- `transportation-krishjayanth-02` (parking after 5 p.m.): left out the West Campus Garage's 4 p.m. start.
- `oal-klee-SAM-01` (WiFi off campus): mentioned only eduroam, not the VPN.
- `extra-krishjayanth-26` (reading day before May finals): said yes but left out the date.

**Citation (2):**
- `catalog-aguw0kie124-05` (CS capstone): cited a link that wasn't in its sources.
- `oal-klee-SAM-05` (AI platforms): a right answer citing a different IT page. The question may need to accept that page too.

**Tool choice (1), fixed after the run:** `extra-krishjayanth-20` ("i want to go from bio to engineering") searched the Registrar instead of the Student Rules and said "not sure", in 3 of 3 reruns. This was a regression from #139. The Student Rules tool description now lists changing your major: **6 of 6 pass**.

**Conversation (1), fixed after the run:** `ask-aguw0kie124-03` ("how is dr kim") asked "Which Dr. Kim?" before looking anything up, with made-up names. The agent now can't offer options until it has looked something up: **3 of 4 pass**, and the miss was in the answer after the student picked.

**Retrieval (1):** `student-rules-rushilsagar-10` (parking permit price): three Transportation searches didn't bring up the rate table, so it said "not sure".

**Flaky (8):** these passed a diagnostic rerun, or most earlier runs: `ask-aguw0kie124-10`, `catalog-aguw0kie124-02`, `catalog-aguw0kie124-04`, `extra-krishjayanth-13`, `extra-krishjayanth-29`, `oal-klee-SAM-11`, `student-rules-kaushalp55-09`, `transportation-krishjayanth-06`.

After the two fixes, the ask and multi-turn questions (34) scored 31 vs 32 before, and Student Rules and Registrar (50) scored 48 vs 48. Both are within noise.

## Every question

[`final-run.csv`](final-run.csv) has one row per question: the question, expected answer and page, pass or fail, the failure cause and a note, every score, and latency. Failures are listed first. Open it in Excel or Google Sheets and filter on `passed` or `failure_cause`.

The result files don't save the agent's answer text or tool calls, so the CSV doesn't have them. For a sample with full answers, see [`flash-lite-40.csv`](flash-lite-40.csv) (40 questions, older commit; details in [HISTORY.md](HISTORY.md#40-question-sample-89)).

## Checking a change

A PR that changes the prompt, model or tools runs the affected questions and compares them with this baseline:

```
uv run python eval/compare.py --a eval/results/release-final-part*.jsonl --b <new run>
```

## Not measured

- **The 15 Libraries questions:** added after this run.
- **Consistency across runs (pass^3) on every question:** the final run ran each question once. Earlier pass^3 checks on subsets are in [HISTORY.md](HISTORY.md#reliability-pass3).
- **Answer text and traces for this run:** the result files keep scores only, and LangSmith tracing was off.
- **The other judges** (`relevance`, `groundedness`, `retrieval_relevance`): measured on one 40-question run only, and the groundedness judge isn't calibrated ([HISTORY.md](HISTORY.md#judges-outside-the-pass-rule-101)).
- **Exact cost:** tokens weren't logged per run.
