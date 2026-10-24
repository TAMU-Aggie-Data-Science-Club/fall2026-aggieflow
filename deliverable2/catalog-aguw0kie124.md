# TAMU Course Catalog

**Link:** https://catalog.tamu.edu · **Issue:** #17 · **Checked:** October 24, 2026

The official Texas A&M catalog, published once a year (currently the 2026-2027 edition). It has every course description, every degree plan, minor, and certificate, the University Core Curriculum, and academic policies. It runs on CourseLeaf, a common catalog system.

## Best way to get the data

1. **Official API:** none documented.
2. **JSON feed: yes, for courses.** The catalog's course search uses a CourseLeaf JSON API:
   - **All courses in one request:** `POST https://catalog.tamu.edu/course-search/api/?page=fose&route=search` with the body `{"other":{"srcdb":"2026"},"criteria":[]}`. It returns all 10,236 courses for 2026-2027 (278 subjects) as `{"key","code","title","srcdb"}`, about 1 MB.
   - **Filter by subject:** add `{"field":"subject","value":"CSCE"}` to `criteria` (151 CSCE courses).
   - **One course's details:** `POST .../api/?page=fose&route=details` with `{"group":"code:CSCE 121","key":"key:2026","srcdb":"2026","matched":"key:2026"}`. It returns `title` plus `description` as HTML, which holds credits, lecture/lab hours, the description, and prerequisites as text.
   - **Catalog years:** `srcdb` takes `2026`, `2025`, `2024`, or `2023`, so course data covers 2023-2024 through 2026-2027.
   - Seen in the Network tab when searching on https://catalog.tamu.edu/course-search/.
3. **Sitemap: yes.** https://catalog.tamu.edu/sitemap.xml lists 1,575 pages with last-modified dates. It is the easiest way to get every degree plan URL.
4. **Download:** a full PDF of each catalog (`/pdf/2026-2027_undergraduate.pdf`, `/pdf/2026-2027_graduate.pdf`). Useful as a backup, but harder to parse than the HTML.
5. **HTML: yes, for degree plans and policies.** Pages are plain HTML (no JavaScript needed). Degree plans use consistent CourseLeaf tables (`sc_plangrid` for the semester-by-semester plan, `sc_courselist` for course lists), and every course code is a link with `title="CSCE 121"`, so courses are easy to pull out.

## How the site is built

- **Course descriptions:** one page per subject, for example https://catalog.tamu.edu/undergraduate/course-descriptions/csce/ (198 undergraduate and 187 graduate subject pages). The JSON feed above is easier.
- **Degree plans, minors, certificates:** `/undergraduate/<college>/<department>/<program>/`, for example:
  - https://catalog.tamu.edu/undergraduate/engineering/computer-science/bs/
  - https://catalog.tamu.edu/undergraduate/engineering/computer-science/cybersecurity-minor/
  - https://catalog.tamu.edu/graduate/colleges-schools-interdisciplinary/engineering/computer-science/ms/
- **Core curriculum and degree rules:** https://catalog.tamu.edu/undergraduate/general-information/university-core-curriculum/ lists the courses for each of the 8 core areas (288 course entries).
- **Academic calendar:** https://catalog.tamu.edu/undergraduate/academic-calendar/
- **Older catalog years:** https://catalog.tamu.edu/archives/ has HTML editions back to 2015-2016 (`/archives/2025-2026/` and so on).
- **robots.txt:** disallows `/archives/`, `/search/`, `/ribbit/`, `/pdf/`, and admin paths. `/course-search/` (the JSON API) is not disallowed.

## Dates, changes, and size

- **Catalog year is on every page** ("2026-2027 Edition"), so each degree plan can be tagged with its year.
- **Changes once a year.** The sitemap's last-modified dates cluster in March and April 2026, before the 2026-2027 edition was published.
- **Size:** 10,236 courses. The undergraduate catalog has 415 program-level pages (73 BS, 25 BA, 4 BBA, 114 minors, 41 certificates, plus combined degrees and department pages), and the graduate catalog has about 500 more.

## 10 questions it answers

