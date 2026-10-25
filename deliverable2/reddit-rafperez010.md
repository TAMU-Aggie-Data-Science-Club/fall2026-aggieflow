
# r/aggies — Source Mapping Report

**Source:** https://www.reddit.com/r/aggies/

**Issue:** #20 — Map source: r/aggies

**Checked:** October 25, 2026

**Contributor:** rafperez010

**Best way to obtain data:** Seek Reddit's approval for the intended use before collecting anything. For a qualifying academic research project, investigate [Reddit for Researchers](https://support.reddithelp.com/hc/en-us/articles/49381918834964-Reddit-for-Researchers-Program); for approved developer applications, consult the [official Data API](https://www.reddit.com/dev/api/). Neither route automatically authorizes AggieFlow to store, index, or reuse Reddit discussions. Prefer an authorized API to scraping internal website endpoints.

## 1. What the Site Is

r/aggies is a public Reddit community for discussions about Texas A&M University and the Bryan–College Station area. Students, alumni, and other community members ask questions and share experiences concerning classes, professors, housing, transportation, student organizations, jobs, restaurants, and campus life. It is useful for **student perspectives**, but it is not an official university source.

**Main URL:** https://www.reddit.com/r/aggies/

## 2. Available Data Feeds and Permissions

**Acquisition preference:** official approved API → approved JSON/data feed → public download/sitemap → ordinary HTML → JavaScript-rendered pages, **only when permitted**. No suitable, authorized post-data feed was confirmed by the browser Network inspection.

- **Official API documentation:** https://www.reddit.com/dev/api/ — describes subreddit listings, searching, and post comment trees. These are documented API capabilities, **not** evidence that AggieFlow is already approved to access them.
- **Developer access guidance:** https://support.reddithelp.com/hc/en-us/articles/14945211791892-Developer-Platform-Accessing-Reddit-Data — identifies approved developer access requirements and directs academic researchers to the Reddit for Researchers program. The program has [eligibility and permitted-use rules](https://support.reddithelp.com/hc/en-us/articles/49381918834964-Reddit-for-Researchers-Program); research approval should not be assumed to authorize a student-facing RAG product. AggieFlow's specific use would need a permissions review.
- **Data API terms:** https://redditinc.com/policies/data-api-terms — impose restrictions on data access, retention, reuse, attribution, and AI model training. A public post is not automatically licensed for bulk ingestion, storage, or AI training. RAG/indexing rights must be evaluated rather than assumed.
- **Public download:** None identified during this limited review.
- **Sitemap:** The standard URL https://www.reddit.com/sitemap.xml returned **404 Not Found** during an October 25 web check; other sitemap arrangements, if any, are **unknown**.
- **RSS/Atom:** https://www.reddit.com/r/aggies/.rss responded with an Atom/XML content type (`application/atom+xml`) during a web check, but its entries and permissions were **not** inspected or established. Reddit's [API documentation](https://www.reddit.com/dev/api/) lists RSS support for some endpoints.
- **Public post JSON feed:** No authorized public JSON post feed was verified. The JSON seen in DevTools involved experiments/CAPTCHA rather than r/aggies posts.

**Bottom line:** Access approval and data-use rights are the biggest integration blockers. No bulk download or automated scraper was performed for this assignment.

### Browser Network-tab findings (observed in Chrome on October 25)

| Request observed | Method / status | Format / finding |
|---|---|---|
| `https://www.reddit.com/svc/shreddit/community-more-posts/best/?after=...` | GET / 200 OK | `text/vnd.reddit.partial+html`; returns HTML fragments containing additional subreddit posts and visible post metadata. The `after` value is a pagination cursor. |
| `https://www.reddit.com/svc/shreddit/graphql` (`ExposeVariant`) | POST / 200 OK | JSON; experiment/variant-related response, **not** a post feed in the observed request. |
| Same GraphQL URL (`CreateCaptchaToken`) | POST / response examined | JSON; CAPTCHA-related response, **not** a post feed in the observed request. |

The HTML-fragment response showed post-related markup and data such as titles, links, timestamps, scores, and comment counts. These `/svc/shreddit/...` requests are **internal website endpoints**, not documented third-party collection APIs. Finding them in DevTools does not grant permission to collect from them.

## 3. Main Kinds of Pages

