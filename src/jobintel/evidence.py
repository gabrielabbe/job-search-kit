"""Evidence base: schema validation, lookups and the claim checker.

Implements career-intelligence-upgrade/03-EVIDENCE-AND-SKILLS-MODEL.md. Nothing here invents facts: records
come from the candidate (interview or the project's memory files) and carry a verification state.

Outward-claim readiness:
  document_verified, candidate_confirmed -> ok
  candidate_reported                      -> needs_confirmation (usable in drafts, flagged, resolved by interview)
  unverified, contradicted                -> blocked
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import jsonschema

VERIFICATION_STATES = ("document_verified", "candidate_confirmed", "candidate_reported", "unverified", "contradicted")
OK_STATES = ("document_verified", "candidate_confirmed")
WARN_STATES = ("candidate_reported",)

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "data" / "evidence" / "schema.json"


class EvidenceError(Exception):
    pass


def load_schema(path: Path | None = None) -> dict:
    return json.loads((path or SCHEMA_PATH).read_text(encoding="utf-8"))


@dataclass
class EvidenceBase:
    records: dict[str, dict] = field(default_factory=dict)
    skills: dict[str, dict] = field(default_factory=dict)
    not_claimed: list[dict] = field(default_factory=list)

    @classmethod
    def load(cls, evidence_path: Path, skills_path: Path | None = None, schema: dict | None = None) -> "EvidenceBase":
        schema = schema or load_schema()
        data = json.loads(Path(evidence_path).read_text(encoding="utf-8"))
        base = cls()
        validator = jsonschema.Draft202012Validator(schema["definitions"]["evidence"])
        for rec in data["records"]:
            errs = sorted(validator.iter_errors(rec), key=lambda e: list(e.path))
            if errs:
                raise EvidenceError(f"{rec.get('id', '?')}: {errs[0].message} at {list(errs[0].path)}")
            if rec["id"] in base.records:
                raise EvidenceError(f"duplicate evidence id {rec['id']}")
            base.records[rec["id"]] = rec
        if skills_path and Path(skills_path).exists():
            sdata = json.loads(Path(skills_path).read_text(encoding="utf-8"))
            sval = jsonschema.Draft202012Validator(schema["definitions"]["skill"])
            for s in sdata["skills"]:
                errs = sorted(sval.iter_errors(s), key=lambda e: list(e.path))
                if errs:
                    raise EvidenceError(f"skill {s.get('name', '?')}: {errs[0].message}")
                for ev in s.get("evidence_ids", []):
                    if ev not in base.records:
                        raise EvidenceError(f"skill {s['name']} cites unknown evidence {ev}")
                base.skills[s["name"].lower()] = s
            base.not_claimed = sdata.get("not_claimed", [])
        return base

    # -- queries ------------------------------------------------------------------
    def state(self, evidence_id: str) -> str:
        rec = self.records.get(evidence_id)
        return rec["verification"] if rec else "missing"

    def conflicts(self) -> list[tuple[str, str]]:
        return [(r["id"], c) for r in self.records.values() for c in r.get("conflicts", [])]

    def find_skill(self, text: str) -> dict | None:
        t = text.lower()
        for s in self.skills.values():
            names = [s["name"].lower()] + [a.lower() for a in s.get("aliases", [])]
            if any(re.search(rf"(?<![\w]){re.escape(n)}(?![\w])", t) for n in names):
                return s
        return None

    def find_gap(self, text: str) -> dict | None:
        t = text.lower()
        for g in self.not_claimed:
            names = [g["name"].lower()] + [a.lower() for a in g.get("aliases", [])]
            if any(re.search(rf"(?<![\w]){re.escape(n)}(?![\w])", t) for n in names):
                return g
        return None


@dataclass
class ClaimCheck:
    status: str  # ok | needs_confirmation | blocked
    problems: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


_NUM = re.compile(r"\$?\d[\d,\.]*\s*(?:%|k|K|m|M)?")
# scope phrases that must be backed by an explicit scope on the cited evidence
_DIRECT_REPORTS = re.compile(r"\b(\d+)\s+(?:direct\s+)?reports\b|\bmanag\w+\s+(?:a\s+)?(?:team|staff)\s+of\s+(\d+)", re.I)
_REPORTING = re.compile(r"\breport(?:s|ing)?\s+(?:directly\s+)?to\s+the\s+(CEO|COO|CFO|CTO|president)", re.I)


def check_claim(base: EvidenceBase, claim: str, evidence_ids: list[str]) -> ClaimCheck:
    """Audit one outward-facing statement against the evidence it cites."""
    res = ClaimCheck("ok")
    if not evidence_ids:
        return ClaimCheck("blocked", ["claim cites no evidence id"])
    recs = []
    for ev in evidence_ids:
        rec = base.records.get(ev)
        if rec is None:
            res.problems.append(f"unknown evidence id {ev}")
            continue
        recs.append(rec)
        if rec["verification"] in ("unverified", "contradicted"):
            res.problems.append(f"{ev} is {rec['verification']}")
        elif rec["verification"] in WARN_STATES:
            res.warnings.append(f"{ev} is candidate_reported: confirm before publishing")
        if rec.get("disclosure") == "restricted":
            res.problems.append(f"{ev} disclosure is restricted")
    haystack = json.dumps(recs, ensure_ascii=False).lower().replace(",", "")
    for m in _NUM.finditer(claim):
        raw = m.group(0).strip().lower().replace(",", "")
        digits = re.sub(r"[^\d\.]", "", raw)
        if digits and len(digits) >= 2 and digits not in haystack:
            res.problems.append(f"number '{m.group(0).strip()}' is not in the cited evidence")
    # direct reports: only when the evidence has a direct_reports scope with that number
    for m in _DIRECT_REPORTS.finditer(claim):
        n = int(m.group(1) or m.group(2))
        known = {r.get("scope", {}).get("direct_reports") for r in recs}
        if n not in known:
            res.problems.append(f"direct-report count {n} is not recorded as direct_reports in the cited evidence")
    gap = base.find_gap(claim)
    if gap:  # a documented gap or an unrecorded tool/skill must never be asserted as used
        res.problems.append(f"claim mentions '{gap['name']}', which is {gap['status'].replace('_', ' ')} ({gap['note']})")
    for m in _REPORTING.finditer(claim):
        who = m.group(1).upper()
        ok = any(who in (r.get("reporting_line") or "").upper() and r["verification"] in OK_STATES for r in recs)
        if not ok:
            res.problems.append(f"reporting line to the {who} is not candidate_confirmed or document_verified")
    if res.problems:
        res.status = "blocked"
    elif res.warnings:
        res.status = "needs_confirmation"
    return res
