---
name: job-research
description: Quick or deep research to improve the job search itself: how to find roles, which companies hire in the candidate's country or worldwide, how a company or ATS publishes jobs, recruiter and hiring-manager discovery. Use when a new source, company list or tactic is mentioned, or the search keeps missing good roles.
---

# Job research (quick and deep)

## Quick (about 5 minutes, one session)

1. `python scripts/find_company.py "<Company>" [--add]` shows the company's official job boards, matching roles and adds the board to the watchlist.
2. For a job site, check `https://<site>/robots.txt` first. If it names Claude or Anthropic crawlers, or the content sits behind a bot challenge, skip it and log why (`search-playbook.md`). Never spoof referers, use keys locked to another site, or rotate agents.
3. Look for a public feed (RSS, `/api`, sitemap) before parsing HTML. Add it to `scripts/scan_boards.py` only if it returns jobs with a stated location.
4. Record the verdict (usable, partly, skipped and why) in `.claude/memory/search-playbook.md`.

## Deep (30 to 60 minutes, parallel)

1. Define the question in one sentence (for example "which edtech employers hire staff in my country remotely").
2. Run 6 to 10 WebSearch queries in the same turn, mixing: the employer type, the candidate's country or "worldwide", ATS names (`jobs.ashbyhq.com`, `boards.greenhouse.io`), and community sources (Reddit cannot be fetched directly, so use articles, newsletters and aggregator threads that quote it).
3. For each promising company run `find_company.py`; for each new site check robots.txt and feeds.
4. Verify claims against the live source. Search snippets can be weeks stale; mark anything unverified.
5. Write the result as a short note under `reference/research/<date>_<topic>.md` (findings, sources, what to build next) and fold the durable parts into `search-playbook.md`.
6. Build the smallest thing that turns the finding into recurring value (a watchlist entry, a feed in `scan_boards.py`, a rule in `target-roles.md`), then test it with a real run.

## Always

- Report what failed as well as what worked. Mark unverified items.
- Stay within public information. Nothing is submitted, nothing is sent.
