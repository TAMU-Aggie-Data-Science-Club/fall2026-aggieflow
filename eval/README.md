# Eval questions

Each file in `eval/questions/` holds test tasks, one JSON object per line. `eval/score.py` reads every file. The judges (#71), routing tests (#72) and eval runner (#73) read them too.

## Fields

| Field | Required | Meaning | Example |
|---|---|---|---|
| `id` | yes | Unique, stable id | `"student-rules-rushilsagar-01"` |
| `question` | yes | What the student types | `"how many q drops do i get"` |
| `answer` | yes | The correct answer, or `"NOT_SURE"` if our sources can't answer it | `"Four..."` |
| `source_url` | yes | The page that answers it (`null` for `NOT_SURE`) | `"https://student-rules.tamu.edu/rule01/"` |
| `also_accept` | no | Other pages that answer it just as well; citing any of them counts as citing the page | `["https://www.it.tamu.edu/oal/aggieprint.html"]` |
| `tools` | no | Tools the agent should call. `[]` means none. | `["search_student_rules"]` |
| `args` | no | Expected tool arguments | `{"course": "MATH 151"}` |
| `set` | no | `regression` (should always pass) or `capability` (hard) | `"capability"` |
| `tags` | no | Labels for slicing results | `["paraphrase"]` |
| `history` | no | Earlier turns of a conversation, oldest first. `question` is the follow-up being graded. | `[{"role": "user", "content": "when's q drop"}, {"role": "assistant", "content": "..."}]` |

When a line has no `tools`, the scorer picks a default from the file name:

| File starts with | Default `tools` |
|---|---|
| `student-rules` | `search_student_rules` |
| `registrar` | `search_registrar` |
| `oal` | `search_tech_help` |
| `catalog` | `search_degree_plans` or `get_course` |
| `anex` | `get_course_grades` or `get_professor_grades` |
| `transportation` | `search_transportation` |
| `ratemyprofessors` | `get_professor_ratings` |

Files with any other prefix, like `extra-<name>.jsonl`, set `tools` on every line.

**Tags:**
- `no-tool`: the agent shouldn't call a tool.
- `multi-tool`: needs two tools.
- `paraphrase`: shares no distinctive words with its page.
- `shorthand`: uses student shorthand ("qdrop", "hrs", "ESA").
- `recovery`: the first tool call should fail and the agent should retry.
- `real`: asked by a real student.
- `known-gap`: the page isn't collected yet. `eval/score.py` skips these tasks.

## Writing questions

Questions copied from a page share its words, which makes keyword search look better than it is.

1. **Write the question first.** Write it before you open the page, the way a student would type it: lowercase, short, with shorthand. Then find the page and write the answer from it.
2. **Use real questions where you can.** Take them from r/aggies, class Discords, or friends ("what would you ask about Q-drops?"), and tag them `real`. Aim for about half of new tasks.
3. **Check `paraphrase` tasks.** First run a word-overlap check against the page's title and headings. Then give an LLM the question, title and headings, and ask whether the question reuses any distinctive word or near-synonym (for example "withdraw" for "Q-drop"). Reword any task that fails either check.
4. **Check every answer by hand** against its source page. For grades, use the live anex.us numbers, and put every number (GPA, % A's, students) in the answer, because #73 grades anex answers by their numbers.
5. **Give `NOT_SURE` questions a real reason.** Use questions a student would actually ask that our sources don't cover (dining, football, weather), not nonsense.

## Judges and calibration

`eval/judges.py` has four LLM judges, one per thing they check. Each returns `{"key", "score", "comment"}` in the shape LangSmith's `evaluate()` accepts, with a score of 1 for yes, 0 for no, or `None` when the judge can't tell.

| Judge | Checks |
|---|---|
| `correctness` | the answer against the question's reference `answer`. A `NOT_SURE` reference means the answer should decline. |
| `relevance` | whether the answer addresses the question |
| `groundedness` | whether every claim is in the retrieved passages. The agent's standard "I'm not sure" answer counts as grounded with no LLM call; a hedged answer is still judged. |
| `retrieval_relevance` | whether the retrieved passages answer the question. With no passages, the score is `None`. |

The judge model is `groq:qwen/qwen3.8-27b` at temperature 0, which is a different model family from the agent's Gemini. If you change it, calibrate again.

**Calibrate before you trust them:**

1. Run `uv run python eval/calibrate.py --make`. It runs the agent on 20 fixed questions (3 of them `NOT_SURE`) and writes `eval/calibration.jsonl`.
2. Set every value under `labels` in that file to `"yes"`, `"no"` or `"unknown"`, using your own judgment. Read the `answer`, the `reference` and the `documents`.
3. Run `uv run python eval/calibrate.py`. It prints the agreement for each judge, and every judge needs at least 85%. Where a judge disagrees with you, its reasoning is printed. Fix that judge's prompt and run it again.

## Full-loop eval

`eval/run_eval.py` runs the whole agent on every task in LangSmith, grades each run, and prints pass rates:

```bash
uv run python eval/run_eval.py --mode keyword --repetitions 3
```

- **Dataset:** the questions sync to the LangSmith dataset `aggieflow-questions`. New ids are added, and an edited question's example is updated to match. `known-gap` tasks are skipped.
- **Code graders** (1 or 0):
  - `cited_page`
  - `not_sure_correct`: a `NOT_SURE` task's answer says "not sure". Linking related pages is fine.
  - `tool_match`
  - `numbers_match`, on grade tasks (expected tools include `get_course_grades` or `get_professor_grades`). Every number the answer states must match the reference or the passages it retrieved: GPA to 2 decimals, % within 1 point, counts within 1%. It must also name the reference's first professor. A short answer passes; a wrong or made-up number fails.
- **LLM judges:** the four above. `correctness` is skipped on grade tasks, where `numbers_match` grades the answer.
- **Path metrics:** `rounds`, `tool_call_count`, `redundant_calls`, `tool_error_rate`, `hit_round_limit` and `recovered`. These are recorded but never fail a task.
- **`passed`:** a run passes when every outcome grader that applies passes. Those are `cited_page` (or `not_sure_correct`), `numbers_match` (or `correctness`), and `tool_match`. A judge's "unknown" doesn't count either way.
- **Run metrics** (recorded, never fail a task):
  - `latency_s`: seconds for the attempt that succeeded, so time spent waiting out rate limits isn't counted.
  - `fell_back`: 1 if a vector or hybrid search fell back to keyword search during the run.
  - `wrongly_not_sure`: an answerable task said "not sure" (a false refusal).
  - `answered_out_of_scope`: a `NOT_SURE` task answered anyway (a false answer).
- **Summary:**
  - pass@1 (the average pass rate) with a 95% CI, by source, `set` and tag. The CI comes from a bootstrap over questions (2,000 resamples, seed 0); each question's runs stay together.
  - pass^k (passed all k runs), when k is more than 1.
  - Grader averages, latency p50/p95, and the number of runs with a fallback. A vector or hybrid experiment with any fallbacks isn't valid for comparing search modes.
  - The false refusal and false answer counts.
- **Saved results:** every run is written as one JSON line to `--out PATH`, by default `eval/results/<experiment>.jsonl` (git-ignored). Each line holds the experiment, commit, model, mode, `setup:` line, question id, source, `set`, tags, repetition, `passed` and every other score.
- **Experiment names** follow `<area>-<mode>-<commit>`, e.g. `agent-keyword-537a7f3`.
- **Options:**
  - `--questions <file>` runs one file.
  - `--search-only` keeps only tasks whose expected tools include a `search_*` tool. Those are the only tasks the search mode can change.
  - `--no-judges` uses the code graders only.
  - `--judges correctness` runs only the named judges (comma-separated). `correctness` is the only judge in the pass rule, so this keeps `passed` the same while using a quarter of the judge tokens.
  - `--ids eval/sample-40.txt` runs only the question ids listed in a file (one per line, `#` comments allowed).
  - `--no-upload` runs locally without a LangSmith key.
- **Groq budget:** on the free tier, a full run (about 129 tasks × 3 runs, plus 4 judge calls each) needs far more than one key's 200k tokens a day. Run a file or two at a time, or use a paid tier.

### Merging and comparing results

When a run is split across members, each with their own Groq key, merge everyone's `--out` files into one summary:

```bash
uv run python eval/summarize.py eval/results/agent-keyword-abc1234-*.jsonl
```

It refuses to merge files whose commit, model or mode differ.

Compare two experiments question by question, for example keyword against vector on the same commit:

```bash
uv run python eval/compare.py keyword.jsonl vector.jsonl
uv run python eval/compare.py --a keyword-1.jsonl keyword-2.jsonl --b vector-1.jsonl vector-2.jsonl
```

Only questions on both sides count. For each grader and metric, it prints:

- the mean in A and in B;
- B minus A, with a paired bootstrap 95% CI over questions;
- wins, losses and ties on `passed`.

Each side must be one commit, model and mode, and both sides must share the commit and model.
