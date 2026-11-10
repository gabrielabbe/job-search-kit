# Remote Job Intelligence — VS Code Agent Workspace

A **three-agent**, evidence-based workflow for discovering remote jobs, ranking the best opportunities, and preparing truthful applications plus targeted recruiter outreach.

**Goal:** search broadly, verify remote-from-anywhere eligibility, evaluate ~100 relevant opportunities, and prioritize up to 10 worth pursuing. The number 10 is a ceiling, not a requirement: return fewer if fewer pass the gates.

## Install in VS Code

1. Open this entire folder as your **workspace** in VS Code with GitHub Copilot Chat or an appropriate VS Code agent harness.
2. Keep the folder structure below. The three `.agent.md` files must live under `.github/agents/`; the `.prompt.md` file must live under `.github/prompts/`.
3. Copy `data/candidate-profile.template.md` to `data/candidate-profile.md`. Complete the verified work history, accomplishments, preferences, salary expectations, current country, and eligibility constraints. **Do not commit personal data or credentials to a public repository.**
4. Open Copilot Chat with the supported **Local** harness if you want to invoke the reusable prompt with `/run-job-search`. Custom agents can also be selected individually in the agent picker; supported features depend on your harness.
5. Enable lawful, supported web search/browsing or job-board integrations if you want live discovery. Without them the workflow cannot verify current openings. Run `/run-job-search` and ask for a 100-to-10 funnel.
6. Review the generated shortlist, tailored documents, and outreach drafts before any external action.

## Folder map

```text
remote-job-agent-workspace/
├── README.md
├── AGENTS.md
├── .github/
│   ├── agents/
│   │   ├── job-scout.agent.md
│   │   ├── fit-analyst.agent.md
│   │   └── application-strategist.agent.md
│   └── prompts/
│       └── run-job-search.prompt.md
├── data/
│   └── candidate-profile.template.md
└── docs/
    ├── data-contracts.md
    └── research-notes.md
```

## The three agents

| Agent | Main question | Deliverable |
|---|---|---|
| **Job Scout** | Is this a real, open job that this candidate could actually work remotely? Who is the appropriate contact? | `output/01-opportunities.md` |
| **Fit Analyst** | How strong is the verified fit, and is applying worth the effort? | `output/02-shortlist.md` |
| **Application Strategist** | How do we present verified evidence clearly and communicate with the right human? | `output/applications/<job-id>/application-package.md` |

The `run-job-search` prompt is a **workflow recipe**, not a production job-board crawler or unattended agent scheduler. Depending on tools available, it may execute all three phases in one conversation or guide you through separate agent runs. Actual recurring searches, contact enrichment, application submission, email delivery, and performance dashboards require integrations and permissions you configure separately. Nothing is sent or submitted by these Markdown files alone.

## Example requests

- Select **Job Scout**: `Find 100 current, genuine work-from-anywhere openings relevant to my verified candidate profile. Verify application links and contact information where available.`
- Select **Fit Analyst**: `Evaluate output/01-opportunities.md using hard eligibility gates and the evidence rubric. Return at most 10 priorities.`
- Select **Application Strategist**: `For the top three approved jobs in output/02-shortlist.md, draft tailored, evidence-backed application packages and personalized recruiter outreach. Do not submit.`
- Or use `/run-job-search` for the entire 100-to-10 workflow when supported.

## Validation checklist

- [ ] All three agent files appear in the agent selector.
- [ ] `data/candidate-profile.md` contains verified candidate facts, not placeholders.
- [ ] Each listed opportunity has a real source URL and verification date.
- [ ] Remote eligibility is `confirmed`, `unverified`, or `ineligible` with specific evidence.
- [ ] Every fit claim is linked to a profile fact.
- [ ] Contacts are sourced and role-matched; no invented emails.
- [ ] No application or outreach goes out without explicit approval.

## Useful documentation

- [VS Code custom agents](https://code.visualstudio.com/docs/agent-customization/custom-agents)
- [VS Code prompt files](https://code.visualstudio.com/docs/agent-customization/prompt-files)
- [VS Code project instructions](https://code.visualstudio.com/docs/agent-customization/custom-instructions)
- [Research references and design caveats](docs/research-notes.md)
