# Texas A&M Student Rules

**Link:** https://student-rules.tamu.edu · **Issue:** #14 · **Checked:** October 26, 2026

The official handbook of Texas A&M student rules, run by the Office of the Vice President for Student Affairs. It covers academic rules (registration, Q-drops, attendance, exams, grading, honors), student life rules (conduct, housing, parking, organizations) and grievance and appeal procedures. It's for students, faculty and staff.

## Best way to get the data

1. **Official API: yes.** The site runs on WordPress, and its public REST API is on.
   - Every page, with its full text: `https://student-rules.tamu.edu/wp-json/wp/v2/pages?per_page=100`
   - One rule: `https://student-rules.tamu.edu/wp-json/wp/v2/pages?slug=rule07`
   - Keyword search: `https://student-rules.tamu.edu/wp-json/wp/v2/search?search=Q-drop` returns the matching rules with links.
   - Each page has `id`, `slug`, `link`, `title.rendered`, `content.rendered` (the rule text as HTML) and `modified` (when it was last edited). Add `&_fields=slug,link,title,modified,content` to keep the response small.
   - There are 81 pages in total (from the `X-WP-Total` header), and all of them fit in one request with `per_page=100`.
2. **JSON feed:** none needed beyond the REST API. The Network tab shows nothing extra.
3. **Sitemap: yes.** https://student-rules.tamu.edu/wp-sitemap.xml lists the same 81 pages. `robots.txt` points to it and sets `Crawl-delay: 10`.
4. **RSS:** https://student-rules.tamu.edu/feed/ exists but has no items, because the site has no blog posts.
5. **HTML:** also works. The rule text is in the page HTML, so no JavaScript is needed.

## How the site is built

- **One page per rule.** The URLs are flat, like `/rule01/` to `/rule62/`. Some numbers are skipped because those rules were removed (for example 30, 33, 34, 43 and 56).
  - https://student-rules.tamu.edu/rule01/ (Registration, including Q-drops)
  - https://student-rules.tamu.edu/rule07/ (Attendance)
  - https://student-rules.tamu.edu/rule10/ (Grading)
- **Section index pages:**
  - https://student-rules.tamu.edu/academic-rules/
  - https://student-rules.tamu.edu/student-life-rules/
  - https://student-rules.tamu.edu/student-grievance-procedures/
- **Appendices** (laws and policies on hazing, alcohol, FERPA, free speech and more):
  - https://student-rules.tamu.edu/appendices/
  - https://student-rules.tamu.edu/appendix-vi/
  - https://student-rules.tamu.edu/appendix-xi/
- **Other pages:**
  - Recent changes: https://student-rules.tamu.edu/changes/
  - Review committee minutes: https://student-rules.tamu.edu/minutes/
  - Campus contacts: https://student-rules.tamu.edu/campus-contacts/
