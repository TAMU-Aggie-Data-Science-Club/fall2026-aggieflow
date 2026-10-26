# Transportation Services

**Main site:** https://transport.tamu.edu
**Bus app (AggieSpirit):** https://aggiespirit.ts.tamu.edu

## Best way to get the data

1. **Official API:** none found.
2. **JSON feeds (best option):** the bus app loads its live data through `POST` requests I saw in the Network tab (Fetch/XHR). The descriptions below are based on the endpoint names and when each one fired:
   - `https://aggiespirit.ts.tamu.edu/Home/GetActiveRoutes`: active routes (fired when the Bus Times page loaded, status 200)
   - `https://aggiespirit.ts.tamu.edu/Home/GetNearbyRoutes`: routes and stops near a location (fired on page load, status 200)
   - `https://aggiespirit.ts.tamu.edu/Home/GetNextStopTimes`: upcoming arrival times at stops (fired on page load, still pending when checked)
   - `https://aggiespirit.ts.tamu.edu/RouteMap/GetPatternPaths/`: the path a route draws on the map (fired when a route was selected, status 200)

   The request bodies and exact response format still need confirming. In DevTools, click each request and open its Payload and Response tabs.
3. **Download or sitemap:** none. `https://transport.tamu.edu/sitemap.xml` returns a "Webpage Not Found" page.
4. **Plain HTML:** the main site runs on ASP.NET (`.aspx` pages linked from the homepage: `/transit.aspx`, `/parking.aspx`, `/events.aspx`, `/about.aspx`). On the homepage, no separate JSON call showed up for the live garage counts, so they're likely built into the HTML. Whether every subpage's text is in its HTML is **Unknown**, since I didn't open each one.
5. **JavaScript-only:** on aggiespirit.ts.tamu.edu, the next bus times, nearby stops, and route paths on the map load through the JSON calls above.

## What the site is

The main site is Texas A&M Transportation Services: parking, the AggieSpirit buses, special events and gameday, sustainable transportation, and fleet services. It's for students, staff, and visitors. The AggieSpirit app shows routes, next bus times, a map, and a trip planner.

## Main page types

| Type | Examples |
|---|---|
| Service hubs | https://transport.tamu.edu/transit.aspx, https://transport.tamu.edu/parking.aspx, https://transport.tamu.edu/events.aspx |
| Live bus data (JS) | https://aggiespirit.ts.tamu.edu/ (Bus Times), https://aggiespirit.ts.tamu.edu/RouteMap |
| Gameday | https://transport.tamu.edu/football |
| Account portal (likely login-only, not opened) | https://myparking.tamu.edu/ ("My Parking" link on the homepage) |

## Dates and freshness

- **Real-time:** next bus times and the homepage's "Live Garage Counts" are live data.
- **Seasonal:** separate "Break, Nights & Weekends" routes (01-04, 03-05, 40-41), so which routes run depends on the date and time.
- **Event-driven:** the homepage banners change for events (football, Midnight Yell, voting parking).
- Most static pages don't show a "last updated" date. **Unknown** how often they change.

## Size

There are 22 bus routes on the route map and 5 garages with live counts. The number of static pages is **Unknown**, since there's no sitemap.

## 10 questions this source answers

| # | Question | Answer | Link |
|---|---|---|---|
| 1 | Which buses stop at the MSC? | Routes 01, 03, 04, 05, 06, 08, 12, 15, 22, 26, 27, 31, 34, 35, 36, 40, 41, 47 (plus break routes) have stops at or near the MSC. | https://aggiespirit.ts.tamu.edu/ |
| 2 | What's the MSC stop ID for Bonfire (01)? | 0100 | https://aggiespirit.ts.tamu.edu/ |
| 3 | Is there a bus to RELLIS? | Yes, Route 47 RELLIS. | https://aggiespirit.ts.tamu.edu/RouteMap |
| 4 | Is there a bus to the airport? | Route 07 Airport. | https://aggiespirit.ts.tamu.edu/RouteMap |
| 5 | Which routes run on breaks, nights, and weekends? | 01-04, 03-05, and 40-41. | https://aggiespirit.ts.tamu.edu/RouteMap |
| 6 | What's the bus to Park West? | Route 08 Howdy, toward Park West. | https://aggiespirit.ts.tamu.edu/RouteMap |
| 7 | Which garages show live space counts? | Central Campus (CCG), Polo Road (PRG), Stallings Blvd (SBG), University Center (UCG), West Campus (WCG). | https://transport.tamu.edu/ |
| 8 | How many spots are open in West Campus Garage? | Live number on the homepage (403 when checked Oct 25, 2026, late evening). | https://transport.tamu.edu/ |
| 9 | How much do AggieSpirit bus drivers make? | $14/hr starting, 12 to 39 hours a week, paid training. | https://transport.tamu.edu/ |
| 10 | Where's the campus parking map? | The homepage's "Maps" button links to Aggie Map's parking tab. | https://transport.tamu.edu/ |

Our source list's example question, **"Which bus goes from Northside to Zachry?"**, would need the AggieSpirit trip planner ("Plan a Trip"). Its data source is **Unknown**, and I didn't confirm its network calls.

## Missing, outdated, or confusing

- No sitemap and no official API docs.
- The bus data is split across two domains (transport.tamu.edu and aggiespirit.ts.tamu.edu).
- `/BusRoutes/` on the main site redirects to the AggieSpirit app.
- Personal parking info (myparking.tamu.edu) is likely behind a login, so it's out of scope.
- Which routes run depends on the time and term. An answer without a timestamp could be wrong.

## How AggieFlow could use it

- **Live bus questions** ("when's the next 04 at the MSC?"): call the JSON feeds at question time. Never store the answers, because they go stale in minutes. Medium difficulty: the feeds are undocumented `POST` endpoints, so we need to work out the request bodies, and they could change without notice.
- **Route facts** (which route goes where, stop IDs): pull from the feeds or route map once per term and store them. Easy to medium.
- **Policy pages** (parking, gameday, events): plain HTML. Scrape lightly and re-check weekly, and more often near football games. Easy.
- **Aliases:** stop and route names map well to our alias node ("MSC", "WCG", "Park West", route numbers like "04").
- **Rule:** always show the time a live answer was fetched, and say "I'm not sure" if a feed is down.

## Links checked by hand

- https://transport.tamu.edu/
- https://transport.tamu.edu/sitemap.xml (returns "Webpage Not Found")
- https://aggiespirit.ts.tamu.edu/
- https://aggiespirit.ts.tamu.edu/RouteMap
- https://transport.tamu.edu/BusRoutes/ (redirects to the RouteMap)