| # | Question | Answer | Link |
|---|---|---|---|
| 1 | Which courses satisfy my humanities core requirement? | The "Language, Philosophy and Culture" area (3 hours) lists 109 courses, such as ENGL 202, PHIL 111, and HIST 210 | https://catalog.tamu.edu/undergraduate/general-information/university-core-curriculum/ |
| 2 | How many hours is the core curriculum? | 42 semester credit hours across 8 areas | https://catalog.tamu.edu/undergraduate/general-information/university-core-curriculum/ |
| 3 | What are the prerequisites for CSCE 121? | A programming course (high school or college). It is 4 credits: 3 lecture and 2 lab hours | https://catalog.tamu.edu/undergraduate/course-descriptions/csce/ |
| 4 | Is CSCE 121 still offered? | Yes, it is in the 2026-2027 catalog along with CSCE 120. anex.us (#18) shows no grades for it after Summer 2024 | https://catalog.tamu.edu/course-search/ |
| 5 | What do Computer Science BS students take their first fall? | CHEM 107 and 117, ENGL 103 or 104, ENGR 102, MATH 151, and a core course (16 hours) | https://catalog.tamu.edu/undergraduate/engineering/computer-science/bs/ |
| 6 | What is the capstone for Computer Science BS? | CSCE 482 Senior Capstone Design, in the final spring | https://catalog.tamu.edu/undergraduate/engineering/computer-science/bs/ |
| 7 | Is there a cybersecurity minor? | Yes | https://catalog.tamu.edu/undergraduate/engineering/computer-science/cybersecurity-minor/ |
| 8 | How many CSCE courses are there? | 151 in 2026-2027 (165 in 2023-2024) | https://catalog.tamu.edu/course-search/ |
| 9 | When is Thanksgiving break in Fall 2026? | November 26-27, with November 25 a reading day (no classes) | https://catalog.tamu.edu/undergraduate/academic-calendar/ |
| 10 | Can I see the degree plan from the year I started? | Yes, archived catalogs go back to 2015-2016 | https://catalog.tamu.edu/archives/ |

## Missing, outdated, or confusing

- Prerequisites are free text inside the description ("Prerequisite: ..."), not a separate field, so they need parsing.
- The JSON feed only covers 2023-2024 onward. Older years exist only as archived HTML.
- Degree plans mix the semester grid with long footnotes (numbers after course codes, like `MATH 151 1,2`), which matter for the actual rules.
- "University Core Curriculum" placeholders in degree plans point back to the core page, so answering "what can I take here" means joining two pages.
- Course codes change over time (for example CSCE 120 and 121 both exist), so a course's history needs the catalog year.

## How we could use it

- **Use:** this is the backbone. It answers degree-plan and requirement questions, and its course list is what anex.us (#18) needs, since anex.us has no list of its own. Course codes are also the key that joins grades (anex.us) and professors (RateMyProfessors, #19).
- **Plan:**
  1. Courses: one search request per catalog year, then one details request per course. Store code, title, credits, description, prerequisites text, and catalog year in a `courses` table.
  2. Degree plans and policies: get URLs from the sitemap, fetch the HTML, and store each page as a document tagged with program and catalog year. Pull course codes out of the `sc_courselist` and `sc_plangrid` tables.
  3. Core curriculum: turn the 8 course lists into a course-to-core-area table.
  4. Refresh once a year (after the new edition comes out in spring), plus a sitemap check for changes.
- **Difficulty: medium.** Courses are easy (clean JSON). Degree plans are consistent HTML but have footnotes and "select one of" rules that need care.
- **Sensitivity:** none. It is official public information.

## Links checked

- https://catalog.tamu.edu/robots.txt and https://catalog.tamu.edu/sitemap.xml (1,575 URLs)
- https://catalog.tamu.edu/course-search/ (the term list and subject list are in the page source)
- `POST .../course-search/api/?page=fose&route=search` for all courses (10,236), CSCE in 2026 (151), and CSCE in 2023 (165)
- `POST .../course-search/api/?page=fose&route=details` for CSCE 121
- https://catalog.tamu.edu/undergraduate/engineering/computer-science/bs/ (plan grid, first-year courses, CSCE 482)
- https://catalog.tamu.edu/undergraduate/general-information/university-core-curriculum/ (8 areas, 109 Language, Philosophy and Culture courses)
- https://catalog.tamu.edu/undergraduate/academic-calendar/ (Fall 2026 dates)
- https://catalog.tamu.edu/archives/ (editions from 2015-2016 to 2025-2026)