- **Text format.** Rules are numbered sections in plain text, like `1.18.4` or `7.3.1.1`. The sections have no HTML anchors, so we can't link straight to a section. To split a rule into sections, use the section numbers in the text.
- **Dates:**
  - The API's `modified` field shows when each page was last edited. Edits run from December 2025 to October 2026.
  - The [changes page](https://student-rules.tamu.edu/changes/) lists each rule change with its approval and effective dates. The most recent is Rule 31, effective 09/30/26.
- **How often it changes.** A few times a year, mostly at the start of the academic year. For example, Rules 1, 10, 15, 41 and 42 changed on 08/20/26.
- **Size.** 81 pages: 57 rules, 11 appendices and 13 index and info pages. Long rules are big; Rule 10 is about 26,000 characters.

## 10 questions it answers

| # | Question | Answer | Link |
|---|---|---|---|
| 1 | How many Q-drops do I get? | 4 as an undergrad (Rule 1.18.4). State law caps dropped courses at 6 across all Texas schools. One-hour courses don't count toward the 4, and a lecture and its lab dropped together count as one. | https://student-rules.tamu.edu/rule01/ |
| 2 | What's the most hours I can take? | 19 in fall or spring, and 14 across all summer sessions (Rule 1.13.1) | https://student-rules.tamu.edu/rule01/ |
| 3 | How do I get an absence excused? | Tell the instructor in writing (email is fine) before the day you're absent (Rule 7.1.1) | https://student-rules.tamu.edu/rule07/ |
| 4 | When is my absence documentation due? | Within 3 business days of the last day of the absence (Rule 7.3.1.1) | https://student-rules.tamu.edu/rule07/ |
| 5 | How long do I have to make up missed work? | No more than 30 calendar days from the last day of the absence. Title IX cases can get longer. | https://student-rules.tamu.edu/rule07/ |
| 6 | I have three finals in one day. What can I do? | You can ask to reschedule one of them (Rule 8.4) | https://student-rules.tamu.edu/rule08/ |
| 7 | How long can a final exam be? | No more than 2 hours (Rule 8.2.1). Finals aren't required at all (Rule 8.1). | https://student-rules.tamu.edu/rule08/ |
| 8 | What GPA do I need for Latin honors? | Cum Laude 3.50–3.699, Magna Cum Laude 3.70–3.899, Summa Cum Laude 3.90+ (Rule 15.4). You also need at least 60 hours at Texas A&M (Rule 15.1). | https://student-rules.tamu.edu/rule15/ |
| 9 | When am I scholastically deficient? | When your semester GPA, cumulative GPA or major GPA is below 2.00 (Rule 12.1) | https://student-rules.tamu.edu/rule12/ |
| 10 | How many hours do I need to be a sophomore, junior or senior? | 30, 60 and 90 hours (Rule 13.1.2) | https://student-rules.tamu.edu/rule13/ |

## Missing, outdated or confusing

- **No links to sections.** You can only link to a whole rule, and some rules are very long.
- **Missing rule numbers.** Some rules were removed, so a number like 56 has no page, and Part III lists "56. Rule Removed 2025-2026".
- **Rules point elsewhere.** Some rules depend on other sites. For example, Q-drop deadlines are on the Registrar's calendar, and some details are only in university SAPs or System policies.
- **The text is all mixed together.** Undergraduate, graduate and professional (medicine, law, dentistry) rules are in the same pages. The assistant needs to give students the undergraduate rule unless they say otherwise.
- **Rules change mid-year.** An answer saved in August can be out of date by October, so the assistant should show the `modified` date with its answers.

## How we could use it

- **Use:** answer policy questions (Q-drops, absences, finals, honors, probation) with the exact rule number and a link.
- **Plan:** one request to `/wp-json/wp/v2/pages?per_page=100` → strip the HTML → split each rule by section number (`7.3.1.1`) → index the sections for search → re-fetch weekly, or only pages whose `modified` date changed.
- **Difficulty: easy.** It's an official API that returns clean JSON in one request, and the text is already split into numbered sections.
- **Permission:** it's a public, official TAMU site with no login. Respect `Crawl-delay: 10`. One request a week is far below that.
- **Sensitivity:** none. These are published policies with no personal data.

## Links checked

- https://student-rules.tamu.edu/ lists Parts I–III, the appendices and the links to changes and minutes
- https://student-rules.tamu.edu/wp-json/wp/v2/pages?per_page=100 returns 81 pages, with `X-WP-Total: 81`
- https://student-rules.tamu.edu/wp-json/wp/v2/search?search=Q-drop returns Rules 17, 11, 10, 8 and 1
- https://student-rules.tamu.edu/robots.txt shows `Crawl-delay: 10` and the sitemap link
- https://student-rules.tamu.edu/wp-sitemap.xml lists 81 page URLs
- https://student-rules.tamu.edu/rule01/ has Rule 1.18.4 (4 Q-drops, state limit of 6) and Rule 1.13.1 (19 and 14 hours), and the text is in the HTML
- https://student-rules.tamu.edu/rule07/ has Rules 7.1.1 and 7.3.1.1 and the 30-day make-up limit
- https://student-rules.tamu.edu/rule08/ has Rules 8.1, 8.2.1 and 8.4
- https://student-rules.tamu.edu/rule15/ has Rule 15.4 (the honors GPA ranges)
- https://student-rules.tamu.edu/changes/ shows Rule 31 changed 09/30/26 and Rules 1, 10, 15 and 41/42 changed 08/20/26
