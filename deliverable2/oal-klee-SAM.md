# Technology Services

**Link**: https://www.it.tamu.edu/ · **Issue**: #16 · Checked: October 24, 2026

The official Texas A&M Technology Services website, serving students, faculty, staff, researchers, and campus visitors. It is the central portal for campus IT infrastructure, software availability, cybersecurity policies, campus Wi-Fi access, Open Access Labs, AI services, and technical support via Help Desk Central.

## Best way to get the data

1. **Official API**: none for main site content. Specific sub-services maintain standalone endpoints—for example, TAMU AI Chat offers an OpenAI-compatible API documented at https://www.it.tamu.edu/services/services-by-category/communication-and-collaboration/tamu-ai-chat.html, and campus mapping services expose REST endpoints like https://gis.it.tamu.edu/arcgis/rest/services/TS/Family_Weekend/MapServer/queryDomains. However, no public API exists for fetching site-wide content or guides.
2. **JSON feed: none.** No general site content or knowledge base JSON feeds are exposed on the domain.
3. **Sitemap: yes.** https://www.it.tamu.edu/sitemap.xml provides a complete structured list of public page URLs, complemented by a human-readable directory at https://www.it.tamu.edu/sitemap.html.
4. **Download: none.** No single bulk download or database dump of IT services or policies is provided.
5. **HTML: yes, for all services, news, and policies.** Content is rendered as server-side static HTML via Cascade CMS. HTML tags and page structures are consistent across service categories, making plain web scraping straightforward.
6. **JavaScript pages: minimal.** Content does not rely on client-side JS rendering; standard HTML parsers can extract all visible text directly from page source files.

## How the site is built

- **Explore Services & Catalog:** Main service listings are categorized by role (/services/services-for-you/), category (/services/services-by-category/), and alphabetically at https://www.it.tamu.edu/services/services-a-z/index.html. Core examples include:
  - https://www.it.tamu.edu/services/services-by-category/administration-and-business/adobe-creative-applications.html
  - https://www.it.tamu.edu/services/services-by-category/infrastructure/eduroam.html
  - https://www.it.tamu.edu/services/services-by-category/communication-and-collaboration/tamu-ai-chat.html

- **Security & Policy Guides:** Detailed guidelines under /security-and-policy/, such as:
  - https://www.it.tamu.edu/security-and-policy/it-policy/it-policy-guides/international-travel.html
  - https://www.it.tamu.edu/security-and-policy/it-policy/it-policy-guides/network-access.html

- **News and Advisories:** Announcements published under /about/news/, for example:
  - https://www.it.tamu.edu/about/news/2026/grackle-google-workspace.html
  - https://www.it.tamu.edu/about/news/2024/conquer-your-inbox.html
- **Robots and Sitemaps:** Crawling guidelines are set in https://www.it.tamu.edu/robots.txt, and the full site map is indexed at https://www.it.tamu.edu/sitemap.xml.

## Dates, changes, and size

