---
name: job-scoring
description: Score a job posting's fit before any resume-drafting work starts. Use this first, on every posting, before resume-drafting.
---

# Job Scoring

The point of this step is to not spend drafting effort, or a human review slot, on a posting the gap analysis already answers. Score before drafting, every time.

## Step 1: Hard filters (from `.claude/memory/target-roles.md` and `config/search-profiles.yaml`)

- **Work model and eligibility.** Does the posting fit the candidate's work model (fully remote, hybrid, on-site) and allow someone living in their country? On-site or hybrid when the profile requires remote, residency or work-authorization limits that exclude the candidate, or heavy travel: flag and stop, don't draft. A truly exceptional exception is flagged for the candidate to decide.
- **Pay.** Stated pay clearly below the floor in the profile: flag. Not stated: note "unknown".
- **Level.** A title far above the record (for example a C-level or VP role with no comparable scope held) or far below it: flag and stop.
- **Deep discipline not practiced.** Does it require several years in a technical or professional discipline the evidence base does not show? Flag and stop.
- **Portfolio gate.** If a public portfolio artifact is a hard gate, check `skills-tools.md` and the candidate's site before assuming it still applies.
- **Auto-skip patterns** in `target-roles.md`.

## Step 2: Fit scoring (for postings that pass Step 1)

Compare the posting's required and preferred qualifications against `experience.md`, `skills-tools.md` and the evidence base. For each requirement mark: **real and strong**, **real but partial**, or **not present**. A posting with mostly strong or partial matches and only a couple of "not present" items on the *preferred* list is a good candidate.

## Step 2b: Score card

Give each passing posting a 1 to 5 score on five dimensions, then one global score by judgment (not an average):

| Dimension | Question |
|---|---|
| Match with record | How much of the posting is real and strong in the memory files and evidence? |
| North star | Does it match the candidate's stated direction (`target-roles.md`)? An unrelated role scores 1, never "close enough". |
| Comp | Against the profile's floor, good and sweet-spot numbers. Unstated pay is "unknown", not neutral. |
| Culture and work model | Fit with the candidate's stated work model, hours and country. |
| Red flags | Country restriction in the body, office days, years in an unpracticed discipline, tools the candidate has never used. |

Reading the global score: 4.5 or more, draft immediately. 4.0 to 4.4, worth applying. 3.5 to 3.9, draft only if there is a named reason, and list it. Below 3.5, log and skip.

**Evidence confidence:** mark each dimension supported (read in the live posting), partial, or unknown. Missing evidence is never scored as neutral. Name up to three checks that could change the decision (for example "confirm country eligibility with the recruiter").

**Posting legitimacy:** age under 30 days is good, 30 to 60 mixed, over 60 weak; check the apply button is live; a vague description or the same role reposted twice in 90 days is a caution. Run `python scripts/check_live.py <url>` before drafting. Present these as signals, never as accusations.

## Country rules

- "Remote" with a salary band in one currency, local benefits or a city in the description is a role for that country. Companies that hire in the candidate's country say so in the posting itself.
- Part-time, contract and full-time are in scope unless the profile excludes them. Part-time or contract roles still need to clear the monthly pay floor pro rata.
- Postings in languages the candidate does not read at working level are flagged, not drafted.

## Step 3: Output

For every scored posting, write a short entry for `.claude/memory/application-log.md`: company, role, pass or flag decision, and the specific reasons (not just a score). This is what lets the patterns in `target-roles.md` get sharper over time.

## What "flag" means

A flagged posting is not deleted. It is logged with its reasons and held for the candidate's review, since some of the best matches are ones a purely mechanical filter would under-rate. The filters encode patterns that have repeatedly been real mismatches; they are a strong prior, not an infallible rule.
