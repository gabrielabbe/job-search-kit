---
name: job-scout
description: Scans company career feeds and job boards for roles that match the candidate's search profile, scores each through job-scoring, and stages the passes for drafting.
---

# Job Scout

## Job

Find postings that match `.claude/memory/target-roles.md` and `config/search-profiles.yaml`: the candidate's target titles, work model, country eligibility and pay floor. Runs on demand, or on a schedule if the candidate registered one (`scripts/register_schedule.ps1`). Also handles any posting the candidate pastes in.

Do not run before onboarding is complete (`python scripts/onboarding_status.py`). The scanners refuse to run on an empty profile.

## Where to look

1. `python scripts/scan_jobs.py --max-age 14`: public job feeds of the companies in `scripts/watchlist.txt`. Add company slugs whenever a lead appears.
2. `python scripts/scan_boards.py --max-age 21`: remote job boards, filtered by the profile's title terms and location terms.
3. Optional: the engine (`jh ingest`, `jh search`, `jh shortlist`) for an eligibility-classified, de-duplicated database.
4. Web search for extra leads in the candidate's industries. LinkedIn and Indeed cannot be read automatically. When a lead comes from there, go to the company's own page and apply through it.
5. Prefer postings from the last 14 days. Both scanners record seen URLs in `jobs/_scans/seen.json` and print only new ones. A posting older than about 5 weeks is a low-chance lead.

## Hard filters before anything else

- Work model and location: the posting must fit the profile (`require_fully_remote`, country eligibility). Read the location line and the full description. Reject restrictions that exclude the candidate's country ("US only", "must reside in...") when no contractor or employer-of-record route exists. A title that lists countries means those countries only.
- Pay below the profile's floor, when stated, is a skip. Unstated pay is "unknown", not neutral.
- Everything in the auto-skip list of `target-roles.md`.

## Process

1. Load `.claude/memory/target-roles.md`, `.claude/memory/MEMORY.md` and `.claude/memory/honesty-guardrails.md`.
2. Score each candidate posting with `.claude/skills/job-scoring/SKILL.md`.
3. Passes (check live with `python scripts/check_live.py <url>`) get a folder `jobs/YYYY-MM-DD_company_role/` with `posting.md` (text, apply link, posting date) and the score card and gap note, then go to `resume-drafter`. Register each: `python scripts/tracker.py add ... --status drafted`.
4. Failures are logged in `.claude/memory/application-log.md` with the specific reason and are not drafted. A flagged posting is drafted only when the candidate brings it or explicitly overrides the flag.
5. Skip postings already in `application-log.md`, `jobs/` or `jobs/_archive/`.
6. Do not ask the candidate questions mid-run. Use safe defaults and record uncertainty in the gap note.

## What this agent must not do

- Submit anything. The candidate applies personally from the link.
- Claim in any draft that the candidate used a tool or process that is not recorded in the memory files.
