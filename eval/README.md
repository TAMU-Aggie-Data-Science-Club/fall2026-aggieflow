# Eval questions

Each file in `eval/questions/` holds test tasks, one JSON object per line. `eval/score.py` reads every file. The judges (#71), routing tests (#72) and eval runner (#73) read them too.

## Fields

| Field | Required | Meaning | Example |
|---|---|---|---|
| `id` | yes | Unique, stable id | `"student-rules-rushilsagar-01"` |
| `question` | yes | What the student types | `"how many q drops do i get"` |
| `answer` | yes | The correct answer, or `"NOT_SURE"` if our sources can't answer it | `"Four..."` |
| `source_url` | yes | The page that answers it (`null` for `NOT_SURE`) | `"https://student-rules.tamu.edu/rule01/"` |
| `tools` | no | Tools the agent should call. `[]` means none. | `["search_student_rules"]` |
| `args` | no | Expected tool arguments | `{"course": "MATH 151"}` |
| `set` | no | `regression` (should always pass) or `capability` (hard) | `"capability"` |
| `tags` | no | Labels for slicing results | `["paraphrase"]` |

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

The judge model is `groq:qwen/qwen3.8-27b` at temperature 0, which is a different model family from the agent's `gpt-oss-20b`. If you change it, calibrate again.

**Calibrate before you trust them:**

1. Run `uv run python eval/calibrate.py --make`. It runs the agent on 20 fixed questions (3 of them `NOT_SURE`) and writes `eval/calibration.jsonl`.
2. Set every value under `labels` in that file to `"yes"`, `"no"` or `"unknown"`, using your own judgment. Read the `answer`, the `reference` and the `documents`.
3. Run `uv run python eval/calibrate.py`. It prints the agreement for each judge, and every judge needs at least 85%. Where a judge disagrees with you, its reasoning is printed. Fix that judge's prompt and run it again.
