"""Resumable pipeline: ingest (+eligibility) -> score -> shortlist -> draft -> STOP at human approval.

Plain Python on purpose (decision D-3). Every step is idempotent, logged in pipeline_runs, and skipped on resume
when already done for the same run id. Nothing here submits or sends anything.
"""
from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

from . import eligibility
from .connectors import CONNECTORS
from .contacts import contacts_for_job
from .evidence import EvidenceBase
from .fit import analyse
from .models import Company
from .store import Store, now_iso

STEPS = ["ingest", "score", "shortlist", "draft"]
ROOT = Path(__file__).resolve().parents[2]


def _log(store: Store, run_id: str, step: str, status: str, detail: dict | None = None) -> None:
    store.db.execute(
        """INSERT INTO pipeline_runs(run_id,step,status,started_at,finished_at,detail) VALUES (?,?,?,?,?,?)
           ON CONFLICT(run_id,step) DO UPDATE SET status=excluded.status, finished_at=excluded.finished_at, detail=excluded.detail""",
        (run_id, step, status, now_iso(), now_iso() if status != "running" else None, json.dumps(detail or {}, ensure_ascii=False)))
    store.db.commit()


def step_done(store: Store, run_id: str, step: str) -> bool:
    r = store.db.execute("SELECT status FROM pipeline_runs WHERE run_id=? AND step=?", (run_id, step)).fetchone()
    return bool(r and r["status"] == "done")


def ingest_company(store: Store, connector, company: Company, candidate_country: str = "BR") -> dict:
    """Fetch one board, classify eligibility on every posting, persist. Failures are returned, not raised."""
    result = connector.fetch_jobs(company)
    for j in result.jobs:
        eligibility.apply(j, candidate_country)
    counts = store.ingest(result)
    return {"provider": company.provider, "slug": company.slug, "status": result.status, "error": result.error, **counts}


