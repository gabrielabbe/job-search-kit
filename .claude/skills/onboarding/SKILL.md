---
name: onboarding
description: The first-run interview that builds the candidate's profile, evidence base, skills, target roles and search profile from their own answers. Use whenever scripts/onboarding_status.py says ONBOARDING REQUIRED, and again when the candidate's situation changes.
---

# Onboarding interview

This project starts empty. Everything it knows about the candidate comes from this interview and from documents they hand over. Nothing is assumed, nothing is copied from anyone else, and nothing is invented. The interview is also how the honesty rules get their facts: a resume line can only be as strong as what the candidate told you here.

## How to run it

- **Start on the very first message**, whatever it says. Greet them, explain in two sentences ("I'll interview you in short rounds. Everything you tell me is saved on this computer in this folder and is used to find roles, tailor resumes and write application answers, and I never state anything about you that you haven't told me."), then begin Round 1. If they asked something else first, answer it in a few lines and then begin.
- **Short rounds, 3 to 6 questions each**, never a wall of questions. Ask, wait, record, then move on. Tolerate "skip" and "later".
- **Record as you go.** After every round, write what was said into the memory files and the evidence base before asking the next question. Do not wait for the end. Set `ONBOARDING_STATUS: IN_PROGRESS` in `.claude/memory/profile.md` at the first round and mark each round done there, so a new session resumes where this one stopped.
- **Use their words and their numbers.** Never round up, never improve, never add a tool or title they did not name. If a number sounds large or vague, ask what it counts and how it was measured.
- **Mark certainty.** Something said once is `candidate_reported`. Something they re-confirm after you read it back is `candidate_confirmed`. Something shown in a document (resume, diploma, offer letter, performance review) is `document_verified`.
- **Ask what must stay private.** For every number or fact about an employer (budget, revenue, headcount, customers, internal tools), ask: "Is this public? May I put it on a resume or a website?" Record the answer as the record's `disclosure` (`approved` or `restricted`). Restricted facts are used only to understand the candidate, never published.
- **Ask for documents.** Invite them to drop their current resume, LinkedIn export or any performance reviews into `reference/`. Read them, extract claims as `document_verified` or `candidate_reported`, and read the extracted facts back to the candidate for confirmation. A resume is a claim, not a proof: if it conflicts with what they say, write the conflict into the record's `conflicts` list and ask.
- **No em dashes** in anything written for the candidate to use.
- **Do not coach them into stretching.** If they want to claim something unproven, record the true version and tell them plainly why (see `honesty-guardrails.md`).

## Where each answer goes

| Answer | File |
|---|---|
| Name, contact, location, languages, education, certifications | `.claude/memory/profile.md` |
| Each job: title, dates, scope, actions, outcomes | `.claude/memory/experience.md` and one evidence record per achievement or role (`python scripts/evidence_tool.py add-record --json '{...}'`) |
| Tools, platforms, methods, self-ratings | `.claude/memory/skills-tools.md` and `python scripts/evidence_tool.py add-skill --json '{...}'` |
| Real anecdotes that work in interviews | `.claude/memory/signature-stories.md` |
| Direction, titles, pay, work model, hard no's | `.claude/memory/target-roles.md` and `config/search-profiles.yaml` |
| Name, LinkedIn, one-line pitch, three proof points | `data/profile/outreach.json` (copy of `config/outreach.example.json`) |
| Rules the candidate sets for themselves | `.claude/memory/honesty-guardrails.md` ("Decided by the candidate" section) |

## Rounds

### Round 1: basics (5 minutes)
Full name as it should appear on resumes. City and country they live in. Citizenship and work authorization (this decides which employers can hire them, so ask plainly: "Which countries could you legally work in without sponsorship, and do you work as an employee, a contractor or both?"). Languages with an honest level for each. Time zone and the hours they can work. Contact details for resumes (email, phone, LinkedIn, portfolio or website) and whether a different phone or email should be used for employers in different countries.

