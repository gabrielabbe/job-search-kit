"""Application tracker for the job search: one JSON file, a small CLI, and the insights the dashboard shows.

Usage:
  python scripts/tracker.py list [--status applied]
  python scripts/tracker.py add --company X --role Y [--source ...] [--url ...] [--folder jobs/...] [--status drafted] ...
  python scripts/tracker.py set <id> [--status applied] [--applied 2026-10-29] [--reply recruiter] [--note "..."] ...
  python scripts/tracker.py insights
  python scripts/tracker.py seed          # one-off import of the 2026-10-28/29 applications

Data lives in data/tracker.json (human-readable, safe to edit). Nothing here submits anything.
Statuses: drafted, applied, interview, offer, rejected, closed (posting dead or not eligible), withdrawn.
Reply values: none (waiting), auto, recruiter, interview, rejection, offer.
"""
import argparse
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parent.parent
STORE = ROOT / "data" / "tracker.json"
STATUSES = ["drafted", "applied", "interview", "offer", "rejected", "closed", "withdrawn"]
REPLIES = ["none", "auto", "recruiter", "interview", "rejection", "offer"]
OUTREACH = ["none", "drafted", "sent", "replied"]
FOLLOW_UP_DAYS = 7


def load():
    if STORE.exists():
        return json.loads(STORE.read_text(encoding="utf-8"))
    return {"applications": [], "lessons": []}


def save(data):
    STORE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STORE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, STORE)


def days_between(a, b):
    try:
        return (datetime.fromisoformat(b) - datetime.fromisoformat(a)).days
    except (TypeError, ValueError):
        return None


def upsert(data, rec):
    """Insert or update an application by id. Unknown keys are kept."""
    apps = data["applications"]
    for a in apps:
        if a["id"] == rec["id"]:
            a.update({k: v for k, v in rec.items() if v is not None})
            return a
    base = {"status": "drafted", "reply": "none", "source": "", "url": "", "folder": "", "found": date.today().isoformat(),
            "applied": "", "reply_date": "", "pay": "", "model": "", "language": "English", "fit": "", "notes": "", "contact": "", "outreach": "none", "outreach_contacts": ""}
    base.update({k: v for k, v in rec.items() if v is not None})
    apps.append(base)
    return base


def follow_ups(data, today=None):
    today = today or date.today().isoformat()
    out = []
    for a in data["applications"]:
        if a["status"] == "applied" and a["reply"] == "none" and a.get("applied"):
            age = days_between(a["applied"], today)
            if age is not None and age >= FOLLOW_UP_DAYS:
                out.append({"id": a["id"], "company": a["company"], "role": a["role"], "days": age})
    return out


FAMILIES = ["it_management", "ai_operations", "martech_gtm", "tech_management", "data_reporting", "other"]


def family_of(a):
    """Stored family, else a plain keyword guess from the role title (kept simple on purpose)."""
    if a.get("family"):
        return a["family"]
    r = (a.get("role") or "").lower()
    for fam, words in (("ai_operations", ("ai operations", "ai solutions", "ai adoption", "automation")),
                       ("it_management", ("it manager", "head of it", "corporate it", "it operations", "gerente de ti", "it engineer", "it lead")),
                       ("tech_management", ("program manager", "project manager", "engineering manager", "technical program")),
                       ("martech_gtm", ("gtm", "martech", "revops", "marketing", "revenue")),
                       ("data_reporting", ("analytics", "data", "reporting", "bi "))):
        if any(w in r for w in words):
            return fam
    return "other"


def source_class_of(a):
    """A official ATS or board API, D manual or restricted (LinkedIn, Indeed, pasted by hand), C anything else."""
    if a.get("source_class"):
        return a["source_class"]
    src = (a.get("source") or "").lower()
    if any(w in src for w in ("company feed", "greenhouse", "lever", "ashby", "himalayas", "remotive", "remoteok", "jobicy", "get on board", "getonbrd")):
        return "A"
    if any(w in src for w in ("indeed", "linkedin", "brought by", "pasted", "found by", "brought by candidate")):
        return "D"
    return "C"


