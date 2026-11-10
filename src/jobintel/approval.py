"""Application and outreach packages with a human-approval gate.

Nothing in this module sends or submits anything. It only records state:
  DRAFT_NOT_SENT -> REVIEW_APPROVED -> SUBMITTED
  BLOCKED_CLAIMS (claims failed the evidence check; cannot be approved)

Gates (decision D-9):
  * claims are checked against the evidence base when the package is created;
  * approval is bound to a hash of the exact content and claims; editing the file voids the approval;
  * SUBMITTED needs a stored approval for the current hash AND a confirmation reference typed by the person
    (a confirmation e-mail id, an application id, a sent-message note). No reference, no completion;
  * the same job cannot be SUBMITTED twice as an application.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .evidence import EvidenceBase, check_claim
from .store import Store, now_iso

DRAFT, APPROVED, SUBMITTED, BLOCKED = "DRAFT_NOT_SENT", "REVIEW_APPROVED", "SUBMITTED", "BLOCKED_CLAIMS"


class ApprovalError(Exception):
    pass


def _hash(content_path: str, claims: list[dict]) -> str:
    body = Path(content_path).read_bytes() if content_path and Path(content_path).exists() else b""
    h = hashlib.sha256(body)
    h.update(json.dumps(claims, sort_keys=True, ensure_ascii=False).encode("utf-8"))
    return h.hexdigest()[:16]


def _event(store: Store, package_id: int, event: str, actor: str, detail: str = "") -> None:
    store.db.execute("INSERT INTO application_events(package_id,at,event,actor,detail) VALUES (?,?,?,?,?)",
                     (package_id, now_iso(), event, actor, detail))
    store.db.commit()


def create_package(store: Store, base: EvidenceBase, job_id: str, kind: str, content_path: str,
                   claims: list[dict]) -> dict:
    """claims: [{"text": "...", "evidence_ids": ["EV-0001"]}]. Returns {"id", "status", "problems", "warnings"}."""
    if kind not in ("application", "outreach"):
        raise ApprovalError("kind must be 'application' or 'outreach'")
    if store.job(job_id) is None:
        raise ApprovalError(f"unknown job {job_id}")
    problems, warnings, ev_ids = [], [], set()
    for c in claims:
        r = check_claim(base, c["text"], c.get("evidence_ids", []))
        ev_ids.update(c.get("evidence_ids", []))
        problems += [f"{c['text'][:60]}...: {p}" for p in r.problems]
        warnings += [f"{c['text'][:60]}...: {w}" for w in r.warnings]
    status = BLOCKED if problems else DRAFT
    cur = store.db.execute(
        """INSERT INTO application_packages(job_id,kind,status,version_hash,content_path,evidence_ids,created_at)
           VALUES (?,?,?,?,?,?,?)""",
        (job_id, kind, status, _hash(content_path, claims), content_path, json.dumps(sorted(ev_ids)), now_iso()))
    pid = cur.lastrowid
    store.db.commit()
    _event(store, pid, "created", "system", json.dumps({"problems": problems, "warnings": warnings}, ensure_ascii=False))
    return {"id": pid, "status": status, "problems": problems, "warnings": warnings}


def package(store: Store, package_id: int):
    row = store.db.execute("SELECT * FROM application_packages WHERE id=?", (package_id,)).fetchone()
    if row is None:
        raise ApprovalError(f"no package {package_id}")
    return row


def approve(store: Store, package_id: int, approver: str, claims: list[dict],
            acknowledge_unconfirmed: bool = False) -> dict:
    """A human approves the exact current content. `claims` must be the same list the package was created with."""
    p = package(store, package_id)
    if not approver.strip():
        raise ApprovalError("approver name is required")
    if p["status"] == BLOCKED:
        raise ApprovalError("package is BLOCKED_CLAIMS: fix the unsupported claims and create a new version")
    if p["status"] != DRAFT:
        raise ApprovalError(f"package is {p['status']}, only {DRAFT} can be approved")
    current = _hash(p["content_path"], claims)
    if current != p["version_hash"]:
        raise ApprovalError("content or claims changed since the package was created; create a new version and review it")
    ev = json.loads(p["evidence_ids"] or "[]")
    # candidate_reported evidence needs a deliberate acknowledgement (the interview should confirm it)
    from_events = store.db.execute("SELECT detail FROM application_events WHERE package_id=? AND event='created'", (package_id,)).fetchone()
    warnings = json.loads(from_events["detail"]).get("warnings", []) if from_events else []
    if warnings and not acknowledge_unconfirmed:
        raise ApprovalError("package contains unconfirmed (candidate_reported) claims; review them and approve with "
                            "acknowledge_unconfirmed=True: " + "; ".join(warnings[:3]))
    store.db.execute("UPDATE application_packages SET status=?, approved_by=?, approved_at=?, approved_hash=? WHERE id=?",
                     (APPROVED, approver, now_iso(), current, package_id))
    store.db.commit()
    _event(store, package_id, "approved", approver, f"hash={current}; evidence={ev}; ack_unconfirmed={acknowledge_unconfirmed}")
    return {"id": package_id, "status": APPROVED, "hash": current}


def mark_submitted(store: Store, package_id: int, actor: str, confirmation_ref: str, claims: list[dict]) -> dict:
    """Record that the PERSON submitted/sent it, with a reference. This never performs the submission."""
    p = package(store, package_id)
    if p["status"] != APPROVED:
        raise ApprovalError(f"package is {p['status']}: it must be {APPROVED} before it can be marked submitted")
    if not (confirmation_ref or "").strip() or len(confirmation_ref.strip()) < 3:
        raise ApprovalError("a confirmation reference is required (confirmation e-mail, application id or sent-message note)")
    if _hash(p["content_path"], claims) != p["approved_hash"]:
        raise ApprovalError("content changed after approval; the approval no longer applies")
    if p["kind"] == "application":
        dup = store.db.execute("SELECT id FROM application_packages WHERE job_id=? AND kind='application' AND status=? AND id<>?",
                               (p["job_id"], SUBMITTED, package_id)).fetchone()
        if dup:
            raise ApprovalError(f"job already has a submitted application (package {dup['id']}); no duplicate submissions")
    store.db.execute("UPDATE application_packages SET status=?, submitted_at=?, confirmation_ref=? WHERE id=?",
                     (SUBMITTED, now_iso(), confirmation_ref.strip(), package_id))
    store.db.commit()
    _event(store, package_id, "submitted_recorded", actor, f"ref={confirmation_ref.strip()}")
    return {"id": package_id, "status": SUBMITTED}
