# Faculty and department pages

**Bonus from #deliverables (Oct 25):** map faculty and department pages so AggieFlow can answer questions like a professor's office, contact and research. Texas A&M has no single faculty directory site we can use, so this covers the three biggest colleges' directories, checked Nov 22, 2026.

| College | Directory | Feed |
|---|---|---|
| Engineering | https://engineering.tamu.edu/cse/profiles/index.html (one per department) | `https://engineering.tamu.edu/profile-data.json` |
| Arts & Sciences (math, physics, chemistry, biology, English, history and the other core-course departments) | https://artsci.tamu.edu/mathematics/contact/faculty.html (one per department) | `https://artsci.tamu.edu/profile-data.json` |
| Mays Business School | https://mays.tamu.edu/faculty/ | `https://mays.tamu.edu/wp-json/wp/v2/person` (list only) |

## Best way to get the data

1. **Official API:** none.
2. **JSON feeds (best option):** Engineering and Arts & Sciences run the same website system, and each department's directory page loads one college-wide JSON file in the Network tab (Fetch/XHR). No login, no key.
   - **Engineering, `profile-data.json`** (1.2 MB): **1,578 people**, one object each with `name`, `titles`, `tag` (department and role, like `["csce", "Faculty"]`), `office`, `phone`, `email` and `link` (the profile page). Roles: 762 Faculty, 259 Affiliated, 142 Emeritus, 284 Staff, 44 Research Staff, and a few others. 13 departments, from Mechanical (186) to Ocean (49). **No students.**
   - **Arts & Sciences, `profile-data.json`**: **3,085 people** with the same fields plus `researchAreas` and `interests`. Each department page also loads its own slice (for example `mathematics/contact/profiles/dept-profile-data.json`). Roles: 1,022 Faculty, 193 Emeritus, 307 Staff, 115 Research Staff, and others, **but also about 990 students** (886 Graduate Student, 105 PhD Student, a few Master's). 292 entries are tagged with a department called `test`. `researchAreas` is filled in for only 111 people and `interests` for 780.
   - **Mays, WordPress REST API**: `wp-json/wp/v2/person` lists **574 people** (faculty and staff) with their profile `link`, but the details (title, department, email) aren't in the API; they're in each profile page's HTML.
3. **Sitemap:** not checked for these sites; the JSON feeds already list every profile page.
4. **Plain HTML:** every profile page I opened has its text in the HTML.
   - Engineering profiles are the richest: title, phone, email, office, then Educational Background, Research Interests, Awards & Honors and Selected Publications (about 200 words).
   - Arts & Sciences profiles are short (one I opened was 27 words): title, contact, office, research areas and interests, and often a link to a CV.
   - Mays profiles: not opened beyond the directory.
5. **JavaScript-only:** the directory pages' A–Z filters are built from the JSON feeds, but the profile pages themselves aren't.

## Office hours: not on these pages

None of the profiles I opened lists office hours. Office hours are in course **syllabi**, which Texas law (HB 2504, now Texas Education Code 51.974) requires universities to make public along with instructors' CVs. At Texas A&M the public route to them goes through Howdy's public class search (https://howdy.tamu.edu/uPortal/p/public-class-search-ui.ctf1/max/render.uP). On Nov 22 that page showed a Cloudflare "verifying you are not a bot" page that never cleared in the browser, and academicaffairs.tamu.edu's page about the law returned an error, so **whether syllabi can be collected is Unknown**. A script shouldn't try to get past a bot check; if office hours matter, ask the Registrar or the PMs whether there's an approved way.

## Dates and freshness

- Profiles show no last-updated date. They change when people are hired, leave or move offices, so about once a semester; refresh the feeds at the start of each semester.
- Some Engineering profiles name recent awards (one lists a 2026 teaching award), so the pages are maintained.

## Size

About 5,200 entries across the three colleges. Faculty roles alone: 1,163 in Engineering (counting affiliated and emeritus) and about 1,360 in Arts & Sciences, plus Mays's faculty among its 574 people. Other colleges (Agriculture, Architecture, Education, Medicine, Vet Med, Bush School, Law, Public Health, Nursing...) have their own sites and weren't mapped. The university-wide `directory.tamu.edu` people search wasn't mapped either: it includes students.

## 10 questions this source answers

Checked on 2026-11-22.

| # | Question | Answer | Link |
|---|---|---|---|
| 1 | where is professor teresa leyk's office | PETR 106. | https://engineering.tamu.edu/cse/profiles/tleyk.html |
| 2 | what else does teresa leyk do besides teach | She supervises the Peer Teacher Program in Computer Science & Engineering. | https://engineering.tamu.edu/cse/profiles/tleyk.html |
| 3 | where did leyk get her phd | Ph.D. in Mathematics from the Australian National University. | https://engineering.tamu.edu/cse/profiles/tleyk.html |
| 4 | has teresa leyk won teaching awards | Yes: the Engineering Teaching Impact Award (2026) and the Undergraduate Faculty Teaching Excellence Award (2024 and 2012). | https://engineering.tamu.edu/cse/profiles/tleyk.html |
| 5 | where's zbigniew leyk's office | PETR 117. He's a Professor of Practice in Computer Science & Engineering. | https://engineering.tamu.edu/cse/profiles/leyk-zbigniew.html |
| 6 | what does ariful azad research | High-performance computing, graph algorithms, graph machine learning and bioinformatics. | https://engineering.tamu.edu/cse/profiles/azad-ariful.html |
| 7 | how do i email ariful azad | ariful@tamu.edu (office PETR 215). | https://engineering.tamu.edu/cse/profiles/azad-ariful.html |
| 8 | where is professor demlow's office | Blocker 507D. | https://artsci.tamu.edu/mathematics/contact/profiles/alan-demlow.html |
| 9 | what kind of math does alan demlow research | Numerical analysis of partial differential equations. | https://artsci.tamu.edu/mathematics/contact/profiles/alan-demlow.html |
| 10 | what are professor leyk's office hours | Not on her profile. Office hours are on the course syllabus (see "Office hours" above). | https://engineering.tamu.edu/cse/profiles/tleyk.html |

Question 10 is one AggieFlow should answer "not sure" (pointing to the syllabus) unless syllabi are collected.

## Missing, outdated or confusing

- **Students in the Arts & Sciences feed.** About 990 graduate and PhD students are listed with office and email. They're on a public page, but students aren't what this source is for: a collector should keep only faculty roles.
- **Test data in production.** 292 Arts & Sciences entries are tagged with a department called `test`.
- **Two professors share a last name.** Teresa and Zbigniew Leyk are both in Computer Science & Engineering, so a tool must ask which one (the same case as the ratings tool's "Which Professor Leyk?").
- **Department tags are short codes** (`csce`, `etid`, `comm-journalism`), and a few are inconsistent (`cse` and `ce` once each in Engineering, `materials` and `materials science and engineering`).
- **No office hours** anywhere on these pages, which was the first feature the bonus mentioned.
- Mays's REST API lists people but hides the details, so Mays needs one page request per person.

## How we could use it

- **A live or daily lookup tool,** `get_professor(name)`: read the two JSON feeds once a day, keep faculty roles only, and match by name (asking which one when two match). Return title, department, office, email and the profile link as the citation. Easy: two requests a day, clean JSON, no parsing.
- **Research interests:** add Engineering's Research Interests section and Arts & Sciences' `researchAreas`/`interests`, so "who researches machine learning in CSCE" works. Medium: Engineering needs one HTML page per profile (about 1,160 faculty pages at 1 per second, about 20 minutes).
- **Pair it with the ratings and grades tools:** "is Leyk good and where's her office" becomes one answer, with each fact cited to its page.
- **Office hours:** out of reach until syllabi are available without a bot check.
- **Sensitivity:** names, offices, work emails and phone numbers of employees, published on official pages. Keep students out, and don't store photos.

## Links I checked by hand

- https://engineering.tamu.edu/cse/profiles/index.html (loads `profile-data.json`)
- https://engineering.tamu.edu/profile-data.json (1,578 entries; both Leyks present)
- https://engineering.tamu.edu/cse/profiles/tleyk.html
- https://engineering.tamu.edu/cse/profiles/azad-ariful.html
- https://engineering.tamu.edu/cse/profiles/leyk-zbigniew.html
- https://artsci.tamu.edu/mathematics/contact/faculty.html (loads `dept-profile-data.json`)
- https://artsci.tamu.edu/profile-data.json (3,085 entries)
- https://artsci.tamu.edu/mathematics/contact/profiles/alan-demlow.html
- https://mays.tamu.edu/faculty/?initial=b (names in the HTML; 222 profile links)
- https://mays.tamu.edu/wp-json/wp/v2/person (574 people, no contact fields)
- https://howdy.tamu.edu/uPortal/p/public-class-search-ui.ctf1/max/render.uP (Cloudflare bot check; didn't load)
