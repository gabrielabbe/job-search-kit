---
name: resume-drafting
description: Draft a one-page, honestly-scoped, tailored resume from a job posting plus the memory files. Use for every posting that passes job-scoring (hasn't been auto-skipped).
---

# Resume Drafting

This method works because of what it refuses to do, not just what it includes: every line is grounded in the candidate's recorded facts, and genuine gaps are surfaced in a gap note instead of papered over.

## Before writing anything

1. Read `.claude/memory/honesty-guardrails.md`. Every draft starts here, not at the end as a check.
2. Read the full posting. Extract: required qualifications, preferred qualifications, actual day-to-day responsibilities, and anything that reveals culture and tone.
3. Read `.claude/memory/experience.md`, `skills-tools.md` and `data/evidence/evidence.json` side by side with the posting's requirements. Build two lists: **what is genuinely there to lead with**, and **what the posting wants that isn't real**.

## Structure

- **Header:** Name, location, phone, email, LinkedIn, in the form the candidate chose in onboarding for this employer's country.
- **One-line title** under the header, tailored to the posting's language, not a generic title.
- **Summary (3 to 5 sentences):** opens with a role descriptor matched to the posting. A years-of-experience figure appears only if the candidate allowed it in onboarding and the dated roles add up to it. Then the current roles and the 1 or 2 strongest genuinely relevant proof points for *this* posting, taken from `signature-stories.md`, not written from scratch.
- **Selected Skills:** one dense paragraph, not a long list: tools and competencies from `skills-tools.md`, worded to match the posting's vocabulary where honestly applicable.
- **Experience:** reverse-chronological, from `experience.md`. Order can change when a posting is closer to an earlier role's work.
- **Education and certifications:** from `profile.md`. In-progress certifications are "in progress, expected <date>", never held.
- **Tools and Languages:** final section.

Keep it to the page limit the candidate chose (default one page). Validate the output (page count, no stray em dashes, no invented contact details) before considering a draft done.

## Output and ATS

- Save the final resume as a **PDF** in `jobs/YYYY-MM-DD_company_role/`, with the source beside it.
- **ATS keywords:** use the posting's exact terms for tools, skills and titles wherever the skill is real, in Skills and in the bullets. Never add a keyword for something not recorded. A keyword that is a gap goes in the gap note.
- **Layout for ATS:** single column, standard headings (Summary, Skills, Experience, Education), no tables, text boxes or icons.
- **Cover letter:** write one whenever the application asks for or allows one, in the posting's language, with the same honesty rules.
- **Language:** follow the posting's language when the candidate reads and writes it at working level; keep documents in a weaker language plain and do not oversell it.
- **Restricted facts:** never publish a number from an evidence record whose `disclosure` is `restricted` or `unknown`. Say the capability without the number.

## Gap note (always produced alongside the resume)

A short, plain list: what the posting asks for that isn't honestly on the resume, and how severe each gap is. It travels with the draft to `application-reviewer`. It is not optional, and it is not softened. If the gap list is long and severe, the right output may be "don't draft this one, flag it" rather than a resume.

## Tone calibration

Match formality to the employer (a bank or enterprise reads differently from a remote-first startup), and match the language to the posting.
