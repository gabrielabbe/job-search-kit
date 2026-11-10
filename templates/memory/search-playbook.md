# Search playbook

How to search, in order of what works. Read it before searching. Add what the candidate's own results teach (outcomes go in `application-log.md` and the tracker; durable lessons go here).

## Principles

1. **Employer first.** Official company job boards (Greenhouse, Lever, Ashby, SmartRecruiters and others) are the most reliable source. Boards and aggregators are discovery feeds: verify every hit at the employer before drafting.
2. **"Remote" is not "worldwide".** A remote role with a salary band in one currency, local benefits, or a city in the description is usually for that country only. Record the sentence that decided eligibility. Companies that hire in the candidate's country say so in the posting.
3. **Recent postings first.** Postings under 14 days old get replies; over about 5 weeks are low-chance leads.
4. **Check the posting is live** (`python scripts/check_live.py <url>`) before drafting.
5. **Quality over volume.** A tailored application to a role that clears the bar beats ten near-misses. Skip hybrid and on-site roles unless the candidate's profile allows them.
6. **Never automate LinkedIn, Indeed or Glassdoor.** Their terms prohibit scraping; use them by hand for leads, then apply through the employer's own page.
7. **Outreach beats resume tweaks.** A short note to the recruiter or hiring manager lifts reply rates. Use `.claude/skills/outreach/SKILL.md`, drafts only.

## Source classes

| Class | Meaning | Examples |
|---|---|---|
| A | Official public API or feed, no credentials | Greenhouse, Lever, Ashby, SmartRecruiters, Recruitee; Himalayas, Remote OK, Remotive, Jobicy, We Work Remotely |
| B | Official API but credentials needed | Adzuna (free key), Teamtailor, JOIN, Comeet |
| C | Public pages, no developer API | Working Nomads, Remote.co and similar. Only after a robots.txt and terms check, then verify at the employer |
| D | Restricted or automation-hostile | LinkedIn, Indeed, Glassdoor: manual use only |

Regional boards (for example Gupy and Get on Board for Brazil and Latin America) are enabled per country in the search profile (`local_feeds`).

## Routine

1. `python scripts/scan_jobs.py --max-age 14` (company feeds from `scripts/watchlist.txt`).
2. `python scripts/scan_boards.py --max-age 21` (job boards, filtered by the search profile).
3. Optional engine: `jh ingest`, `jh search`, `jh shortlist` (see `docs/architecture.md`).
4. Score each lead with `.claude/skills/job-scoring/SKILL.md`; draft the passes with `.claude/skills/resume-drafting/SKILL.md`.
5. Log everything in `application-log.md` and the tracker.

## Learning loop

At the start of each session run `python scripts/tracker.py insights`. Per application record `--family`, `--score` and `--source-class`, and `--rejection-stage` on a rejection. Turn patterns into rules in `target-roles.md`. Rates under about 10 to 15 applications are noise: note them, do not act on them.

## Lessons from this candidate's own search

(none yet)