def score_jobs(store: Store, base: EvidenceBase, profile: dict, run_id: str, include_unverified: bool = True,
               origin: str = "live") -> int:
    allowed = ("yes", "unknown") if include_unverified else ("yes",)
    rows = store.db.execute(
        f"SELECT * FROM job_postings WHERE status='OPEN' AND eligible_for_candidate IN ({','.join('?' * len(allowed))}) "
        "AND (? = 'any' OR data_origin = ?)", (*allowed, origin, origin)).fetchall()
    n = 0
    for r in rows:
        cons = contacts_for_job(store, r["job_id"])
        hm = any(c["relation_to_role"] == "confirmed" and re.search(r"manager|director|head|lead", c["title"], re.I) for c in cons)
        f = analyse(r, base, profile, contacts=len(cons), hiring_manager_contact=hm)
        store.db.execute(
            """INSERT INTO job_scores(job_id,scored_at,fit_score,fit_band,coverage,desirability,contactability,hiring_signal,
               priority,confidence,decision,detail_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (r["job_id"], now_iso(), f.fit_score if f.fit_score is not None else f.fit_provisional, f.fit_band, f.coverage,
             f.desirability, f.contactability, f.hiring_signal, f.priority, f.confidence, f.decision,
             json.dumps({"run_id": run_id, "gate": f.gate_decision, "reasons": f.hard_gate_reasons, "categories": f.categories,
                         "matrix": f.matrix, "gaps": f.gaps, "unknowns": f.unknowns, "open_questions": f.open_questions,
                         "fit_is_provisional": f.fit_score is None}, ensure_ascii=False)))
        n += 1
    store.db.commit()
    return n


def shortlist(store: Store, limit: int = 10, origin: str = "live") -> list:
    """Latest score per job, PASS gate and decision PRIORITY or REVIEW, best priority first. At most `limit`."""
    return store.db.execute(
        """SELECT s.*, p.title, p.company_name, p.apply_url, p.remote_class, p.eligibility_evidence, p.job_id jid
           FROM job_scores s JOIN job_postings p ON p.job_id=s.job_id
           WHERE s.id IN (SELECT MAX(id) FROM job_scores GROUP BY job_id)
             AND s.decision IN ('PRIORITY','REVIEW') AND s.priority IS NOT NULL AND p.status='OPEN'
             AND (? = 'any' OR p.data_origin = ?)
           ORDER BY s.priority DESC LIMIT ?""", (origin, origin, limit)).fetchall()


def safe_name(job_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "__", job_id)


def draft_package_skeleton(store: Store, base: EvidenceBase, row, out_dir: Path) -> Path:
    """Contract C skeleton. The résumé and letter are NOT generated here: drafting stays with the existing resume-drafter
    flow (one page, no years figure). Everything is marked DRAFT_NOT_SENT."""
    job = store.job(row["job_id"])
    detail = json.loads(row["detail_json"])
    d = out_dir / safe_name(row["job_id"])
    d.mkdir(parents=True, exist_ok=True)
    cons = contacts_for_job(store, row["job_id"])
    lines = [f"# {job['company_name']}: {job['title']} ({job['job_id']})", "",
             "STATUS: DRAFT_NOT_SENT. Nothing in this folder has been submitted or sent.", "",
             "## 1. Job snapshot and eligibility",
             f"- Apply URL: {job['apply_url'] or 'unknown'}", f"- First seen: {job['first_seen_at']}; last checked: {job['last_seen_at']}",
             f"- Remote class: {job['remote_class']} ({job['eligible_for_candidate']})", f"- Evidence: {job['eligibility_evidence']}",
             f"- Time zone limits: {job['time_zone_limits'] or 'none stated'}",
             f"- Pay: {job['salary_min']}-{job['salary_max']} {job['currency']} per {job['salary_period']}" if job["salary_min"] else "- Pay: not stated",
             f"- Fit: {row['fit_score']} ({row['fit_band']}; provisional={detail['fit_is_provisional']}), coverage {row['coverage']}, "
             f"priority {row['priority']}, confidence {row['confidence']}, decision {row['decision']}. These are heuristics, not interview probabilities.",
             "", "## 2. Requirement-to-evidence map", "| requirement | must | evidence | rating | gap |", "|---|---|---|---|---|"]
    for m in detail["matrix"]:
        lines.append(f"| {m['requirement'][:90].replace('|', '/')} | {'yes' if m['must'] else 'no'} | {', '.join(m['evidence_ids']) or '-'} | "
                     f"{'unknown' if m['rating'] is None else m['rating']} | {m['gap'][:90].replace('|', '/')} |")
    lines += ["", "### Unresolved conflicts in the cited evidence (resolve in the interview before publishing)"]
    cited = {e for m in detail["matrix"] for e in m["evidence_ids"]}
    for ev in sorted(cited):
        for c in base.records.get(ev, {}).get("conflicts", []):
            lines.append(f"- {ev}: {c}")
    lines += ["", "## 3. Tailored résumé: DRAFT (not generated here)",
              "Use the existing resume-drafter flow (`resume_spec.json`, one page, no years figure). Every bullet must cite evidence ids above.",
              "", "## 4. Cover letter: DRAFT (not generated here)", "", "## 5. Screening questions and truthful answers",
              "Answer only from verified evidence; ask the candidate for anything unrecorded.", "", "## 6. Verified contact intelligence"]
    if cons:
        for c in cons:
            lines.append(f"- {c['name']}, {c['title']} ({c['relation_to_role']}); source {c['source_url']}; checked {c['checked_at']}; "
                         f"email: {c['business_email'] or 'not found'} ({c['email_verification']})")
    else:
        lines.append("- no_verified_contact")
    lines += ["", "## 7. Outreach drafts: NOT SENT", "", "## 8. Interview preparation", "",
              "## 9. Candidate approval checklist", "- [ ] Facts reviewed by the candidate", "- [ ] Conflicts above resolved",
              "- [ ] Approved for submission (status: DRAFT_NOT_SENT)"]
    path = d / "application-package.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def run_pipeline(store: Store, base: EvidenceBase, profile: dict, companies: list[Company], http=None,
                 run_id: str | None = None, steps: list[str] | None = None, resume: bool = True,
                 shortlist_limit: int = 10, out_dir: Path | None = None, connectors: dict | None = None,
                 origin: str = "live") -> dict:
    run_id = run_id or uuid.uuid4().hex[:8]
    steps = steps or STEPS
    out_dir = out_dir or ROOT / "output" / "applications"
    summary: dict = {"run_id": run_id, "steps": {}}
    conns = connectors or {name: cls(http=http) for name, cls in CONNECTORS.items()}
    for step in steps:
        if resume and step_done(store, run_id, step):
            summary["steps"][step] = "skipped (already done)"
            continue
        _log(store, run_id, step, "running")
        try:
            if step == "ingest":
                results = [ingest_company(store, conns[c.provider], c, profile["candidate_country"]) for c in companies]
                detail = {"boards": len(results), "ok": sum(r["status"] == "ok" for r in results),
                          "failed": [r for r in results if r["status"] in ("error", "access_denied")],
                          "not_found": sum(r["status"] == "not_found" for r in results)}
            elif step == "score":
                detail = {"scored": score_jobs(store, base, profile, run_id, origin=origin)}
            elif step == "shortlist":
                detail = {"shortlisted": [r["job_id"] for r in shortlist(store, shortlist_limit, origin)]}
            elif step == "draft":
                paths = [str(draft_package_skeleton(store, base, r, out_dir))
                         for r in shortlist(store, min(shortlist_limit, 3), origin)]
                detail = {"drafted": paths, "awaiting_human_approval": True}
            else:
                raise ValueError(f"unknown step {step}")
            _log(store, run_id, step, "done", detail)
            summary["steps"][step] = detail
        except Exception as e:  # a failed step is recorded and stops the run; later steps do not run on bad state
            _log(store, run_id, step, "failed", {"error": f"{type(e).__name__}: {e}"})
            summary["steps"][step] = {"failed": f"{type(e).__name__}: {e}"}
            summary["stopped_at"] = step
            break
    return summary
