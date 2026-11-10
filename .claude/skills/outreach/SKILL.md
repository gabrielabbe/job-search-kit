---
name: outreach
description: Find the right people at a company for a promising application (recruiter, hiring manager, People lead) and draft the email, LinkedIn note and follow-up for the candidate to send. Use after drafting a resume for any role scored 3.5 or higher, and for applied roles that have no reply.
---

# Outreach

A direct, short note to the person running the process lifts reply rates more than any resume edit. This skill finds that person and drafts the message. It never sends anything.

## 1. Find the people (public information only)

Run bounded WebSearch queries (standard mode, 3 to 5 queries per company), then record up to three contacts:

1. **Recruiter or talent partner** for that function or region. Queries: `"<company>" talent acquisition recruiter <function or region>`. Open recruiting job postings at the company also reveal the team and titles.
2. **Hiring manager**: the person the role reports to. The posting often says "reports to" or names the team; search `"<company>" "<department head title>"`.
3. **People or Talent lead** as the fallback.

For each contact write name, title, the source URL and a confidence note. Third-party pages (aggregators, repost sites) are `unverified`: tell the candidate to confirm on LinkedIn that the person still works there and still does that job. If nothing reliable turns up, give the exact LinkedIn search strings instead of inventing a name.

## 2. Hard rules

- Use names and titles from public pages only. LinkedIn itself cannot be scraped; do not try to get around that.
- Use an email address only if the company or the person published it. Never guess or pattern-match addresses, never test addresses, never use data-broker sites.
- Never contact anyone on the candidate's behalf. The drafts are for them to review and send from their own account.
- Honesty rules apply in full (`.claude/memory/honesty-guardrails.md`): proof points come only from the candidate's confirmed evidence and stories. No new numbers, no tools they have not used, no start date or notice period unless they give one.

## 3. Draft with `scripts/outreach.py`

```
python scripts/outreach.py --company "<Company>" --role "<Role>" --url <posting url> \
  --folder <job folder> --track <proof set> [--contact "Name" --title "Title"] [--applied] [--lang en|pt] \
  [--research notes.txt] --tracker-id <tracker id>
```

It reads the name, LinkedIn, location sentence and proof points from `data/profile/outreach.json` (written during onboarding), writes `outreach.md` in the job folder (email, LinkedIn note under 300 characters, 7-day follow-up) and sets outreach to `drafted` in the tracker. `--track` picks one of the proof-point sets in that file. Put contact research in a notes file and pass it with `--research`.

## 4. After the candidate sends

`python scripts/tracker.py set <id> --outreach sent` (or the dashboard), later `--outreach replied`. The dashboard's "Outreach effect" table compares reply rates with and without a message, so the loop teaches itself which approach works.

## Timing

Send within a day of applying. Follow up once after 7 days, then stop. Warm contacts (a recruiter who already wrote) get a reply, not a cold template.
