# Architecture (as built 2026-11-06)

```
                    scripts/watchlist.txt (company registry, provenance)           config/search-profiles.yaml
                                   |                                                          |
 Greenhouse | Lever | Ashby | SmartRecruiters  (public APIs, rate limited, 401/403 stop)        |
            \  typed connectors: discover_companies / fetch_jobs / fetch_job / health_check     |
             v                                                                                  |
   normalize -> eligibility (5 classes + evidence, judged for the candidate's country) -> SQLite store ------------+
                                  |   raw hash, versions, dedupe (id, canonical URL, fuzzy for review),
                                  |   closure only on an authoritative successful fetch, FTS5
                                  v
   search (hard filters first: status, eligibility, pay floor, title exclusions; then FTS5 bm25)
                                  v
   fit analyst (requirement -> evidence matrix, 0-4 ratings, fit / desirability / contactability / hiring signal /
                priority / confidence kept separate; unknown is not zero)  <---  data/evidence (private JSON, 5 verification states)
                                  v
   shortlist (PASS gate only, at most N) -> draft skeleton (Contract C, DRAFT_NOT_SENT)
                                  v
   claim check -> package (BLOCKED_CLAIMS | DRAFT_NOT_SENT) -> HUMAN APPROVAL (hash-bound) -> person submits -> reference recorded
```

## Modules (`src/jobintel/`)
| Module | Responsibility |
|---|---|
| `models.py` | `JobPosting`, `Company`, `FetchResult`, geography classes, HTML-to-text (untrusted input) |
| `http.py` | Pacing, timeouts, 429/Retry-After, backoff with jitter and caps, 401/403 stop, 404 not_found, injectable transport |
| `connectors/` | One class per ATS; reference-repo traps handled (see `docs/source-compliance.md`) |
| `eligibility.py` | `classify()` returns class, yes/no/unknown, quoted evidence, time-zone limits |
| `store.py` | SQLite + FTS5, migrations, versions, duplicates, source health, audit events |
| `search.py` | Hard filters then bm25; pay normalization that never defaults the period |
| `evidence.py` | Schema validation, verification states, `check_claim()` (numbers, direct reports, reporting lines, gaps) |
| `fit.py` | Deterministic fit and priority, gates, matrix, honest coverage |
| `contacts.py` | Sourced contacts only; no guessed or free-mail addresses; opt-out |
| `approval.py` | Package lifecycle and the approval gate; never sends anything |
| `pipeline.py` | Resumable steps logged in `pipeline_runs`; stops before approval |
| `cli.py` | `doctor`, `sources-test`, `ingest`, `search`, `shortlist`, `draft`, `evidence`, `approve`, `confirm-submitted`, `run` |

## Data separation
Public job data (`job_postings`, `job_versions`, `source_fetches`, `duplicates`) and candidate-private records (`data/evidence/*.json`, git-ignored) are separate. `job_postings.data_origin` marks `live` versus `fixture`; search and shortlist default to live only.

## What runs where
The existing Windows task `JobHunter-Scan` and the Claude agents are unchanged. The engine is an additional, tested path; moving the schedule onto it is decision P-4 and is not done.
