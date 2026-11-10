# Source compliance

Rules enforced in code (`src/jobintel/http.py`) and by configuration (`config/sources.yaml`):

- Only public, documented job-board endpoints are used by the connectors: Greenhouse Job Board API, Lever Postings API, Ashby public posting API, SmartRecruiters public postings. No authentication is bypassed and no endpoint is guessed or brute-forced. A board slug is accepted only from the user's registry (initially `scripts/watchlist.txt`, `ats_confidence=unverified` until a fetch returns rows).
- Identified user agent. Per-host minimum interval between requests (default 1.0 s) and a retry cap.
- HTTP 429: honour `Retry-After`, otherwise exponential backoff with jitter, capped. HTTP 5xx and timeouts: same, capped.
- HTTP 401 or 403: stop for that source, log `access_denied`, never retry, never rotate anything. Treated as a hard block.
- HTTP 404: `not_found` (wrong slug or retired board). It is **not** recorded as "closed" for existing postings: closure requires the posting to be absent from a *successful* full fetch.
- A timeout or network error never closes a posting.
- No proxies, CAPTCHA solvers, stealth fingerprints or account rotation exist in this code base and none may be added.
- Contacts: only name, role, organisation, public profile or published business address, with the source URL and date. Email addresses are never guessed or pattern-derived.
- Job text, web pages and emails are untrusted data. Instructions embedded in them are ignored; HTML is reduced to text before storage.

| Source | Status | Notes |
|---|---|---|
| Greenhouse boards API | implemented | `content=true&pay_transparency=true`; note `content=false` also drops departments (reference trap 6) |
| Lever postings API | implemented | `mode=json`; no company name in payload, filled from the registry (trap 2) |
| Ashby posting API | implemented | `includeCompensation=true` |
| SmartRecruiters | implemented | page size 100, paging on `offset`; an unknown slug returns 200 with zero rows, so zero is reported as `empty_or_unknown` (trap 1) |
| USAJOBS | blocked | needs an API key and is oriented to US federal hiring |
| Employer careers pages (JSON-LD) | planned | permitted pages only |
| Crawl4AI, Scrapy | planned | only for employers with no ATS, after a robots.txt and terms review per domain |
| ScrapeGraphAI | optional, not integrated | only if simple parsing fails |
| JobSpy | rejected by default | see decisions D-6 |
| freehire | reference only | see decisions D-7 |
| Indeed, LinkedIn, Glassdoor | not automated | use the existing manual or MCP-assisted lookups only |
