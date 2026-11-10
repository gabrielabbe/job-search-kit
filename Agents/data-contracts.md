# Data contracts, decisions, and scoring

This document defines the interface between the three specialized agents. All actual outputs are Markdown. Embedded YAML/JSON examples are **illustrations**, not real opportunities or people.

## Contract A — Job Scout → Fit Analyst

Required job attributes:

| Field | Meaning |
|---|---|
| `job_id` | Stable source-derived ID; never reused for a different requisition. |
| `company`, `role_title` | Employer/role as explicitly published. |
| `canonical_url`, `apply_url` | Evidence-backed URLs; `unknown` when unavailable. |
| `source_type`, `source_url` | Official employer/ATS vs aggregator or third party. |
| `checked_at` | Actual last verification timestamp; don't fake it. |
| `posting_status` | `OPEN`, `UNVERIFIED`, `CLOSED`, or `SUSPECTED_SCAM`. |
| `remote_class` | `CONFIRMED_GLOBAL`, `CONFIRMED_COUNTRY`, `CONFIRMED_REGION`, `UNVERIFIED`, or `INELIGIBLE`. |
| `remote_evidence` | Source and wording supporting geographic eligibility. |
| `time_zone_limits`, `residency_limits` | Explicitly published conditions or `unknown`. |
| `contract_type` | Employee, contractor, both, or unknown. |
| `compensation` | Published amount + currency + period or unknown. |
| `required_competencies` | Source-grounded mandatory tasks/skills. |
| `preferred_competencies` | Source-grounded nice-to-have skills. |
| `contact_leads` | Only sourced and permission-compliant professional leads. |
| `red_flags` | Fraud, outdated posting, third-party inconsistencies, etc. |

**Do not** infer that a role is global solely because a job board tags it "Remote". A posting that accepts residents of the candidate's country but requires citizenship or permanent residency is not confirmed work-from-anywhere.

## Contract B — Fit Analyst → Application Strategist

Required decision attributes:

| Field | Meaning |
|---|---|
| `job_id` | Reference back to Agent One. |
| `gate_decision` | `PASS`, `HOLD_UNVERIFIED`, `FAIL`. |
| `hard_gate_reasons` | Exact constraint, candidate fact, and source. |
| `evidence_matrix` | Requirement → candidate evidence ID → rating and confidence. |
| `fit_score` | Experimental 0–100 competency score or provisional band. |
| `desirability_score` | 0–100 preference alignment index, explained. |
| `contactability_score` | 0–100 access-to-human index, explained. |
| `hiring_signal_score` | 0–100 active-hiring evidence index, explained. |
| `priority_score` | Combined score **for PASS jobs only**. |
| `confidence` | `HIGH`, `MEDIUM`, `LOW` based on evidence completeness and freshness. |
| `decision` | `PRIORITY`, `REVIEW`, `DEFER`, `EXCLUDE`. |
| `open_questions` | Important uncertainty to resolve before submission. |

### Scoring

Convert each evidenced 0–4 rating to a 0–100 scale. Initial unvalidated rubric:

`fit = 35% required competencies + 25% achievements + 15% seniority + 10% domain + 15% career alignment`

For `PASS` jobs only:

`priority = 45% fit + 25% desirability + 15% contactability + 15% hiring signal`

**Important:** Those numbers are **heuristics**, not calibrated probabilities. Unknown evidence must be reported separately. Do not hide missing evidence inside a false sense of precision.

**Shortlist ceiling:** Top **10** only if enough jobs pass all gates. If worldwide mobility is a hard requirement, region-only positions should be separated into an alternative list, not silently ranked as global.

## Contract C — Strategist package

Each job gets `output/applications/<job-id>/application-package.md`:

```markdown
# <Company> — <Role> (<job_id>)
## 1. Job snapshot and eligibility
## 2. Requirement-to-evidence map
## 3. Tailored résumé — DRAFT
## 4. Cover letter — DRAFT
## 5. Screening questions and truthful answers
## 6. Verified contact intelligence
## 7. Outreach drafts — NOT SENT
## 8. Interview preparation and source links
## 9. Candidate approval checklist and status
```

All text must be sourced to the profile, the original job description, or explicitly labeled inference. The applicant verifies all personal details and specific answers. Contact research must not reveal private personal information.

## Suggested status machine (for future application code)

`DISCOVERED -> VERIFIED -> GATE_PASS / GATE_HOLD / GATE_FAIL -> SCORED -> PRIORITIZED -> PACKAGE_DRAFT -> REVIEW_APPROVED -> SUBMITTED -> FOLLOW_UP_DUE -> INTERVIEW / REJECTED / OFFER / CLOSED`

- `SUBMITTED` requires actual evidence of successful submission; no leap from `REVIEW_APPROVED`.
- `FOLLOW_UP_DUE` is a *suggestion* until an outbound channel is legitimately connected and authorized.
- Log `application_source`, `outreach_source`, response dates, interview outcome, and notes; allow an opt-out state.

## Outcome feedback and tests

Track interviews per eligible application, replies per legitimately delivered outreach, and offer quality. Analyze by source, job family, location eligibility, résumé version, contact path, and application date. Beware selection bias: referred applicants and inbound applicants may differ systematically, so observational response rates don't prove causality.

Basic quality tests:

1. A "US only" posting **fails** worldwide eligibility for a resident of another country unless separate authorized arrangement is established.
2. A "Remote" listing with no geographic conditions is `UNVERIFIED`, not `CONFIRMED_GLOBAL`.
3. An attractive role with a mandatory unheld license is `FAIL` or held for verification, not fast-tracked.
4. A job with a sourced description but no real contact may still qualify; `contact_status = no_verified_contact`.
5. A skill absent from the candidate profile is unknown, not automatically false; a fabricated résumé bullet is prohibited.
6. No real web access yields zero **verified current postings**, not invented filler.