def score_band_of(a):
    try:
        sc = float(a.get("score"))
    except (TypeError, ValueError):
        return "unscored"
    return "4.0+" if sc >= 4.0 else "3.5-3.9" if sc >= 3.5 else "below 3.5"


def insights(data, today=None):
    """Numbers and plain-language hints used to tune the search. Small samples get a caveat, never a conclusion."""
    today = today or date.today().isoformat()
    apps = data["applications"]
    applied = [a for a in apps if a.get("applied")]
    replied = [a for a in applied if a["reply"] not in ("none",)]
    real = [a for a in applied if a["reply"] in ("recruiter", "interview", "offer")]
    out = {
        "total": len(apps),
        "by_status": {s: sum(1 for a in apps if a["status"] == s) for s in STATUSES},
        "applied": len(applied),
        "replies": len(replied),
        "real_replies": len(real),
        "reply_rate": round(100 * len(real) / len(applied)) if applied else None,
        "interviews": sum(1 for a in apps if a["status"] in ("interview", "offer") or a["reply"] in ("interview", "offer")),
        "median_days_to_reply": None,
        "follow_ups_due": follow_ups(data, today),
        "by_source": {},
        "by_model": {},
        "hints": [],
    }
    waits = [days_between(a["applied"], a["reply_date"]) for a in real if a.get("reply_date")]
    waits = [w for w in waits if w is not None]
    if waits:
        out["median_days_to_reply"] = median(waits)
    for key, field in (("by_source", "source"), ("by_model", "model")):
        groups = {}
        for a in applied:
            groups.setdefault(a.get(field) or "unknown", []).append(a)
        out[key] = {k: {"applied": len(v), "replies": sum(1 for a in v if a["reply"] in ("recruiter", "interview", "offer"))}
                    for k, v in groups.items()}
    for key, fn in (("by_family", family_of), ("by_source_class", source_class_of), ("by_score_band", score_band_of)):
        groups = {}
        for a in applied:
            groups.setdefault(fn(a), []).append(a)
        out[key] = {k: {"applied": len(v), "replies": sum(1 for a in v if a["reply"] in ("recruiter", "interview", "offer"))}
                    for k, v in groups.items()}
    stages = {}
    for a in apps:
        if a.get("rejection_stage"):
            stages[a["rejection_stage"]] = stages.get(a["rejection_stage"], 0) + 1
    if stages:
        out["rejection_stages"] = stages
    sent = [a for a in applied if a.get("outreach") in ("sent", "replied")]
    quiet = [a for a in applied if a.get("outreach", "none") in ("none", "drafted")]
    out["outreach"] = {
        "sent": {"applied": len(sent), "replies": sum(1 for a in sent if a["reply"] in ("recruiter", "interview", "offer"))},
        "not_sent": {"applied": len(quiet), "replies": sum(1 for a in quiet if a["reply"] in ("recruiter", "interview", "offer"))},
        "drafted_unsent": sum(1 for a in applied if a.get("outreach") == "drafted"),
    }
    if out["outreach"]["drafted_unsent"]:
        out["hints"].append(f"{out['outreach']['drafted_unsent']} outreach message(s) are drafted but not sent. A direct note to the recruiter or hiring manager is the cheapest way to lift the reply rate.")
    n = len(applied)
    if n < 10:
        out["hints"].append(f"Only {n} applications so far, so rates are noise. Keep applying and logging replies; patterns start to mean something around 10 to 15.")
    elif out["reply_rate"] is not None and out["reply_rate"] < 10:
        out["hints"].append("Reply rate is under 10%. Check posting age at apply (apply within 3 days), warm contacts (message a recruiter), and whether the roles match the record closely.")
    if out["follow_ups_due"]:
        out["hints"].append(f"{len(out['follow_ups_due'])} application(s) have had no reply for {FOLLOW_UP_DAYS}+ days: send one short follow-up each.")
    best = [(k, v) for k, v in out["by_source"].items() if v["applied"] >= 3 and v["replies"] > 0]
    if best:
        k, v = max(best, key=lambda kv: kv[1]["replies"] / kv[1]["applied"])
        out["hints"].append(f"Best source so far: {k} ({v['replies']} replies from {v['applied']} applications).")
    closed = [a for a in apps if a["status"] == "closed"]
    if closed:
        out["hints"].append(f"{len(closed)} role(s) closed or ineligible before applying: check eligibility (country, hours) earlier in the funnel.")
    return out


