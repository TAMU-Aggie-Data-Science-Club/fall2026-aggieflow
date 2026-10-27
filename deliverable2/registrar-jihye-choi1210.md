# Source Map: Texas A&M Office of the Registrar

**Source:** [Texas A&M Office of the Registrar](https://registrar.tamu.edu/)
**GitHub issue:** #13
**Date investigated:** October 26, 2026

## 1. Site and audience

The Office of the Registrar website provides information about academic calendars, registration, academic records, grading, Q-Drops, classroom scheduling, and graduation. It is mainly useful to Texas A&M students, but faculty, staff, graduates, and families also use it. AggieFlow could use the site to answer common student questions and link students to the official information.

## 2. Data sources found

| Source | URL | Format | Findings |
| --- | --- | --- | --- |
| Registrar sitemap | https://registrar.tamu.edu/sitemap.xml | XML | Lists 154 URLs, with `loc`, `lastmod`, `changefreq`, and `priority` fields. |
| Academic calendar RSS | https://calendar.tamu.edu/live/rss/events/group/Office%20of%20the%20Registrar/tag/fall%202026/start_date/-2%20years/end_date/+2%20years | RSS/XML | Feed for Fall 2026 Registrar calendar events. |
| Semester calendar download | https://calendar.tamu.edu/live/ical/events/group/Office%20of%20the%20Registrar/tag/fall%202026/start_date/-2%20years/end_date/+2%20years | iCalendar (`.ics`) | Calendar events can be imported into calendar applications. |
| Academic calendar widget | https://calendar.tamu.edu/live/widget/982 | HTML | Network request returned HTML containing Fall 2026 calendar event titles and dates. |
| Registrar news data | https://registrar.tamu.edu/_json-data/json-news-data.json | JSON | Contains news titles, article links, dates, categories, tags, and descriptions. |
| Classroom inventory data | https://aws-api.marcomm.tamu.edu/google-sheets/v1/query-sheet/1pWwmYbJIKsjQj53v1CMlHurXYG3kSMMp30pPnPaLeg8/classroom%20inventory | JSON | Provides building, room, seating capacity, status, and photo fields. This appears to be a site-specific data endpoint, not a documented public API. |

I did not find a documented general-purpose Registrar API during this investigation. The `https://registrar.tamu.edu/robots.txt` address returned a 404 error when I opened it. That does not mean the site has no access rules or that its data can automatically be reused without checking permissions.

## 3. Page types and example URLs

### Academic calendars and deadlines
- https://registrar.tamu.edu/academic-calendar/index.html
- https://registrar.tamu.edu/academic-calendar/fall-2026.html
- https://registrar.tamu.edu/academic-calendar/spring-2027.html

These pages provide semester dates, registration periods, deadlines, holidays, and final exam information.

### Academic policies, grades, and records
- https://registrar.tamu.edu/academic-services/records-administration-archives/q-drops.html
- https://registrar.tamu.edu/academic-services/grading/index.html
- https://registrar.tamu.edu/academic-services/grading/online-grading-instructions-for-howdy.html

These pages explain policies and procedures that students and staff may need to understand.

### Registration, scheduling, and classrooms
- https://registrar.tamu.edu/registration-scheduling-and-analytics/index.html
- https://registrar.tamu.edu/registration-scheduling-and-analytics/classroom-inventory.html
- https://registrar.tamu.edu/registration-scheduling-and-analytics/course-scheduling-timeline.html

These pages cover registration-related operations, classroom details, and scheduling.

### Graduation
- https://registrar.tamu.edu/graduation/faqs/index.html
- https://registrar.tamu.edu/graduation/ceremony-information/guest-information.html
- https://registrar.tamu.edu/graduation/ceremony-information/photos-and-videos.html

These pages explain graduation logistics and answer questions from graduates and guests.

### News and announcements
- https://registrar.tamu.edu/news/index.html
- https://registrar.tamu.edu/news/newsfeed.html
- https://registrar.tamu.edu/news/2026/09/spring-2027-class-schedules-available-and-registration-times-assigned.html

These pages contain dated announcements about registration, graduation, and other Registrar services.

## 4. Original HTML versus JavaScript

The Q-Drops page contains policy text directly in its original HTML, inside `details` and `summary` elements. The Graduation FAQs page also includes its questions and answers in the original HTML. These pages should be relatively straightforward to read without running JavaScript.

The Academic Calendar page loads event information from a separate HTML widget at `calendar.tamu.edu/live/widget/982`. The Registrar News page requests a JSON file, and the Classroom Inventory page uses JavaScript to load a JSON table. The classroom table has search, sorting, and pagination; the webpage notes that it may take up to 45 seconds to load.

The JSON endpoints are useful, but I would not assume they are stable, documented APIs. For the classroom endpoint, DevTools showed a successful `200 OK` response with `Content-Type: application/json` when the Registrar page requested it through `searchsorttable.js`. However, opening the same endpoint directly in Chrome returned `{"message":"Internal Server Error"}`. The successful response included `Access-Control-Allow-Origin: https://registrar.tamu.edu`. This may limit access from other browser applications, but the exact cause of the direct-request error is unknown.

## 5. Updates and freshness

The sitemap provides `lastmod` dates and marks pages with a suggested `monthly` change frequency. This is metadata, not proof that every page is updated monthly. The news page displays publication dates, including announcements from September and October 2026. Academic calendar information changes between semesters, while policies may change less often. AggieFlow should save the source URL and check important deadlines against the current semester before answering.

## 6. Approximate number of useful pages

I counted **154 `<loc>` entries** in the Registrar sitemap using Chrome's Find feature. This is the number of URLs listed, **not** a confirmed count of useful student pages. The sitemap includes news archives and administrative pages that may not be relevant to most student questions.

As an initial scope, I would prioritize the academic calendars, Q-Drop and records policies, registration information, graduation FAQs, and current news. A precise count of useful pages would require reviewing and classifying the sitemap entries.

## 7. Ten student questions and answers

The answers marked **Recheck** are provisional and should be confirmed on their linked official pages before submission.

| # | Student question | Answer | Exact source |
| --- | --- | --- | --- |
| 1 | When is the Fall 2026 Q-Drop deadline? | November 16, 2026, at 5:00 p.m. **Recheck the calendar before relying on this date.** | https://registrar.tamu.edu/academic-calendar/fall-2026.html |
| 2 | How many Q-Drops can I use? | Texas A&M normally permits four undergraduate Q-Drops. State law limits eligible students to six drops across Texas public institutions. Exceptions may apply. | https://registrar.tamu.edu/academic-services/records-administration-archives/q-drops.html |
| 3 | How do I request a Q-Drop? | Students can use the Submit Q-Drop Request card in Howdy. **Recheck the page for current instructions.** | https://registrar.tamu.edu/academic-services/records-administration-archives/q-drops.html |
| 4 | When does Spring 2027 preregistration begin? | November 5, 2026, with assigned registration times. **Recheck the calendar before relying on this date.** | https://registrar.tamu.edu/academic-calendar/fall-2026.html |
| 5 | Where can I find my assigned registration time? | The Registration Readiness card in Howdy. **Recheck the announcement for current instructions.** | https://registrar.tamu.edu/news/2026/09/spring-2027-class-schedules-available-and-registration-times-assigned.html |
| 6 | Do I need guest tickets for Fall 2026 graduation? | No. Tickets are not required, and seating is first come, first served. | https://registrar.tamu.edu/graduation/faqs/index.html |
| 7 | How long does a graduation ceremony last? | The duration varies, but guests should plan for up to three hours. | https://registrar.tamu.edu/graduation/faqs/index.html |
| 8 | What should I wear to graduation? | Business or business casual is typical. Graduates must wear appropriate regalia and shoes. | https://registrar.tamu.edu/graduation/faqs/index.html |
| 9 | Can my family watch graduation online? | Yes. KAMU-TV provides online streaming for Reed Arena ceremonies. | https://registrar.tamu.edu/graduation/faqs/index.html |
| 10 | How many seats are in ZACH 310? | The Classroom Inventory table lists a seating capacity of 100. | https://registrar.tamu.edu/registration-scheduling-and-analytics/classroom-inventory.html |

## 8. Missing, outdated, or confusing information

- Information is spread across regular HTML pages, an HTML calendar widget, RSS/iCalendar feeds, and JSON files. There is no single confirmed general-purpose API for everything.
- Semester-specific deadlines can become outdated if AggieFlow uses the wrong calendar or an old announcement.
- The Classroom Inventory page warns that the table can take up to 45 seconds to load. Some room photo entries are marked `No Image`. The JSON endpoint succeeded from the webpage but returned an Internal Server Error when opened directly in Chrome.
- The sitemap includes update dates, but these do not guarantee that every detail on a page is current.
- Some policies have exceptions, so AggieFlow should link to the complete policy rather than oversimplifying an answer.

## 9. Proposed integration and difficulty

**Recommended difficulty: Medium.**

I would start with the academic calendar feeds, Q-Drops page, Graduation FAQs, and current Registrar news. The RSS and iCalendar feeds are promising sources for academic events. The news JSON feed and classroom inventory JSON provide structured data. For policies and FAQs, AggieFlow could extract the text from the original HTML and keep the source link with each answer.

I would not start by scraping all 154 sitemap URLs. Instead, I would use the sitemap to find relevant pages, prioritize common student questions, and refresh semester-specific information regularly. Before using the internal JSON endpoints in a deployed application, the team should check whether their use is allowed and whether they can be accessed reliably. In particular, the classroom JSON endpoint needs further testing because direct navigation returned an error even though the webpage request succeeded.

## 10. Pages I checked manually

I opened and inspected these public pages in Chrome during the investigation:

1. https://registrar.tamu.edu/academic-calendar/index.html — calendar widget, RSS, and semester download options.
2. https://registrar.tamu.edu/academic-services/records-administration-archives/q-drops.html — policy text and HTML structure.
3. https://registrar.tamu.edu/registration-scheduling-and-analytics/classroom-inventory.html — searchable table and JSON request.
4. https://registrar.tamu.edu/news/index.html — news categories, tags, and JSON request.
5. https://registrar.tamu.edu/graduation/faqs/index.html — questions and answers in HTML.
6. https://registrar.tamu.edu/sitemap.xml — XML entries and total URL count.

No login was needed for these pages. I did not attempt to access private student data.
