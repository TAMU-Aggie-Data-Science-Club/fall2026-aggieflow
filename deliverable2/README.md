# Deliverable 2: Map a source

**Issue:** [#11](https://github.com/TAMU-Aggie-Data-Science-Club/fall2026-aggieflow/issues/11) · **Due:** Sunday, October 25 · **Time:** about 1 hour

AggieFlow can only answer questions from sources it understands. Before we build the scrapers and database, we need to know what each source has, how its pages are built, the best way to get its data, and what we're allowed to collect.

This week you claim one source and explore it, first by hand and then with an AI assistant using the prompt below. The deliverable is a short report with information on how the website is structured, any key findings, and how we could use and integrate the data. We'll design the data pipeline from these reports.

## Steps

1. **Claim a source.** Open the [list of source issues](https://github.com/TAMU-Aggie-Data-Science-Club/fall2026-aggieflow/issues?q=is%3Aopen+label%3Adeliverable-2) and pick one nobody is assigned to. Click **Assignees** → **assign yourself**. One person per source, except the Course Catalog, which takes two. If they're all taken, ask a PM.
2. **Look for a data feed first.** Open the site in Chrome, press F12, and click the **Network** tab. Then click **Fetch/XHR** and use the site normally: search, open pages, change filters. If requests show up that return JSON, that's a data feed. Write down its URL and what it returns. Also check whether the site has an official API, a public download, or a sitemap (`<site>/sitemap.xml`).
3. **Explore with AI.** Paste the prompt below into an AI assistant that can browse the web, such as Claude, ChatGPT, or Gemini. Include what you found in step 2. It ends with a short report.
4. **Check the report.** Open at least 5 of the links it gives you and make sure they say what it claims. AI makes things up sometimes. Fix anything wrong, and list the links you checked at the bottom.
5. **Save the report** as `deliverable2/<source>-<you>.md`. Your source issue gives the exact file name.
6. **Submit:** make a branch named `issue-<n>/<you>`, where `<n>` is your source's issue number. Commit your report and open a pull request into `main`. Put `Closes #<n>` in the PR description.

`<you>` is your GitHub username in lowercase.

## Rules

- Public pages only. Nothing that requires a NetID or login (AI cannot access these).
- Look around by hand or with AI. Don't write scripts that download the whole site.
- Prefer an API or JSON feed over scraping.

## Done when

- [ ] You're assigned to your source's issue
- [ ] You checked the Network tab for a data feed and wrote down what you found (or "none found")
- [ ] Your report covers everything the prompt asks for ("Unknown" is fine)
- [ ] You checked at least 5 links by hand and listed them in the report
- [ ] Your pull request says `Closes #<n>` and is open by the due date

Stuck? Ask in the team chat.

---

## The prompt

```text
Help me map a website so my team can build a search assistant from it.

Source: <SOURCE NAME>
URL: <SOURCE URL>
Data feeds I found in the browser's Network tab: <PASTE URLS AND WHAT THEY RETURN, OR "NONE">

Rules: Public pages only. Look at about 30 pages at most. Give a link for every
claim. If you don't know something, say "Unknown" instead of guessing.

Tell me:
1. What this site is and who it's for.
2. Whether it has an official API, a public JSON endpoint, a data download,
   an RSS feed, or a sitemap. Include links.
3. The main kinds of pages it has, with 2 or 3 example links each.
4. Whether the page text is in the HTML or only loads with JavaScript.
5. Whether pages show dates, and how often things seem to change.
6. Roughly how many useful pages there are.
7. 10 questions a TAMU student might ask that this site answers, with the
   answer and the exact link.
8. Anything missing, outdated, or confusing.
9. How we could use this data in our assistant, and how hard it would be to
   integrate.

Then write a short, simple report in Markdown with the key info, including the
data feeds I found. Start with the source name and link. List the best way to
get the data first: official API, then JSON feed, then download or sitemap, then
plain HTML, then JavaScript pages. Keep it brief.
```
