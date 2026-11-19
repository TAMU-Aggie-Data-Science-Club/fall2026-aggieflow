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
