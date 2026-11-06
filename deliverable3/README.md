# Deliverable 3: Collect your source

**Issue:** see the [deliverable-3 issues](https://github.com/TAMU-Aggie-Data-Science-Club/fall2026-aggieflow/issues?q=is%3Aopen+label%3Adeliverable-3) · **Due:** Sunday, November 15, 2026 · **Time:** about 4 hours

In Deliverable 2 you mapped a source. This week you write the code that collects its data. You'll also write the questions we'll use to test AggieFlow. By the end of the week we'll have real data from every source, all in one format, plus a test set to score the assistant against.

There are two tracks. Everyone does **Part 2**.

- **Track A: Collector.** You mapped Anex, the Course Catalog, Technology Services, the Registrar, Student Rules, or Transportation. Write a collector for that source.
- **Track B: Shared piece.** You mapped Reddit or RateMyProfessors, or you didn't map a source. Build one of the shared tools that every source needs (see [Track B](#track-b-shared-pieces)). Reddit and RateMyProfessors are on hold while the PMs review their terms of use, so don't collect from them.

## Setup

```bash
git switch main
git pull
git switch -c issue-<n>/<you>
pip install requests beautifulsoup4
```

`<n>` is your issue number and `<you>` is your GitHub username in lowercase. Only use Playwright (`pip install playwright`) if your source's text loads only with JavaScript.

---

## Part 1, Track A: Write a collector

Your collector is one Python file, `pipeline/collect/<source>.py`. Running it fetches your source and writes two outputs:

| Output | What goes in it |
|---|---|
| `data/raw/<source>/` | Exactly what the site returned (JSON, HTML, XML), one file per request. Never edit these. |
| `data/processed/<source>.jsonl` | Clean passages, one JSON object per line, in the format below. |

Use the source names from Deliverable 2: `anex`, `catalog`, `oal`, `registrar`, `student-rules`, `transportation`.

### Passage format

Every line of `data/processed/<source>.jsonl` is one passage:

```json
{"id": "student-rules:rule07:3", "source": "student-rules", "title": "Rule 7: Attendance", "text": "An absence is considered excused when...", "source_url": "https://student-rules.tamu.edu/rule07/", "fetched_at": "2026-11-10T18:04:00Z"}
```

| Field | Rule |
|---|---|
| `id` | `<source>:<page key>:<chunk number>`. It must be the same every time you run the collector, so re-runs replace passages instead of duplicating them. Use something stable from the site (a slug, a course code), not a counter over the whole run. |
| `source` | Your source name, exactly as listed above. |
| `title` | The page title or section heading the passage comes from. |
| `text` | Plain text: no HTML tags, no menus, headers, or footers. About 100–400 words. Split long pages at headings. Don't cut a sentence in half. |
| `source_url` | The page a student should open to check the answer. This is the citation, so it must be a real page and not an API URL. |
| `fetched_at` | When you fetched it, in UTC ISO 8601 (`2026-11-10T18:04:00Z`). |

Track B is building a checker and a loader against this format, so stick to it exactly. Don't add or rename fields. If you think a field is missing, raise it in the team chat.

### Steps

1. **Start from your report.** Use the best access method your Deliverable 2 report found: official API, then JSON feed, then sitemap, then plain HTML. JavaScript pages come last.
2. **Fetch a few pages first.** Save the raw responses, then check that you're getting the text you expect.
3. **Turn raw data into passages.** Strip the HTML, split long pages, and write the JSONL.
4. **Run it on everything.** Then open `data/processed/<source>.jsonl` and read 10 random lines. Is each one readable on its own? Does its link open the right page?
5. **Add your source to [`DATA.md`](../DATA.md).** Add a row to the source register and fill in every column. Put `TBD` for anything you don't know, and mention it in your PR.

### Rules

- **Be polite to the site.** Wait at least 1 second between requests. Use the API, feed, or sitemap from your report instead of crawling every link.
- **Public pages only.** Nothing behind a NetID login.
- **Commit the code, never the data.** `data/` is git-ignored. Never force-add anything from it.
- **One command.** `python pipeline/collect/<source>.py` with no arguments should rebuild both outputs from scratch.

### Tips by source

- **Course Catalog:** there are 10,000+ courses. Get one subject working before running all of them, and add a `--limit` option for testing. Degree plans are plain HTML pages listed in `sitemap.xml`.
- **Student Rules:** the WordPress API returns every rule in one request. Split each rule at its numbered subsections.
- **Anex:** the data is numbers, not text. Turn each course and professor into a short sentence, for example "CSCE 120 with Prof. X, Fall 2025: 42% A, 30% B, …". Use the Anex search page for that course as the `source_url`.
- **Transportation:** collect the static pages (parking, routes, policies). Skip live bus times, since they're out of date within minutes.
- **Registrar and Technology Services:** use `sitemap.xml` to list pages, then pull the main content area of each page.

---

## Part 1, Track B: Shared pieces

Claim one piece by assigning yourself to its issue. Each piece takes up to two people.

| Piece | What you build | Done when |
|---|---|---|
| **Database** | `docker-compose.yml` that starts PostgreSQL with pgvector, plus `pipeline/db/schema.sql` with a `passages` table that has a column for each passage field, plus an `embedding` column we'll fill later. | `docker compose up` starts the database, and the schema loads with no errors. |
| **Loader** | `pipeline/load.py` reads every `data/processed/*.jsonl` file and inserts the passages, replacing any passage with the same `id`. | Running it twice leaves the same number of rows. It prints a count per source. |
| **Checker** | `pipeline/check.py <file.jsonl>` checks a processed file against the passage format: required fields, ID format, duplicate IDs, empty or huge `text`, and HTML tags left in. | It catches every problem in a bad file you make up. Track A people can run it on their own output. |
| **Scorer** | `eval/score.py` runs every question in `eval/questions/` through an answer function and reports how many answers cite the expected `source_url` and how many "not sure" questions were correctly answered "not sure". | It works with a dummy answer function, and it works with your Deliverable 1 agent. |

Write your piece against the formats in this file, not against someone else's code. Until real data lands, test with a small JSONL file you make yourself.

---

## Part 2: Ten test questions (everyone)

Write 10 questions that a TAMU student might ask, each with its correct answer and the page that shows it. Save them as `eval/questions/<source>-<you>.jsonl`.

- **If you mapped a source:** start from the 10 questions in section 7 of your report. Open every link and check that the answer is really there and still correct, because AI made some of them up. Fix or replace any that are wrong.
- **If you didn't map a source:** pick any official source above and write 10 questions from its pages.

Each line is one question:

```json
{"id": "student-rules-rushilsagar-01", "question": "How many days do I have to turn in a doctor's note for an excused absence?", "answer": "Within two working days of returning to class.", "source_url": "https://student-rules.tamu.edu/rule07/"}
```

- Write the questions the way students actually ask them ("when's q drop"), not the way the site phrases them.
- Make at least 1 of your 10 a question your source **can't** answer. Set `"answer": "NOT_SURE"` and `"source_url": null`. AggieFlow should say it isn't sure instead of guessing.
- Don't tune anything against these questions yet. The PMs will set some aside for the final evaluation.

---

## Submit

Commit your code and your questions file, but nothing from `data/`. Push your branch and open a pull request into `main` with `Closes #<n>` in the description.

## Done when

**Track A**
- [ ] `python pipeline/collect/<source>.py` rebuilds `data/raw/<source>/` and `data/processed/<source>.jsonl`
- [ ] Every passage follows the passage format, and you spot-checked 10 of them
- [ ] Your source has a complete row in `DATA.md`

**Track B**
- [ ] Your piece meets its "Done when" in the table above

**Everyone**
- [ ] `eval/questions/<source>-<you>.jsonl` has 10 checked questions, including at least 1 `NOT_SURE`
- [ ] Nothing under `data/` is committed
- [ ] Your pull request says `Closes #<n>` and is open by the due date

Stuck? Post the command you ran and the full error in the team chat.
