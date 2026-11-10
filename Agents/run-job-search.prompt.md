---
name: run-job-search
description: Run the three-stage, evidence-based remote job discovery, ranking, and application drafting workflow.
agent: agent
argument-hint: '[desired discovery count, e.g. 100; priority count, e.g. 10; optional role focus]'
---

# Run the Remote Job Intelligence workflow

Read [project rules](../../AGENTS.md), [candidate profile](../../data/candidate-profile.md), [data contracts](../../docs/data-contracts.md), and the three phase instructions: [Job Scout](../agents/job-scout.agent.md), [Fit Analyst](../agents/fit-analyst.agent.md), and [Application Strategist](../agents/application-strategist.agent.md).

## Defaults

- Discover up to **100 genuine current job postings** relevant to the candidate's profile (or user-specified number).
- Prioritize **up to 10** qualified, eligible openings (or user-specified number).
- Respect the candidate's true global-work and location criteria; never assume all remote jobs are location-independent.
- Draft application packages for the highest-priority **up to 3** opportunities unless otherwise specified. Do not apply or send messages.

## Execute the stages in this sequence

1. **Scout:** Research current listings with actual approved web/job APIs where available. Verify canonical source and geographic eligibility; deduplicate; look for role-relevant professional contacts. Save results to `output/01-opportunities.md`.
2. **Analyst:** Apply hard gates; compare job requirements to candidate evidence using the rubric; assign separately documented fit/priority/confidence; select up to 10 and save `output/02-shortlist.md`.
3. **Strategist:** For the top approved subset, draft tailored résumé, cover letter, screening answers, company brief, verified-contact leads, and personalized outreach in `output/applications/<job-id>/application-package.md`.
4. **Report:** Provide counts per stage, the priority shortlist with evidence/eligibility confidence, URLs for real jobs, missing information that can change decisions, and exact next steps requiring human approval.

## Tool and workflow limitations

- This is a **sequential orchestration prompt**. It references each agent's specialist playbook; whether it can delegate actual subagent calls depends on the active VS Code harness and enabled tools. Follow the playbooks in sequence even if delegation is unavailable. Do not claim to have invoked subagents unless you really did.
- Web access unavailable? Do not invent current jobs. Instead give a concrete, reproducible search plan/queries and the integration or permission needed, then pause live discovery.
- Candidate profile missing or incomplete? Request the *smallest* essential details. Do not infer qualifications from placeholders.
- Output size or time constraints? Deliver verified partial progress with exact counts and remaining tasks. Do not fill gaps with fabricated data.
- Sending messages/applications and changes to external accounts require explicit human approval and suitable integrations. **Never auto-submit.**

## End state

Provide only real, verifiable job records. Prefer 6 outstanding opportunities over 10 misleading ones. Success means a useful, reviewed shortlist and strong draft packages, not a large number of low-quality applications.