### Round 2: the goal (5 minutes)
What kind of work, in their own words, and the job titles they would be happy to hold. What level (individual contributor, manager, director, executive). Industries they prefer or want to avoid. Where the career should be in 3 to 5 years. Work model: fully remote, hybrid or on-site; if hybrid is acceptable, how many office days; is relocation or travel acceptable. Pay: currency, the monthly (or annual) minimum they would accept, a good number, a great number, and employee versus contractor. What they will never do or accept (hard no's: industries, travel, on-call, overnight hours, a given employer). How fast they need a job (urgent or exploring). Where they have already applied, if anywhere (so duplicates are avoided).

### Round 3: work history, one employer at a time (10 to 20 minutes)
For each job, newest first, going back far enough to cover everything relevant (usually 10 to 15 years):
- Employer, title, start and end month, full or part time, employee or contractor.
- Who they reported to, how many people reported to them (and whether those were employees or contractors), team size, budget or revenue they were accountable for, customers or users supported. Ask for numbers and what each number counts.
- What they actually did day to day, then the 3 to 5 things they are proudest of there.
- For each achievement: the problem, what they personally did (not the team), the tools used, the result, a number if one exists, how the number was measured, what it was before. If there is no number, record that honestly. "I think", "about" and "I estimate" are recorded as such.
- What of this is confidential.
- A title change, promotion or reorganisation: what happened and when.

One evidence record per role and per major achievement. Fields: `employer`, `role`, `period` (`start` and `end` as YYYY-MM, `end` null if current), `claim` (one factual sentence), `ownership` (`accountable`, `led_team`, `individual_contributor`, `contributor`), `reporting_line`, `scope` (only the keys the schema allows), `actions`, `technologies`, `outcomes`, `verification`, `confidence`, `disclosure`, `conflicts` (open questions), `tags`. Read `data/evidence/schema.json` if unsure.

### Round 4: skills and tools (10 minutes)
Go through the tools and methods in their field (offer a checklist based on their target roles and let them add). For each: have you used it, how, how recently, and the best concrete example. Self-rate 1 to 5 (1 heard of it, 3 can do tasks with help, 4 independent and productive, 5 could teach or design with it). A 4 or 5 needs a named concrete use: no example means 3 at most, recorded as such. Separate three lists: tools they use, things they are studying (listed as "in progress" with an expected date, never as "known"), and things they have not done. Certifications: held (with issuer and date), in progress (with expected date), planned. Education: degree, field, school, year, whether complete. Record every gap honestly: gaps drive the gap notes later.

### Round 5: stories (10 minutes)
Four or five real stories they could tell in an interview: a project they are proud of, a failure and what they learned, a conflict or disagreement and how it ended, a time they led without authority, a time they saved money or time. Ask for specifics: where, when, who, what happened, what they did, how it ended. Never write a story for them. If they cannot recall specifics, store the topic as "candidate story, details pending".

### Round 6: resume and application preferences (3 minutes)
Which language or languages their resumes should be in. One page or two. Whether a years-of-experience figure should appear on resumes (default: no figure unless every year is backed by dated roles). Anything they do not want on a resume (an old employer, a gap, a short job). How they want to be described in a one-line title. LinkedIn headline and about text if they have it.

### Round 7: confirm, then build
1. Read the whole profile back in short sections: identity, goal, each role with its numbers, skills with ratings, gaps. Ask them to correct anything. Update records to `candidate_confirmed` for what they confirm.
2. Fill `config/search-profiles.yaml` profile `default`:
   - `onboarded: true`, `candidate_name`, `candidate_country` (ISO code), `country_name`.
   - `location_terms`: the country name in the local language and English, its main cities, and the regions that include it.
   - `require_fully_remote`: true or false from Round 2.
   - `pay`: floor, good and sweet-spot monthly numbers in `currency_reference`; add the fx rate for their currency to `fx_to_usd` if missing.
   - `seniority_target` (1 to 5).
   - `role_families`: group their target titles into 3 to 6 families with `level` (`north_star`, `target` or `adjacent`) and `terms` (the exact title phrases that appear on job postings: use their stated titles plus the common variants; write terms in the languages of the job boards they will search).
   - `exclude_title_terms`: titles that mean "not for me" from their hard no's.
   - `domains`, `extra_title_terms`.
3. Create `data/profile/outreach.json` from `config/outreach.example.json` using confirmed facts only (name, LinkedIn, a location sentence, a one-line pitch, three proof points).
4. Write `.claude/memory/target-roles.md` (direction, comp, what to apply to, auto-skip patterns, flag-instead-of-draft cases) and `.claude/memory/profile.md` in full, with the line `ONBOARDING_STATUS: COMPLETE`.
5. Run `python scripts/evidence_tool.py validate`, `python scripts/tracker.py seed`, then `python -m jobintel doctor` with `PYTHONPATH=src` (or `jh doctor`). Fix anything that fails.
6. Offer the next step: run the first scan (`python scripts/scan_jobs.py` and `python scripts/scan_boards.py`, then `jh ingest` and `jh search`), explain the folders in two sentences, and remind them that nothing is ever submitted for them.
7. Record in `.claude/memory/MEMORY.md` that onboarding finished and when.

## Re-running or extending
When the candidate has a new job, a new certificate, a changed goal or says "that's no longer true", update the evidence records (do not delete history; set the old fact's `period.end` or add a `conflicts` note), the memory files and the search profile together. Re-run the rounds that changed. A resume must always be built from the current confirmed state.

## What a good interview looks like
They leave with: a profile they have read and corrected; a skills list with honest ratings and clear gaps; 5 to 15 evidence records with numbers and their basis; four or five stories; a search profile that reflects their real constraints; and the knowledge that anything unproven will be marked `[REPLACE: ...]` for them rather than invented.
