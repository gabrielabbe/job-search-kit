# Job Search Kit

A personal job-search assistant that runs inside [Claude Code](https://claude.com/claude-code). It interviews you once, then:

1. **Finds** postings that match your real profile (company career pages and remote job boards), checks you can actually work for each one from your country, and ranks them.
2. **Drafts** a one-page resume, a gap note and paste-ready application answers for each good match, using only facts you confirmed.
3. **Stages** everything for you. **You** press the apply button. The kit never submits anything and never contacts anyone for you.
4. **Tracks** every application and learns from the replies.

Its one rule: nothing on a resume or in an answer that isn't true and recorded. Gaps go in a private note, not on the page.

## Start here (10 minutes)

1. Install [Claude Code](https://claude.com/claude-code) and Python 3.11 or newer.
2. In this folder run `pip install -r requirements.txt`.
3. Open this folder in Claude Code and say **hello**. The first thing it does is interview you in short rounds: who you are, where you live and can work, what you want, your work history with real numbers, your skills with honest ratings, and your stories. It saves each answer as you give it, so you can stop and resume any time.
4. Optional: put your current resume or LinkedIn export in `reference/` before you start. Claude reads it and asks you to confirm each claim.
5. When the interview ends, say **"run the first scan"**.

Word is needed only to turn resumes into PDF (`scripts/docx_to_pdf.ps1`, Windows). Without it you get the .docx.

## Privacy: read this before you use Git

Everything personal about you is created on your computer and is git-ignored: `.claude/memory/`, `config/search-profiles.yaml`, `data/`, `jobs/`, `reference/`, `linkedin/`, `portfolio/`, and generated resumes. **Do not remove those lines from `.gitignore` and do not push this folder anywhere public.** If you want a backup, use a private repository of your own.

## Day to day

| You say | It does |
|---|---|
| "Any new jobs?" | Runs the scanners, scores new postings, drafts the good ones |
| (paste a posting) | Scores it and drafts a resume if it clears your bar |
| "I applied" | Marks it applied, archives the folder, schedules a follow-up |
| "I got a reply / rejection" | Records it and updates what the search learns |
| "Open the dashboard" | `Open Dashboard.bat` shows what to apply to, what is waiting, what replied |

## What is inside

- `.claude/` agents and skills (scout, resume drafter, reviewer, outreach, scoring, research, onboarding)
- `scripts/` scanners, tracker, resume builder, outreach drafter, evidence tool
- `src/jobintel/` an optional engine with a database, geographic eligibility classes and evidence-linked fit scoring (`jh doctor`)
- `templates/` the blank memory files and search profile that onboarding fills in
- `docs/` how it is designed

## Tests

`python -m pytest -q` (no network needed).
