"""Draft the outreach messages for one application: an email, a LinkedIn note, and a follow-up.

Usage:
  python scripts/outreach.py --company Oyster --role "Senior AI Solutions Engineer" --url https://... \
      --folder jobs/_archive/2026-10-28_oyster_senior-ai-solutions-engineer --track ai \
      [--contact "Jane Doe" --title "Senior Global Recruiter"] [--applied] [--lang en|pt] [--tracker-id ID]

Writes <folder>/outreach.md and (with --tracker-id) records outreach status "drafted" in the tracker.
Messages use only facts recorded in .claude/memory (signature stories, experience), never invent numbers, never
promise a start date, and are never sent by this script. The candidate reviews and sends them personally.
--track picks one of the proof-point sets written during onboarding in data/profile/outreach.json (config/outreach.example.json shows the shape).
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tracker  # noqa: E402

ROOT = tracker.ROOT

PROFILE_FILE = ROOT / "data" / "profile" / "outreach.json"


def load_outreach_profile():
    """Name, LinkedIn, location sentence and proof points written during onboarding (private, git-ignored)."""
    if not PROFILE_FILE.exists():
        sys.exit("data/profile/outreach.json is missing. It is created by the onboarding interview "
                 "(see config/outreach.example.json for the shape).")
    return json.loads(PROFILE_FILE.read_text(encoding="utf-8"))


EN = {
    "email": """Subject: {role}: application sent, and a quick introduction

Hi {first},

I just applied for the {role} role at {company} ({url}) and wanted to introduce myself directly.

{p1} {p2}

{location_en} I would be glad to walk you through my track record on a short call any weekday.

My resume is attached and my LinkedIn is {linkedin}.

Thank you for your time,
{name}
""",
    "email_pre": """Subject: {role}: interested, and a quick introduction

Hi {first},

I am interested in the {role} role at {company} ({url}) and wanted to introduce myself before applying.

{p1} {p2}

{location_en} I would be glad to walk you through my track record on a short call any weekday.

Thank you for your time,
{name}
{linkedin}
""",
    "linkedin": "Hi {first}, I {verb} for the {role} role at {company}. {li_pitch} Would love to connect and share my background if useful.",
    "followup": """Subject: Following up: {role} at {company}

Hi {first},

A quick follow-up on my application for the {role} role ({url}). I remain very interested. {p3}

Is there anything else I can send to help your review? I am happy to jump on a call at your convenience.

Best,
{name}
""",
}
PT = {
    "email": """Assunto: {role}: candidatura enviada e uma breve apresentação

Olá {first},

Acabei de me candidatar à vaga de {role} na {company} ({url}) e quis me apresentar diretamente.

{p1} {p2}

{location_pt} Currículo em anexo e LinkedIn: {linkedin}.

Obrigado pela atenção,
{name}
""",
    "email_pre": "",
    "linkedin": "Olá {first}, {verb_pt} à vaga de {role} na {company}. {li_pitch_pt} Gostaria de me conectar e compartilhar minha experiência.",
    "followup": """Assunto: Retorno sobre a vaga de {role}

Olá {first},

Passando para reforçar meu interesse na vaga de {role} ({url}). {p3}

Posso enviar algo mais para ajudar na avaliação? Fico à disposição para uma conversa.

Abraço,
{name}
""",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--company", required=True)
    ap.add_argument("--role", required=True)
    ap.add_argument("--url", default="")
    ap.add_argument("--folder", default="")
    ap.add_argument("--track", default="default", help="proof-point set from data/profile/outreach.json")
    ap.add_argument("--contact", default="")
    ap.add_argument("--title", default="")
    ap.add_argument("--lang", choices=["en", "pt"], default="en")
    ap.add_argument("--applied", action="store_true", help="the application is already sent")
    ap.add_argument("--tracker-id", default="")
    ap.add_argument("--research", default="", help="path to a text file with contact research notes to embed")
    a = ap.parse_args()

    first = a.contact.split()[0] if a.contact else "there"
    t = (PT if a.lang == "pt" else EN)
    prof = load_outreach_profile()
    if a.track not in prof["proof"]:
        sys.exit(f"track '{a.track}' not in outreach.json; available: {', '.join(prof['proof'])}")
    p = prof["proof"][a.track]
    fields = dict(company=a.company, role=a.role, url=a.url, first=first, p1=p[0], p2=p[1], p3=p[2],
                  name=prof["name"], linkedin=prof["linkedin"], location_en=prof["location_en"],
                  location_pt=prof.get("location_pt", prof["location_en"]), li_pitch=prof["li_pitch"],
                  li_pitch_pt=prof.get("li_pitch_pt", prof["li_pitch"]),
                  verb="applied" if a.applied else "am applying", verb_pt="me candidatei" if a.applied else "vou me candidatar")
    email = t["email"] if a.applied or not t.get("email_pre") else t["email_pre"]
    notes = Path(a.research).read_text(encoding="utf-8") if a.research else "Contact research was not run for this role. Look for a recruiter or talent partner, the hiring manager (the person the role reports to), and the head of People."
    body = f"""# Outreach: {a.company}, {a.role}

Prepared {date.today().isoformat()}. Drafts only: nothing is sent automatically. Review, attach the resume PDF, and send from your own account.

## Who to contact

{a.contact + (' (' + a.title + ')' if a.title else '') if a.contact else 'No named contact confirmed yet.'}

{notes}

Rules for contacts: use names and titles from public pages only, confirm the person still works there on LinkedIn, and use an email address only if it is published by the company or the person. Do not guess or pattern-match addresses. If no email is public, send the LinkedIn note and ask to connect.

## Email

{email.format(**fields)}
## LinkedIn connection note (under 300 characters)

{t['linkedin'].format(**fields)}

## Follow-up (send after 7 days without a reply)

{t['followup'].format(**fields)}
## Honesty check

Every claim above comes from `.claude/memory/signature-stories.md` and `experience.md`. Do not add numbers, tools or years that are not there. Availability is stated as time zone and weekday calls only; add a start date only if you decide one.
"""
    out = ROOT / a.folder / "outreach.md" if a.folder else ROOT / "outreach_draft.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(body, encoding="utf-8")
    print("wrote", out.relative_to(ROOT))
    if a.tracker_id:
        data = tracker.load()
        tracker.upsert(data, {"id": a.tracker_id, "outreach": "drafted", "outreach_contacts": a.contact + (f" ({a.title})" if a.title else "")})
        tracker.save(data)
        print("tracker: outreach drafted for", a.tracker_id)


if __name__ == "__main__":
    main()
