# anex.us

**Link:** https://anex.us/grades/ · **Issue:** #18 · **Checked:** October 22, 2026

anex.us is an unofficial, student-built site for Texas A&M grade distributions. You enter a department and course number, and it shows a GPA-by-semester chart for each professor plus a table of every section's grades. It's for students choosing a course or a professor.

## Best way to get the data

1. **Official API:** none. `https://anex.us/api` returns 404.
2. **JSON feed: yes, and this is the one to use.**
   - `POST https://anex.us/grades/getData/` with a form body such as `dept=MATH&number=151`
   - The response is JSON (served as `text/plain`) in the form `{"classes": [ ... ]}`, with one object per section:
     ```json
     {"dept":"CSCE","number":"121","section":"200","prof":"KEYSER J",
      "year":"2015","semester":"SPRING","gpa":"3.69230769230769",
      "A":"10","B":"2","C":"1","D":"0","F":"0","I":"1","Q":"1","S":"0","U":"0","X":"0"}
     ```
   - Every value is a string. `Q` is Q-drops. Sections starting with `2` are honors (the site's own `drawGraph.js` marks them "(H)").
   - It returns every section of the course since Spring 2015, in one response of about 90 KB for a big course.
   - Seen in the Network tab (Fetch/XHR) when you search on the page or open a permalink.
3. **Download / sitemap / RSS:** none. `robots.txt` and `sitemap.xml` both return 404.
4. **HTML:** not usable. The page HTML has only the search form. The chart and table are drawn by JavaScript from the JSON feed.

## How the site is built

- **Pages.** There's really one page. `https://anex.us/` redirects to `https://anex.us/grades/`. Each course has a permalink, which is the same page with a query string:
  - https://anex.us/grades/?dept=MATH&number=151
  - https://anex.us/grades/?dept=CHEM&number=107
  - https://anex.us/grades/?dept=ENGR&number=102
- **JavaScript.** All data loads through JavaScript. A plain HTML scraper gets nothing, so call the feed instead.
- **No other pages.** There is no "about", source or terms page, and no links on the page at all.
- **Dates.** Each row has a year and semester. Data runs from Spring 2015 to Summer 2026 (35 semesters for MATH 151). Fall 2026 isn't in yet because the semester isn't over.
- **How often it changes.** About three times a year. The data looks like it comes from the TAMU Registrar's [grade distribution reports](https://web-as.tamu.edu/gradereports), which come out in late December, mid-May and mid-August. anex.us doesn't say where its data comes from, so that's our guess.
- **Size.** There's one feed result per course, which probably means thousands of courses. The exact number is unknown because there's no list of courses.

## Feed behavior to know about

- **No course list.** You have to already know the department and number, so the course list would come from the Course Catalog (#17).
- **Department must be uppercase.** The site's JavaScript uppercases it before sending. Lowercase `csce` returns broken JSON (`{"classes":]}`), and a course that doesn't exist returns the same thing.
- **Course number is required.** Leaving out the number returns `400 Error`.
- **POST only.** A GET request to `getData` returns `405`.
- **Professor names** look like `MASHBURN J` (last name plus first initial), so linking them to RateMyProfessors (#19) will need fuzzy matching.

## 10 questions it answers

These are worked out from the feed: GPAs are weighted by students (A–F count), and "since 2023" counts professors with at least 50 graded students.

| # | Question | Answer | Link |
|---|---|---|---|
| 1 | What's the average GPA in MATH 151? | 2.79 (Spring 2015 to Summer 2026) | https://anex.us/grades/?dept=MATH&number=151 |
| 2 | Is MATH 152 harder than MATH 151? | By GPA, a little: 2.68 vs 2.79 | https://anex.us/grades/?dept=MATH&number=152 |
| 3 | Which CHEM 107 professor has the highest GPA lately? | MARTINEZ Z, 3.33 since 2023 (852 students) | https://anex.us/grades/?dept=CHEM&number=107 |
| 4 | Which PHYS 206 professor has the highest GPA lately? | MAHAPATRA R, 3.38 since 2023 (639 students) | https://anex.us/grades/?dept=PHYS&number=206 |
| 5 | Who should I take for POLS 206? | NEDERMAN C has the highest GPA since 2023, 3.85 (1,937 students) | https://anex.us/grades/?dept=POLS&number=206 |
| 6 | How many people get an A in STAT 211? | 44.5% of A–F grades; average GPA 3.16 | https://anex.us/grades/?dept=STAT&number=211 |
| 7 | Do many people Q-drop ACCT 229? | Yes: about 15% of students Q-drop, the most of the courses checked | https://anex.us/grades/?dept=ACCT&number=229 |
| 8 | Is CSCE 121 still taught? | Last data is Summer 2024. CSCE 120 data starts Fall 2021, so it may have replaced 121 (Unknown; check the catalog) | https://anex.us/grades/?dept=CSCE&number=121 |
| 9 | How many professors teach ENGR 102? | 38 have taught it since 2023 | https://anex.us/grades/?dept=ENGR&number=102 |
| 10 | Which HIST 105 professor has the highest GPA lately? | HERZOGENRATH J, 3.80 since 2023 (195 students) | https://anex.us/grades/?dept=HIST&number=105 |

## Missing, outdated or confusing

- There's no source, license or terms of use anywhere on the site, and the site is unofficial.
- The site has no course or department list, and you can't search by professor.
- A bad input returns broken JSON instead of a clear error.
- A high GPA doesn't mean a professor is better. Sample sizes vary a lot (79 students vs 1,900).
- The Registrar only posts the five most recent years (2021–2026), while anex.us goes back to 2015. The older data can't be checked against an official source.

## How we could use it

- **Use:** answer "what's the GPA in this course / with this professor" questions, and link students to the anex.us permalink for the chart.
- **Plan:** take the course list from the Course Catalog → make one POST per course → save the JSON under `data/raw/anex/` → refresh about three times a year (late Dec, mid-May, mid-Aug).
- **Difficulty: easy.** The data is already clean JSON with one request per course. The main work is the course list and matching professor names.
- **Ask a PM first:** the site has no terms, so check whether we may collect and store its data, and keep requests slow if we do. The official fallback is the Registrar's [PDF reports](https://web-as.tamu.edu/gradereports), which cover only five years and are harder to parse.
- **Sensitivity:** low. The data is grade counts per section and instructor names, with no student information.

## Links checked

- https://anex.us/ redirects to https://anex.us/grades/ (the search form only)
- https://anex.us/grades/?dept=MATH&number=151 auto-runs the search and shows the chart and the table (2026 sections at the top)
- https://anex.us/grades/?dept=CSCE&number=121 has Summer 2024 as its newest row
- https://anex.us/grades/?dept=POLS&number=206 lists NEDERMAN C sections and has Summer 2026 rows
- `POST https://anex.us/grades/getData/` returns the JSON above. MATH 151, MATH 152, CHEM 107, PHYS 206, POLS 206, STAT 211, ACCT 229, CSCE 120/121, ENGR 102 and HIST 105 were all checked through it.
- https://anex.us/grades/drawGraph.js shows how the page calls the feed, the uppercase rule and the honors rule
- https://anex.us/robots.txt and https://anex.us/sitemap.xml both return 404
- https://web-as.tamu.edu/gradereports confirms the five-year window and the release schedule