- **Dates:** Pages display explicit modification timestamps (e.g., "Last Modified: September 30, 2026" on https://www.it.tamu.edu/), and news advisories are dated by publication day.
- **Changes:** Updated continuously throughout the year as new IT tools roll out, policies change, or security advisories are issued.
- **Size:** Approximately 300 to 500 core public informational pages covering services, policy guides, leadership directories, and news articles.

## 10 questions it answers

| # | Question | Answer | Link |
|---|---|---|---|
| 1 | What is the primary secure campus Wi-Fi network for TAMU students? | TAMU_WiFi is the primary secure wireless network for students, faculty, and staff | https://www.it.tamu.edu/security-and-policy/it-policy/it-policy-guides/network-access.html |
| 2 | How do I contact Help Desk Central for password or technical assistance? | Call 979-845-8300, email helpdesk@tamu.edu, or visit an Open Access Lab | https://www.it.tamu.edu/security-and-policy/it-policy/it-policy-guides/alternate-work-locations.html |
| 3 | How can students print on campus from their personal devices? | Use AggiePrint to send print jobs to Open Access Lab (OAL) printers | https://www.it.tamu.edu/sitemap.html |
| 4 | Which generative AI platforms are available to TAMU students? | TAMU AI Chat, Microsoft Copilot Chat, Perplexity Enterprise Pro, Google Gemini, and Gemini Notebook | https://www.it.tamu.edu/sitemap.html |
| 5 | What core productivity software is provided to TAMU students? | Microsoft 365, including Word, Excel, PowerPoint, Teams, and OneDrive storage | https://www.it.tamu.edu/services/services-a-z/index.html |
| 6 | How do I connect to Wi-Fi when visiting other academic institutions? | Connect to eduroam using your full TAMU credentials | https://www.it.tamu.edu/services/services-by-category/infrastructure/eduroam.html |
| 7 | What cybersecurity measures are required when traveling abroad with devices? | Use full-disk encryption, access campus resources via official TAMU VPN, disable auto-login, avoid public Wi-Fi, and reset passwords upon return | https://www.it.tamu.edu/security-and-policy/it-policy/it-policy-guides/international-travel.html |
| 8 | Does TAMU provide custom developer access or APIs for AI models? | Yes, TAMU AI Chat provides an OpenAI-compatible API endpoint for developers and custom workflows | https://www.it.tamu.edu/services/services-by-category/communication-and-collaboration/tamu-ai-chat.html |
| 9 | What tool is available to test Google Workspace documents for accessibility? | Grackle for Google Workspace (such as Grackle Sheets) checks for alt text, headings, and color contrast | https://www.it.tamu.edu/about/news/2026/grackle-google-workspace.html |
| 10 | Where can students access digital design tools like Photoshop or Premiere Pro? | Through Adobe Creative Applications, which offers Adobe Creative Cloud and Adobe Express for Education | https://www.it.tamu.edu/services/services-by-category/administration-and-business/adobe-creative-applications.html |

## Missing, outdated, or confusing

- Interactive Knowledge Base articles and support tickets require navigating off-site to TeamDynamix (tamu.teamdynamix.com), decoupling static service pages from detailed troubleshooting documentation.
- Software eligibility rules can be confusing because permissions differ across general students, TAMU Health students, and departmental employees.
- Main site search results mix general informational pages with external ticketing resources, occasionally requiring NetID single sign-on (SSO) login for gated articles.

## How we could use it

- **Use:** Provides the core knowledge layer for answering questions regarding campus IT services, available software licenses, campus Wi-Fi setups, AI tool access, cybersecurity rules, and IT Help Desk contact options.

- **Plan:**
1. Fetch all public URLs directly from https://www.it.tamu.edu/sitemap.xml.
2. Parse the static HTML markup to extract page titles, main body text, service metadata, and role target tags (Students, Faculty, Staff).
3. Chunk and index content in a vector search database categorized by topics (Software, Wi-Fi & Network, Cybersecurity, AI Tools, Support).
4. Monitor https://www.it.tamu.edu/sitemap.xml for updated lastmod dates to trigger automated incremental re-indexing.
- **Difficulty: easy.** Plain HTML structure, clear site hierarchy, and an XML sitemap make extraction straightforward without needing headless browser rendering.
- **Sensitivity:** none. Public information.

## Links checked

- https://www.it.tamu.edu/sitemap.html (human friendly sitemap)
- https://www.it.tamu.edu/services/services-a-z/index.html (Q5, relevant links can be found by CTRL+F or search feature)
- https://www.it.tamu.edu/services/services-by-category/communication-and-collaboration/tamu-ai-chat.html (info on TAMU AI chat usage for students and researchers)
- https://www.it.tamu.edu/robots.txt is present
- https://www.it.tamu.edu/security-and-policy/it-policy/it-policy-guides/international-travel.html
- https://www.it.tamu.edu/security-and-policy/it-policy/it-policy-guides/network-access.html
- https://www.it.tamu.edu/incidents/unresolved.json (incident data, thought it would be interesting to include)
- https://tamu.teamdynamix.com/