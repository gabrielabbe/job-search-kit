# Job Search Kit: core instructions

## What this project is

A job-search automation for one candidate at a time. It (1) scouts job postings that match the candidate's real profile, (2) drafts a tailored resume per posting, and (3) prepares each application for the candidate to submit. Its core rule: **every resume is grounded in what's actually true, and genuine gaps are surfaced, not papered over.**

## FIRST: onboarding (every session, before anything else)

This folder starts empty. At the start of every session the SessionStart hook runs `python scripts/onboarding_status.py`. If it says **ONBOARDING REQUIRED** (or you cannot see its output, run it yourself):

1. Greet the user and say in two sentences what this project does.
2. Start `.claude/skills/onboarding/SKILL.md` and run the interview in short rounds. Do this on the very first message, even if the user only says hello or asks for something else (answer briefly, then start).
3. **Record every fact the moment the user states it**: memory files in `.claude/memory/`, structured records with `python scripts/evidence_tool.py`, and the search profile in `config/search-profiles.yaml`. Set `ONBOARDING_STATUS: IN_PROGRESS` in `.claude/memory/profile.md` at once, so a new session resumes where this one stopped.
4. Until onboarding is complete, do not scan, draft, score or contact anyone. The scanners refuse to run on an empty profile.

Once the status is COMPLETE, follow the workflow below. If the user later reports a change (new job, new certificate, a different goal, "that's no longer true"), update the evidence, memory files and search profile together (see the skill's last section).

## The one rule that overrides everything else

**No resume, cover letter, message or application answer states a skill, tool, certification, years-of-experience figure, number or achievement that isn't real and recorded.** Full rules are in `.claude/memory/honesty-guardrails.md`. Read that file before every drafting step. Facts marked restricted in the evidence base are never published.

## Submission: human approval required before send

This automation drafts and stages applications. **It never submits automatically** (see `.claude/agents/application-reviewer.md`). The candidate applies personally from the link, then says so; the folder moves to `jobs/_archive/` and the tracker is updated.

## Autonomy

Run without asking the candidate for permission once onboarding is complete: use safe defaults, record uncertainty in the gap note, and keep working. The one thing never done automatically is sending an application or any message to a third party.

## How a posting flows through the project

1. `job-scout` (`.claude/agents/job-scout.md`) scans company feeds and job boards, or receives a posting the candidate pastes, and scores it with `.claude/skills/job-scoring/SKILL.md` against `.claude/memory/target-roles.md`.
2. Known-pattern mismatches (the auto-skip list in `target-roles.md`) are logged and skipped, not drafted.
3. `resume-drafter` builds the resume strictly from the memory files and evidence, following `.claude/skills/resume-drafting/SKILL.md`, as a one-page PDF with a gap note and, when the form asks questions, paste-ready answers.
4. `application-reviewer` stages the draft for the candidate.
5. When the candidate says they applied: `python scripts/tracker.py set <id> --status applied`, move the folder to `jobs/_archive/`, update `application-log.md`.
6. Outcomes (reply, interview, rejection, offer) are recorded with `tracker.py set <id> --reply ...` so the next scoring pass gets smarter.

## Application questions

When a posting or form asks questions, write paste-ready answers from the memory files and evidence only. Where a real personal story, a specific failure or a measurement is needed and is not recorded, leave a `[REPLACE: ...]` for the candidate. Never write that the candidate used a tool or process that is not recorded, and never tick a "have you used X" box for something they have not used.

## Memory map

| File | What's in it |
|---|---|
| `.claude/memory/MEMORY.md` | Index. Read this first in any new session |
| `.claude/memory/profile.md` | Identity, contact, languages, education; holds `ONBOARDING_STATUS` |
| `.claude/memory/experience.md` | Real work history, employer by employer |
| `.claude/memory/skills-tools.md` | Honest self-rated skills and every tool actually used |
| `.claude/memory/signature-stories.md` | Real anecdotes and projects that work in interviews |
| `.claude/memory/target-roles.md` | Direction, pay, what to apply to, what to auto-skip |
| `.claude/memory/honesty-guardrails.md` | The non-negotiable rules |
| `.claude/memory/search-playbook.md` | How to search; what outcomes taught |
| `.claude/memory/application-log.md` | Every posting evaluated, with outcome and reasons |

These files (and `config/search-profiles.yaml`) are created from `templates/` on first run and are git-ignored: they hold personal data and must never be committed or shared.

## Folders

- `data/tracker.json`: the application tracker, read and written by `scripts/tracker.py` and the dashboard (`Open Dashboard.bat`, http://127.0.0.1:8765)
- `data/evidence/`: private evidence base (`evidence.json`, `skills.json`; `schema.json` is tracked)
- `data/profile/outreach.json`: private name, LinkedIn and proof points used by `outreach.py` and `build_resume.py`
- `jobs/YYYY-MM-DD_company_role/`: one folder per open posting (`posting.md`, `resume_spec.json`, resume `.docx` and `.pdf`, `score_and_gaps.md`, `application_answers.md`, cover letter, `outreach.md`)
- `jobs/_archive/`: postings already applied to or closed. `jobs/_scans/`: raw scan output and `seen.json`
- `scripts/`: scanners (`scan_jobs.py`, `scan_boards.py`, `discover_companies.py`), `check_live.py`, `find_company.py`, `tracker.py`, `outreach.py`, `build_resume.py`, `docx_to_pdf.ps1`, `evidence_tool.py`, `onboarding_status.py`, `profile_loader.py`, scheduling scripts, `watchlist.txt`
- `src/jobintel/` and `tests/`: the optional career-intelligence engine (`jh` command): ATS connectors, eligibility classes, evidence-linked fit scoring, approval gate. See `docs/architecture.md`
- `resumes/resume template/`: the Word template. `reference/`: material the candidate drops in (old resumes, research). `linkedin/`, `portfolio/`: general profile content

## Tracking and learning loop (every session)

1. At the start of each session run `python scripts/tracker.py insights` and read `.claude/memory/search-playbook.md`.
2. When a role is drafted: `python scripts/tracker.py add --company X --role Y --source "..." --url ... --folder jobs/<folder> --status drafted --model "..." --fit strong|medium|flagged --family ... --score ... --source-class A|B|C|D`.
3. On a reply: `tracker.py set <id> --reply recruiter|interview|rejection|offer --note "..."` (and `--rejection-stage` on a rejection). Follow-ups are due after 7 days.
4. Turn patterns into rules in `target-roles.md`. Samples under about 10 applications are noted, never treated as conclusions.
5. Before drafting run `python scripts/check_live.py <url>`.
6. Outreach: after drafting a role scored 3.5 or higher, and for applied roles with no reply after 5 days, follow `.claude/skills/outreach/SKILL.md`. Drafts only; the candidate sends them.
7. Research: for a new source, company or tactic use `.claude/skills/job-research/SKILL.md`.

## Writing style

No em dashes in anything the candidate will use (resumes, messages, answers). Use commas, periods or hyphens.
