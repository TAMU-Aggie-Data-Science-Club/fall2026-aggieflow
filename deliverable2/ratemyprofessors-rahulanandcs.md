# Source: RateMyProfessors

**URL:** <https://www.ratemyprofessors.com>

**Data feeds I found in the browser's Network tab:** `https://www.ratemyprofessors.com/graphql` (Returns JSON with professor stats, reviews, and university data via POST requests).

## Best Ways to Get the Data

1. **JSON Feed:** The internal GraphQL endpoint (`/graphql`) provides highly structured data used by the frontend.

2. **JavaScript Pages:** Standard web pages heavily rely on React to fetch and load data dynamically.

3. **Official API / Download / Sitemap:** None found.

4. **Plain HTML:** Not useful; scraping the HTML without JS execution only yields a skeletal page without review data.

## Site Overview

**1. What this site is and who it's for:**
RateMyProfessors is a public review platform for college and university students to rate, review, and compare professors and campuses. It's primarily used to help students choose classes and instructors during course registration.

**2. Data Endpoints & Feeds:**

* **Official API / Data Download / RSS:** None available for developers.

* **Public JSON Endpoint:** Uses an internal, undocumented GraphQL API (`https://www.ratemyprofessors.com/graphql`).

* **Sitemap:** None found (RateMyProfessors does not expose a public `/sitemap.xml`).

**3. Main Kinds of Pages:**

* **School Pages** (Aggregated university ratings & top professors):

  * Texas A&M University: <https://www.ratemyprofessors.com/school/1003>

  * UT Austin: <https://www.ratemyprofessors.com/school/1255>

* **Professor Pages** (Individual reviews, tags, and difficulty ratings):

  * Akash Tyagi (CSCE): <https://www.ratemyprofessors.com/professor/1967267>

  * Teresa Leyk (CSCE): <https://www.ratemyprofessors.com/professor/609101>

  * Amit Merchant (CSCE): <https://www.ratemyprofessors.com/professor/3035399>

  * Shinjiro Sueda (CSCE): <https://www.ratemyprofessors.com/professor/2438929>

**4. HTML vs. JavaScript:**
The core review and rating content **only loads with JavaScript**. The site is a React single-page application that fetches content from the GraphQL endpoint dynamically on load.

**5. Dates and Updates:**
Yes, individual student reviews show the specific date they were posted. Aggregated ratings appear to change immediately when new reviews are submitted and approved.

**6. Number of Useful Pages:**
Millions. There are over 1.7 million professors and 7,500 schools listed. TAMU alone has thousands of professor directory pages.

**7. 10 Questions a TAMU Student Might Ask:**

 1. **Q:** What is Texas A&M's overall student rating?
    **A:** Around 4.4 out of 5 based on student votes. [Link](https://www.ratemyprofessors.com/school/1003)

 2. **Q:** Is attendance mandatory for Professor Akash Tyagi?
    **A:** The reviews state "Attendance: Mandatory" or mention attendance policies in student feedback. [Link](https://www.ratemyprofessors.com/professor/1967267)

 3. **Q:** Is Professor Teresa Leyk considered a tough grader?
    **A:** The platform calculates a difficulty rating and includes student tags like "Tough Grader". [Link](https://www.ratemyprofessors.com/professor/609101)

 4. **Q:** What percentage of students would take Akash Tyagi again?
    **A:** It lists an exact "Would Take Again" percentage of 95% on the professor header card. [Link](https://www.ratemyprofessors.com/professor/1967267)

 5. **Q:** Are textbooks required for Amit Merchant's class?
    **A:** Reviews explicitly list "Textbook: Yes" or "Textbook: No" indicators. [Link](https://www.ratemyprofessors.com/professor/3035399)

 6. **Q:** What is Shinjiro Sueda's overall quality rating?
    **A:** It displays an overall numeric score of 4.4 out of 5 based on aggregated ratings. [Link](https://www.ratemyprofessors.com/professor/2438929)

 7. **Q:** What specific feedback do students have about CSCE 312 with Akash Tyagi?
    **A:** Users can filter or browse reviews specifically tagged with course codes like "CSCE312". The class very difficult but it had more to do with the content itself than the professor. [Link](https://www.ratemyprofessors.com/professor/1967267)

 8. **Q:** Does Teresa Leyk give a lot of homework or heavy exams?
    **A:** Written student reviews provide detailed qualitative feedback on workload, exams, and grading style. Professor gave heavy exams. [Link](https://www.ratemyprofessors.com/professor/609101)

 9. **Q:** Who are the top-rated professors at TAMU overall?
    **A:** The university school page features a list of highest-rated faculty members. Akash Tyagi is one of the highest. [Link](https://www.ratemyprofessors.com/school/1003)

10. **Q:** Was Shinjiro Sueda rated well for online/asynchronous sections?
    **A:** Reviews state whether the section was taken "Online" or in-person. Professor was rated well for mostly in-person classes. [Link](https://www.ratemyprofessors.com/professor/2438929)

**8. Missing, Outdated, or Confusing Info:**

* RMP does not verify if a professor still actively teaches at a university (profiles for retired/departed professors remain).

* Course names/numbers submitted by students can be outdated or misspelled.

* Extreme voluntary response bias is present; most reviews are written by students who either loved or severely disliked their experience.

**9. Data Integration:**

* **Usefulness:** Highly useful for answering "Who is the easiest professor for CSCE 312?" or providing context on textbook costs and attendance policies.

* **Difficulty:** Hard. We have to bypass standard scraping and reverse-engineer their `/graphql` payload structures, which might trigger bot protection if polled too fast. Additionally, matching RMP's user-submitted names (e.g., "Bob" vs. "Robert") to TAMU's official course roster will require fuzzy string matching.

---

**Links Checked:**

* <https://www.ratemyprofessors.com>
* <https://www.ratemyprofessors.com/school/1003>
* <https://www.ratemyprofessors.com/professor/1967267>
* <https://www.ratemyprofessors.com/professor/3035399>
* <https://www.ratemyprofessors.com/professor/609101>
* <https://www.ratemyprofessors.com/professor/2438929>