# University Libraries

**Main site:** https://library.tamu.edu
**Hours and events (LibCal):** https://tamu.libcal.com

## Best way to get the data

1. **Official API:** none found for the main site's pages. Hours and events run on Springshare LibCal, which has public feeds (below).
2. **JSON feeds (best option, for hours):** the Hours page loads its tables with JavaScript from LibCal. LibCal also answers the same data as JSON, no login needed:
   - `https://tamu.libcal.com/api_hours_grid.php?iid=150&format=json&weeks=1&systemTime=0`: one week of hours for all 23 locations (Evans, Evans Annex, West Campus Library, Cushing, Medical Sciences and its regional sites, Williams Library in Galveston, Qatar, plus services like AskUs chat, the Maker Zone and The Studio). Each day has `date`, `status`, `hours` (from/to) and a `rendered` string such as "7am - 11pm".
   - `https://tamu.libcal.com/api_hours_today.php?iid=150&lid=0&format=json&systemTime=0`: today's hours for every location, with `currently_open`.
   - Seen in the Network tab on https://library.tamu.edu/about/hours.html: `https://tamu.libcal.com/widget/hours/grid?iid=150&lid=<location id>` (the HTML table widget, one per location, for example `lid=1644` is Evans) and `https://tamu.libcal.com/js/hours_grid.js`.
   - Seen on the homepage: `https://tamu.libcal.com/api_events.php?m=upc&cid=1881&...&format=js` (the "Upcoming events" box; with `format=json` it still returns HTML) and `https://chat-us.libanswers.com/widget_status?...` (whether AskUs chat is staffed).
3. **RSS:** `https://tamu.libcal.com/rss.php?cid=1881` is an RSS feed of library events. The main site has no RSS link.
4. **Sitemap:** `https://library.tamu.edu/sitemap.xml` lists 286 pages with `lastmod` dates (all between 2026-04-09 and 2026-10-16 when checked). There is no `robots.txt` (404).
5. **Plain HTML:** every content page I opened has its full text in the HTML (checked by reading the raw HTML, not the rendered page). Only the hours tables and the events box need the LibCal feeds above.
6. **Not part of this source:** book and article search goes to EBSCO (`research.ebsco.com`) and the catalog at `catalog.library.tamu.edu`; theses are in OAKTrust (`oaktrust.library.tamu.edu`); guides are on `tamu.libguides.com`. Those are separate systems. Whether they have public APIs is **Unknown**.

## What the site is

Texas A&M University Libraries: Evans Library and Annex, West Campus Library, the Medical Sciences Library, Cushing Memorial Library (special collections), Williams Library in Galveston and Qatar. It is for students, faculty and staff (your TAMU ID is your library card) and has reduced services for non-TAMU guests. It covers hours, borrowing rules, study spaces, the Tech Bar (free electronics loans), printing, course reserves, events, research help and special collections.

## Main page types

| Type | Examples |
|---|---|
| Borrowing rules | https://library.tamu.edu/borrowing/loan-evans.html, https://library.tamu.edu/borrowing/overdue.html, https://library.tamu.edu/borrowing/returns.html |
| Services | https://library.tamu.edu/services/techbar.html, https://library.tamu.edu/services/print-scan-copy.html |
| Spaces | https://library.tamu.edu/spaces/reserve-a-room.html, https://library.tamu.edu/spaces/gameroom.html |
| Hours (JavaScript, from LibCal) | https://library.tamu.edu/about/hours.html |
| Branch libraries | https://library.tamu.edu/wcl/index.html, https://library.tamu.edu/galveston/about.html, https://library.tamu.edu/medical-sciences/about/index.html |
| Special collections | https://library.tamu.edu/cushing/about/contact-us.html, https://library.tamu.edu/university-archives/athletics.html |
| Course reserves | https://library.tamu.edu/open-ed/textbook-reserves.html |

## Dates and freshness

- **Hours change every week** (finals, breaks, holidays), so they must come from the LibCal feed at question time or be refreshed daily. Some locations (for example the Policy Sciences & Economics Library and several Medical Sciences regional sites) had no hours set for the week I checked.
- **Pages** show no date on screen, but the sitemap gives a `lastmod` for each one. Every page was modified in 2026, so the site is actively maintained.
- **Events** change daily (LibCal RSS).

## Size