| Page type | Examples | What it contains |
|---|---|---|
| Community listings | [Main feed](https://www.reddit.com/r/aggies/), [New](https://www.reddit.com/r/aggies/new/), [Top](https://www.reddit.com/r/aggies/top/) | Lists of posts, titles, dates, flairs, votes, links, and comment counts. |
| Post and comment threads | [CSCE professors](https://www.reddit.com/r/aggies/comments/1bm4l5s/recommendations_for_csce_221_and_222_professors/), [Housing](https://www.reddit.com/r/aggies/comments/1qui7nw/llc_and_housing_questions/), [Bus guide](https://www.reddit.com/r/aggies/comments/1mook46/guide_on_how_to_ride_the_busand_what_to_expect/) | Original question/post and threaded responses; sometimes images and outside links. |
| Search result pages | [Professor search](https://www.reddit.com/r/aggies/search/?q=CSCE%20professor&restrict_sr=1), [Housing search](https://www.reddit.com/r/aggies/search/?q=housing&restrict_sr=1), [Study spots search](https://www.reddit.com/r/aggies/search/?q=study%20spots&restrict_sr=1) | Keyword results with links to potentially relevant discussions. |

## 4. HTML or JavaScript?

The public threads examined displayed readable post and comment text without logging in. **Confirmed:** Reddit makes background requests while loading more posts, and an observed `community-more-posts/best/` call returned **partial HTML**, not JSON. Two GraphQL calls returned JSON for unrelated site features. **Unknown:** whether the initial post text is contained in the first page's raw HTML or requires JavaScript; we did not compare *View Page Source* against the rendered page or disable JavaScript. Dynamic loading complicates collection.

## 5. Dates, Change Frequency, and Rough Size

Posts and comments display relative dates (such as “2mo ago”); post activity can continue after creation, and content may be edited, deleted, or removed. New discussions appear frequently, while older advice can become stale. Exact update cadence and the **total number of useful pages are unknown**. At least **10 distinct relevant public discussion pages** were identified in this small sample; that is a lower bound for our examples, **not an estimate of the entire archive**. No whole-site download or enumeration was performed. Topics with fast-changing details (routes, permits, application deadlines, instructor assignments) need recent, official corroboration.

## 6. Ten Questions TAMU Students Could Ask

The answers below summarize **what individual Reddit participants said**. They are examples of supported student-experience answers, not verified TAMU policy, representative surveys, or current availability.

1. **Which professors do students recommend for CSCE 221 and 222?**
   Commenters recommended **Leyk** for CSCE 221 and **Carlisle** for CSCE 222; one also discussed helpful office hours. These are older personal opinions, not current section assignments.
   [Source discussion](https://www.reddit.com/r/aggies/comments/1bm4l5s/recommendations_for_csce_221_and_222_professors/)

2. **What housing do students suggest for incoming engineering students?**
   Commenters recommended **The Commons** (Krueger, Dunn, Mosher, Aston) and discussed Engineering Honors/LLC arrangements. Housing program availability and dorm assignments require official confirmation.
   [Source discussion](https://www.reddit.com/r/aggies/comments/1qui7nw/llc_and_housing_questions/)

3. **Where can I study quietly with charging outlets outside popular library areas?**
   Participants mentioned the fifth floor of Zachry, Cushing, MedSci, PLPM, ILCB, Student Services, Rudder, Civil Engineering, and an ARCB hallway. Outlet availability and access hours were not verified.
   [Source discussion](https://www.reddit.com/r/aggies/comments/175k3id/best_spots_on_campus_to_study_with_access_to/)

4. **What do students regret about freshman year?**
   Common experiences in this thread included not joining organizations, not making friends, inconsistent studying, skipping office hours, and delaying requests for support. Some comments contain sensitive or inappropriate material, which an assistant should not repeat indiscriminately.
   [Source discussion](https://www.reddit.com/r/aggies/comments/1va66n2/biggest_regrets_from_freshman_yearundergrad/)

5. **What should a new student know about riding AggieSpirit buses?**
   A poster identifying as a bus driver advises riders to request stops, allow extra travel time, make room on crowded buses, and consult official transit maps. Route and schedule specifics in the older thread may be obsolete.
   [Source discussion](https://www.reddit.com/r/aggies/comments/1mook46/guide_on_how_to_ride_the_busand_what_to_expect/)

6. **Which majors do students say are harder than outsiders assume?**
   Commenters mentioned English, Nutrition, Meteorology, Psychology, Environmental Design, Journalism, and GIS, giving examples of heavy reading, sciences, writing, or studio work. These are subjective impressions, not difficulty rankings.
   [Source discussion](https://www.reddit.com/r/aggies/comments/s8v076/what_is_a_major_at_am_that_is_assumed_to_be_easy/)

7. **What alternatives are suggested if a commuter has no campus parking permit?**
   Students suggested paying for visitor parking temporarily, carpooling, cycling, or investigating park-and-ride connections. **Never assume a private lot allows public parking**; current prices, rules, and routes must be checked with TAMU Transportation and property owners.
   [Source discussion](https://www.reddit.com/r/aggies/comments/1voha6o/parking_help/)

8. **Which Bryan–College Station restaurants do students recommend?**
   Suggestions included Shun De Mom, Masfajitas, RR Pinoy Thai, Shiraz Shish Kabob, Cafe Capri, and others. Restaurants, prices, and customer experiences may have changed; these are preferences, not rankings or verified allegations.
   [Source discussion](https://www.reddit.com/r/aggies/comments/1icdfxr/foodrestaurant_recommendations_in_college/)

9. **Can a junior still join campus organizations to make friends?**
   Respondents encouraged joining later in college and mentioned Cephid Variable, Tabletop Troupe, Student Bonfire, Alpha Phi Omega, Twelve, Aggie Camping Club, and Somtech. Membership rules and short-term application deadlines need current verification.
   [Source discussion](https://www.reddit.com/r/aggies/comments/1w6o5ra/joining_orgs_as_a_junior/)

10. **How can students build experience if they do not get a final-summer internship?**
    Commenters suggested personal projects, research, networking, volunteering/coursework, and continued full-time job applications. Several described getting jobs without internships, while others acknowledged that the first job may be harder to secure. These are individual experiences, not promises of employment.
    [Source discussion](https://www.reddit.com/r/aggies/comments/1tvbbja/how_do_you_get_over_not_getting_a_internship_for/)

## 7. Missing, Outdated, or Confusing Information

- **Not authoritative:** Reddit posts are personal accounts and may be wrong, exaggerated, contradictory, or unrepresentative. Some users disagree about professors, majors, businesses, and transportation advice.
- **Time-sensitive claims:** Bus stops, parking permissions, student-organization deadlines, course staffing, dining availability, and campus services may change after a post is published.
- **Moderation and relevance:** Threads may include profanity, sexual remarks, off-topic replies, jokes, advertisements, or moderator-removed comments. Some also describe sensitive personal situations. Filtering and careful presentation would be essential for a student-facing assistant.
- **Deletion and privacy:** Posts/comments can be removed, and usernames or personal stories should not be retained or republished outside what is permitted. A citation can also lead users to the original unfiltered discussion.
- **Coverage and representativeness:** There is no guarantee that the most popular comments reflect most students. Exact size of the useful corpus, comprehensive coverage, and available official bulk download are **unknown**.

## 8. How AggieFlow Could Use This Source

**Potential value:** Supplement official TAMU records with clearly attributed student experiences about studying, academics, housing, campus life, clubs, and careers. For example, a response could say “In this Reddit thread, several commenters recommend ...” and link to that thread.

**Suggested integration if access is approved:** obtain data using the authorized route; retain only allowed fields for the approved purpose; index or retrieve relevant content only when permitted; filter irrelevant/sensitive content; preserve source URL and original post date; separate community opinions from verified facts; and cross-check current policies, fees, transportation details, and academic requirements against official TAMU websites. Implement deletion/retention compliance and avoid training a model on Reddit content without necessary consent.

**Difficulty: High (conditional).** Technically, threads and metadata are structured enough to be useful, but access approval, licensing, privacy, content moderation, stale information, and provenance make safe integration substantially more difficult than ingesting official university documentation. **Do not assume RAG indexing or AI use is allowed merely because posts are public.** If approval cannot be obtained, AggieFlow could link users to relevant public discussions without storing a Reddit corpus, subject to applicable terms.

## 9. Links Manually Checked

These threads were opened and examined in the browser during this source-mapping exercise, with relevant post text/comments reviewed:

1. [CSCE 221/222 professors](https://www.reddit.com/r/aggies/comments/1bm4l5s/recommendations_for_csce_221_and_222_professors/)
2. [LLC and Housing questions](https://www.reddit.com/r/aggies/comments/1qui7nw/llc_and_housing_questions/)
3. [Study spots and charging outlets](https://www.reddit.com/r/aggies/comments/175k3id/best_spots_on_campus_to_study_with_access_to/)
4. [Freshman-year regrets](https://www.reddit.com/r/aggies/comments/1va66n2/biggest_regrets_from_freshman_yearundergrad/)
5. [AggieSpirit bus guide](https://www.reddit.com/r/aggies/comments/1mook46/guide_on_how_to_ride_the_busand_what_to_expect/)
6. [Underestimated majors](https://www.reddit.com/r/aggies/comments/s8v076/what_is_a_major_at_am_that_is_assumed_to_be_easy/)
7. [Parking help](https://www.reddit.com/r/aggies/comments/1voha6o/parking_help/)
8. [Restaurant recommendations](https://www.reddit.com/r/aggies/comments/1icdfxr/foodrestaurant_recommendations_in_college/)