def cmd_list(args):
    for a in load()["applications"]:
        if args.status and a["status"] != args.status:
            continue
        print(f"{a['id']:<62} {a['status']:<10} reply={a['reply']:<9} applied={a.get('applied') or '-'}")


def fields_from(args):
    keys = ["company", "role", "source", "url", "folder", "status", "applied", "reply", "reply_date", "pay", "model",
            "language", "fit", "notes", "contact", "outreach", "outreach_contacts", "family", "score", "rejection_stage",
            "source_class"]
    return {k: getattr(args, k, None) for k in keys}


def cmd_add(args):
    data = load()
    rec = fields_from(args)
    rec["id"] = args.id or (date.today().isoformat() + "_" + "".join(c if c.isalnum() else "-" for c in f"{args.company}_{args.role}".lower())[:60])
    upsert(data, rec)
    save(data)
    print("saved", rec["id"])


def cmd_set(args):
    data = load()
    rec = fields_from(args)
    rec["id"] = args.id
    if not any(a["id"] == args.id for a in data["applications"]):
        sys.exit("no such id: " + args.id)
    if args.note:
        cur = next(a for a in data["applications"] if a["id"] == args.id)
        rec["notes"] = (cur.get("notes", "") + "\n" if cur.get("notes") else "") + f"{date.today().isoformat()}: {args.note}"
    if args.status == "applied" and not args.applied:
        rec["applied"] = date.today().isoformat()
    upsert(data, rec)
    save(data)
    print("updated", args.id)


def cmd_insights(_):
    print(json.dumps(insights(load()), indent=1, ensure_ascii=False))


DEFAULT_LESSONS = [
    {"date": "start", "text": "Remote on a job board with a salary band in one currency and local benefits usually means a role for that country only. Read the posting for the countries it hires in."},
    {"date": "start", "text": "Use a job board's server-side country filter instead of reading page one of an all-jobs list."},
]


def cmd_seed(_):
    """Start the tracker with a few general lessons. No applications are created."""
    data = load()
    if not data["lessons"]:
        data["lessons"] = list(DEFAULT_LESSONS)
    save(data)
    print("tracker ready:", len(data["applications"]), "applications,", len(data["lessons"]), "lessons")


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("insights").set_defaults(fn=cmd_insights)
    sub.add_parser("seed").set_defaults(fn=cmd_seed)
    ls = sub.add_parser("list")
    ls.add_argument("--status")
    ls.set_defaults(fn=cmd_list)
    for name, fn in (("add", cmd_add), ("set", cmd_set)):
        sp = sub.add_parser(name)
        if name == "set":
            sp.add_argument("id")
        else:
            sp.add_argument("--id")
            sp.add_argument("--company", required=True)
            sp.add_argument("--role", required=True)
        for k in ["source", "url", "folder", "applied", "reply_date", "pay", "model", "language", "fit", "notes", "contact"]:
            sp.add_argument("--" + k.replace("_", "-"), dest=k)
        sp.add_argument("--status", choices=STATUSES)
        sp.add_argument("--reply", choices=REPLIES)
        sp.add_argument("--outreach", choices=OUTREACH)
        sp.add_argument("--outreach-contacts", dest="outreach_contacts")
        sp.add_argument("--family", choices=FAMILIES)
        sp.add_argument("--score", type=float, help="global score 1-5 from the job-scoring card")
        sp.add_argument("--rejection-stage", dest="rejection_stage", help="where it ended: screening, recruiter, hiring-manager, technical, final")
        sp.add_argument("--source-class", dest="source_class", choices=["A", "B", "C", "D"],
                        help="A official ATS or board API, B API needing credentials, C public pages, D manual or restricted")
        if name == "set":
            sp.add_argument("--note")
        sp.set_defaults(fn=fn)
    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