286 pages in the sitemap. Biggest sections: about (55), Cushing (45), Medical Sciences (36), spaces (15), instruction (14). The student-facing core (borrowing, services, spaces, hours, branch libraries) is roughly 80 pages. 23 locations in the LibCal hours feed.

## 10 questions this source answers

Checked on 2026-11-11.

| # | Question | Answer | Link |
|---|---|---|---|
| 1 | Can I return a calculator from West Campus Library at Evans? | Yes. Tech Bar items can be returned at any TAMU library Tech Bar location. | https://library.tamu.edu/services/techbar.html |
| 2 | how long can i keep a tech bar calculator | 3 days. Most other Tech Bar equipment is 7 days. | https://library.tamu.edu/services/techbar.html |
| 3 | whats the late fee for tech bar stuff | $7 per day, per item. | https://library.tamu.edu/services/techbar.html |
| 4 | how long can undergrads keep library books | 4 months, up to 100 items, with up to 99 renewals. | https://library.tamu.edu/borrowing/loan-evans.html |
| 5 | do i get fined if a library book is late | Most books don't build up daily fines. High-demand items do, for example course reserve books are $3 an hour up to $150. | https://library.tamu.edu/borrowing/overdue.html |
| 6 | where can i drop off books when the library is closed | Book drops at the Evans Library concourse, on Bizzell Street across from WERC, near Blocker and the Engineering/Physics building off Parking Area 7, and on the covered walk between the Medical Sciences Library and the Reynolds Building. | https://library.tamu.edu/borrowing/returns.html |
| 7 | can any student book a study room at evans | Yes. Individual and group study rooms and study pods at Evans and the Annex are open to all students; research rooms are for graduate students, faculty and staff only. | https://library.tamu.edu/spaces/reserve-a-room.html |
| 8 | can i check out board games from the library | No. The Game Room (Evans, 1st floor, room 108) has board games, but they must be played in the room. It can't be reserved; just drop in. | https://library.tamu.edu/spaces/gameroom.html |
| 9 | is there color printing at evans | Yes, color printers on the 1st floors of Evans Library and the Annex. | https://library.tamu.edu/services/print-scan-copy.html |
| 10 | when does evans close on friday | It changes by week. For the week of Nov 9, 2026: Friday 7am to 7pm (Evans and the Annex). | https://library.tamu.edu/about/hours.html |

Our source list's example question, **"Can a calculator checked out at West Campus Library be returned to Evans?"**, is question 1.

## Missing, outdated or confusing

- **Tech Bar replacement rule disagrees between pages.** The Tech Bar page says an item more than **14 days** overdue is charged its full replacement cost; the Overdue page and the Evans loan page say **7 days**. The assistant should cite one and flag the conflict, or the Libraries should be told.
- Typo on the Overdue page: journals are "$1 per pay".
- Hours are not in the page HTML at all, so a plain HTML scraper would store an empty Hours page.
- No `robots.txt`, and no RSS on the main site.
- Several LibCal locations show blank hours instead of "Closed".

## How we could use it

- **Hours:** call the LibCal JSON feed (`api_hours_grid.php` or `api_hours_today.php`) at question time, or cache it daily. This is the most-asked library question and it can't come from scraped pages. Easy: one request, clean JSON.
- **Policies and services:** collect the ~80 student-facing pages from `sitemap.xml` with `requests` and BeautifulSoup (text is in the HTML), split at headings, cite each page. Easy to medium; tables (loan periods, fines) should be turned into sentences.
- **Events:** the LibCal RSS feed, if we want "what's happening at the library this week". Easy, but low priority.
- **Out of scope for now:** book search, articles and theses (separate systems). The assistant should say "I'm not sure" and link the catalog instead.

## Links I checked by hand

- https://library.tamu.edu/sitemap.xml (286 URLs, all with `lastmod`)
- https://library.tamu.edu/about/hours.html (hours load from LibCal; none in the raw HTML)
- https://tamu.libcal.com/api_hours_grid.php?iid=150&format=json&weeks=1&systemTime=0 (JSON, 23 locations)
- https://tamu.libcal.com/rss.php?cid=1881 (RSS of events)
- https://library.tamu.edu/services/techbar.html
- https://library.tamu.edu/borrowing/loan-evans.html
- https://library.tamu.edu/borrowing/overdue.html
- https://library.tamu.edu/borrowing/returns.html
- https://library.tamu.edu/spaces/reserve-a-room.html
- https://library.tamu.edu/spaces/gameroom.html
- https://library.tamu.edu/services/print-scan-copy.html
