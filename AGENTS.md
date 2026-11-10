# AGENTS.md

Read `CLAUDE.md` first. It is the source of truth for this project (onboarding first, honesty rules, the no-auto-submit gate, memory map). This file is for other coding agents.

## Hard rules

- Never submit an application or send a message to a third party. Drafts only.
- Never state a fact about the candidate that is not in `.claude/memory/` or `data/evidence/`. Restricted facts are never published.
- "Remote" never means "worldwide". Eligibility is judged for the country in the candidate's profile and records its evidence.
- Never scrape LinkedIn, Indeed or Glassdoor. Respect robots.txt, rate limits and 429 responses; stop on 401 or 403.
- Personal data stays local: `.claude/memory/`, `config/search-profiles.yaml`, `data/`, `jobs/`, `reference/`, `linkedin/`, `portfolio/` are git-ignored. Do not commit or print them.

## Commands

- Tests: `python -m pytest -q` (no network).
- Engine CLI: `jh` or `PYTHONPATH=src python -m jobintel` (doctor, sources-test, ingest, search, shortlist, draft, evidence, approve, confirm-submitted, health, run).
- Onboarding state: `python scripts/onboarding_status.py`.
- Evidence base: `python scripts/evidence_tool.py list|add-record|update-record|add-skill|validate`.

## Layout

`src/jobintel/` (engine), `tests/` (fixtures, no network), `scripts/` (scanners, tracker, builders), `config/` (`sources.yaml`, `outreach.example.json`), `templates/` (blank memory files and search profile copied on first run), `docs/` and `Agents/` (design notes and reference prompts).
