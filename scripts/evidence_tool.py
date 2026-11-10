"""Create and update the candidate's private evidence base (data/evidence/evidence.json and skills.json).

Used by the onboarding interview so facts are stored the moment the candidate states them, with who said it,
how sure we are, and whether it may be published. Nothing here invents a fact: it only writes what it is given.

Usage:
  python scripts/evidence_tool.py init
  python scripts/evidence_tool.py add-record --json '{"employer": "...", "role": "...", "claim": "...", "actions": ["..."]}'
  python scripts/evidence_tool.py update-record EV-0003 --json '{"verification": "candidate_confirmed"}'
  python scripts/evidence_tool.py add-skill --json '{"name": "Excel", "proficiency": 4, "evidence_ids": ["EV-0001"]}'
  python scripts/evidence_tool.py list
  python scripts/evidence_tool.py validate

Defaults when a field is not given: verification candidate_reported, confidence medium, disclosure unknown (treated as
"do not publish numbers" until the candidate says it is fine), ownership unknown, source = the onboarding interview.
Verification levels: candidate_reported (said once), candidate_confirmed (said and re-confirmed), document_verified
(a document shows it), unverified, contradicted. A skill rating of 4 or 5 needs a named concrete thing in evidence.
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from jobintel.evidence import EvidenceBase, EvidenceError, load_schema  # noqa: E402

EVIDENCE = ROOT / "data" / "evidence" / "evidence.json"
SKILLS = ROOT / "data" / "evidence" / "skills.json"
NOTE = "Private file, git-ignored. Written by scripts/evidence_tool.py during onboarding. Edit through the tool or carefully by hand."


def _read(path, empty):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else empty


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def cmd_init(_):
    if not EVIDENCE.exists():
        _write(EVIDENCE, {"_note": NOTE, "records": []})
    if not SKILLS.exists():
        _write(SKILLS, {"_note": NOTE, "skills": [], "not_claimed": []})
    print("evidence files ready")


def _validate():
    base = EvidenceBase.load(EVIDENCE, SKILLS)
    return base


def cmd_add_record(a):
    cmd_init(a)
    data = _read(EVIDENCE, {"records": []})
    rec = json.loads(a.json)
    n = 1 + max([int(r["id"].split("-")[1]) for r in data["records"]] or [0])
    rec.setdefault("id", f"EV-{n:04d}")
    rec.setdefault("employer", "")
    rec.setdefault("role", "")
    rec.setdefault("ownership", "unknown")
    rec.setdefault("scope", {})
    rec.setdefault("verification", "candidate_reported")
    rec.setdefault("confidence", "medium")
    rec.setdefault("disclosure", "unknown")
    rec.setdefault("sources", [{"type": "candidate_interview", "reference": "onboarding interview", "date": date.today().isoformat()}])
    data["records"].append(rec)
    _write(EVIDENCE, data)
    try:
        _validate()
    except EvidenceError as e:
        data["records"].pop()
        _write(EVIDENCE, data)
        sys.exit(f"not saved, record invalid: {e}")
    print("added", rec["id"])


def cmd_update_record(a):
    data = _read(EVIDENCE, {"records": []})
    hit = next((r for r in data["records"] if r["id"] == a.id), None)
    if not hit:
        sys.exit(f"no record {a.id}")
    backup = json.loads(json.dumps(hit))
    changes = json.loads(a.json)
    for k, v in changes.items():
        if isinstance(v, dict) and isinstance(hit.get(k), dict):
            hit[k].update(v)
        else:
            hit[k] = v
    hit["last_confirmed"] = date.today().isoformat()
    _write(EVIDENCE, data)
    try:
        _validate()
    except EvidenceError as e:
        hit.clear()
        hit.update(backup)
        _write(EVIDENCE, data)
        sys.exit(f"not saved, record invalid: {e}")
    print("updated", a.id)


def cmd_add_skill(a):
    cmd_init(a)
    data = _read(SKILLS, {"skills": [], "not_claimed": []})
    s = json.loads(a.json)
    s.setdefault("kind", "direct")
    s.setdefault("confidence", "medium")
    s.setdefault("evidence_ids", [])
    s.setdefault("aliases", [])
    s.setdefault("gaps", [])
    if s.get("proficiency", 0) >= 4 and not s["evidence_ids"]:
        sys.exit("a rating of 4 or 5 needs at least one evidence record naming a concrete use. Add the record first.")
    data["skills"] = [x for x in data["skills"] if x["name"].lower() != s["name"].lower()] + [s]
    _write(SKILLS, data)
    try:
        _validate()
    except EvidenceError as e:
        sys.exit(f"not saved, skill invalid: {e}")
    print("saved skill", s["name"])


def cmd_list(_):
    data = _read(EVIDENCE, {"records": []})
    for r in data["records"]:
        print(f"{r['id']} [{r['verification']}/{r['disclosure']}] {r['employer']} | {r['role']} | {r['claim'][:110]}")
    sk = _read(SKILLS, {"skills": []})["skills"]
    print(f"{len(data['records'])} records, {len(sk)} skills")


def cmd_validate(_):
    base = _validate()
    print(f"valid: {len(base.records)} records, {len(base.skills)} skills, {len(base.conflicts())} open conflicts")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init").set_defaults(fn=cmd_init)
    sub.add_parser("list").set_defaults(fn=cmd_list)
    sub.add_parser("validate").set_defaults(fn=cmd_validate)
    s = sub.add_parser("add-record")
    s.add_argument("--json", required=True)
    s.set_defaults(fn=cmd_add_record)
    s = sub.add_parser("update-record")
    s.add_argument("id")
    s.add_argument("--json", required=True)
    s.set_defaults(fn=cmd_update_record)
    s = sub.add_parser("add-skill")
    s.add_argument("--json", required=True)
    s.set_defaults(fn=cmd_add_skill)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
