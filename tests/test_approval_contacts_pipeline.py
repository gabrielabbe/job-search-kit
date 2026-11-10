import json

import pytest

from conftest import fake_http, fixture_json, make_job
from jobintel import approval, contacts, eligibility
from jobintel.approval import ApprovalError
from jobintel.models import Company, FetchResult
from jobintel.pipeline import run_pipeline, shortlist


def _job(store):
    j = eligibility.apply(make_job())
    store.ingest(FetchResult("greenhouse", "acme", "u", "ok", [j], authoritative=True))
    return j.job_id


CLAIMS_OK = [{"text": "Lead a team of 3", "evidence_ids": ["EV-0001"]}]
CLAIMS_UNCONFIRMED = [{"text": "Cut onboarding from 30-45 minutes to a few minutes", "evidence_ids": ["EV-0002"]}]


def _file(tmp_path, text="resume v1"):
    p = tmp_path / f"pkg_{abs(hash(text))}.md"
    p.write_text(text, encoding="utf-8")
    return str(p)


# ------------------------------------------------------------------ approval gate
def test_package_with_unsupported_claims_is_blocked_and_cannot_be_approved(store, evidence, tmp_path):
    jid = _job(store)
    bad = [{"text": "Manage 200 direct reports", "evidence_ids": ["EV-0001"]}]
    r = approval.create_package(store, evidence, jid, "application", _file(tmp_path), bad)
    assert r["status"] == approval.BLOCKED and r["problems"]
    with pytest.raises(ApprovalError, match="BLOCKED_CLAIMS"):
        approval.approve(store, r["id"], "Candidate", bad)


def test_cannot_mark_submitted_without_approval(store, evidence, tmp_path):
    jid = _job(store)
    r = approval.create_package(store, evidence, jid, "application", _file(tmp_path), CLAIMS_OK)
    assert r["status"] == approval.DRAFT
    with pytest.raises(ApprovalError, match="must be REVIEW_APPROVED"):
        approval.mark_submitted(store, r["id"], "Candidate", "CONF-123", CLAIMS_OK)


def test_full_happy_path_requires_reference_and_records_events(store, evidence, tmp_path):
    jid = _job(store)
    r = approval.create_package(store, evidence, jid, "application", _file(tmp_path), CLAIMS_OK)
    approval.approve(store, r["id"], "Candidate", CLAIMS_OK)
    with pytest.raises(ApprovalError, match="confirmation reference"):
        approval.mark_submitted(store, r["id"], "Candidate", "", CLAIMS_OK)
    assert approval.mark_submitted(store, r["id"], "Candidate", "email confirmation 2026-11-06", CLAIMS_OK)["status"] == approval.SUBMITTED
    events = [e["event"] for e in store.db.execute("SELECT event FROM application_events WHERE package_id=? ORDER BY id", (r["id"],))]
    assert events == ["created", "approved", "submitted_recorded"]


def test_editing_content_after_creation_or_approval_voids_the_gate(store, evidence, tmp_path):
    jid = _job(store)
    path = _file(tmp_path)
    r = approval.create_package(store, evidence, jid, "application", path, CLAIMS_OK)
    open(path, "w", encoding="utf-8").write("resume v2 with a new unreviewed claim")
    with pytest.raises(ApprovalError, match="changed since"):
        approval.approve(store, r["id"], "Candidate", CLAIMS_OK)
    # approve a fresh version, then edit after approval
    path2 = _file(tmp_path, "resume v3")
    r2 = approval.create_package(store, evidence, jid, "application", path2, CLAIMS_OK)
    approval.approve(store, r2["id"], "Candidate", CLAIMS_OK)
    open(path2, "w", encoding="utf-8").write("resume v3 edited after approval")
    with pytest.raises(ApprovalError, match="after approval"):
        approval.mark_submitted(store, r2["id"], "Candidate", "REF-1", CLAIMS_OK)


def test_unconfirmed_claims_need_explicit_acknowledgement(store, evidence, tmp_path):
    jid = _job(store)
    r = approval.create_package(store, evidence, jid, "application", _file(tmp_path), CLAIMS_UNCONFIRMED)
    assert r["status"] == approval.DRAFT and r["warnings"]
    with pytest.raises(ApprovalError, match="unconfirmed"):
        approval.approve(store, r["id"], "Candidate", CLAIMS_UNCONFIRMED)
    assert approval.approve(store, r["id"], "Candidate", CLAIMS_UNCONFIRMED, acknowledge_unconfirmed=True)["status"] == approval.APPROVED


def test_no_duplicate_submissions_for_the_same_job(store, evidence, tmp_path):
    jid = _job(store)
    ids = []
    for i in range(2):
        r = approval.create_package(store, evidence, jid, "application", _file(tmp_path, f"v{i}"), CLAIMS_OK)
        approval.approve(store, r["id"], "Candidate", CLAIMS_OK)
        ids.append(r["id"])
    approval.mark_submitted(store, ids[0], "Candidate", "REF-A", CLAIMS_OK)
    with pytest.raises(ApprovalError, match="no duplicate"):
        approval.mark_submitted(store, ids[1], "Candidate", "REF-B", CLAIMS_OK)


def test_approver_name_is_required(store, evidence, tmp_path):
    jid = _job(store)
    r = approval.create_package(store, evidence, jid, "application", _file(tmp_path), CLAIMS_OK)
    with pytest.raises(ApprovalError, match="approver"):
        approval.approve(store, r["id"], "  ", CLAIMS_OK)


# ------------------------------------------------------------------ contacts
def test_contact_needs_a_source(store):
    jid = _job(store)
    with pytest.raises(contacts.ContactRejected, match="source URL"):
        contacts.add_contact(store, jid, "Acme", "Ana Silva", "Recruiter", source_url="")


def test_guessed_and_personal_emails_are_never_stored(store):
    jid = _job(store)
    with pytest.raises(contacts.ContactRejected, match="never guess"):
        contacts.add_contact(store, jid, "Acme", "Ana Silva", "Recruiter", "https://acme.test/team",
                             business_email="ana.silva@acme.test", email_verification="not_verified")
    with pytest.raises(contacts.ContactRejected, match="free-mail"):
        contacts.add_contact(store, jid, "Acme", "Ana Silva", "Recruiter", "https://acme.test/team",
                             business_email="ana@gmail.com", email_verification="source_published")
    cid = contacts.add_contact(store, jid, "Acme", "Ana Silva", "Recruiter", "https://acme.test/team",
                               business_email="talent@acme.test", email_verification="source_published")
    assert cid and contacts.contacts_for_job(store, jid)[0]["business_email"] == "talent@acme.test"
    contacts.add_contact(store, jid, "Acme", "Bo Lee", "Head of IT", "https://acme.test/about")  # no email: 'not found' is fine
    assert [c["business_email"] for c in contacts.contacts_for_job(store, jid)][1] is None


def test_opted_out_contacts_are_not_returned(store):
    jid = _job(store)
    cid = contacts.add_contact(store, jid, "Acme", "Ana Silva", "Recruiter", "https://acme.test/team")
    contacts.opt_out(store, cid)
    assert contacts.contacts_for_job(store, jid) == []


# ------------------------------------------------------------------ pipeline end to end
def _companies():
    return [Company("FixtureCo", "fixtureco", "greenhouse"), Company("LeverCo", "leverco", "lever"),
            Company("AshbyCo", "ashbyco", "ashby"), Company("SRCo", "srco", "smartrecruiters")]


def _http():
    return fake_http({"greenhouse.io/v1/boards/fixtureco": fixture_json("greenhouse_board.json"),
                      "api.lever.co/v0/postings/leverco": fixture_json("lever_board.json"),
                      "ashbyhq.com/posting-api/job-board/ashbyco": fixture_json("ashby_board.json")})[0]


def test_end_to_end_ingest_eligibility_rank_draft_and_halt(store, evidence, profile, tmp_path):
    out = run_pipeline(store, evidence, profile, _companies(), http=_http(), run_id="t1", origin="fixture", out_dir=tmp_path)
    assert "stopped_at" not in out
    assert out["steps"]["ingest"]["ok"] == 3 and out["steps"]["ingest"]["not_found"] == 1  # SR board unknown
    sl = [r["job_id"] for r in shortlist(store, 10, "fixture")]
    # eligible and passing gates only: Brazil, worldwide, LATAM
    assert "lever:leverco:aaaa-1" in sl and "ashby:ashbyco:ash-1" in sl and "greenhouse:fixtureco:1001" in sl
    # the Brazil IT Manager role has a REQUIRED documented gap (AWS certification): it is shortlisted for REVIEW, never PRIORITY,
    # and the gap stays visible in the stored score detail
    row = store.db.execute("SELECT decision, detail_json FROM job_scores WHERE job_id='greenhouse:fixtureco:1001'").fetchone()
    assert row["decision"] == "REVIEW" and "REQUIRED" in row["detail_json"]
    # US-only, on-site, Canada-only, unverified 'Remote', unlisted: never shortlisted
    for bad in ("greenhouse:fixtureco:1002", "greenhouse:fixtureco:1003", "greenhouse:fixtureco:1004",
                "lever:leverco:aaaa-2", "ashby:ashbyco:ash-3", "ashby:ashbyco:ash-2"):
        assert bad not in sl
    # the draft step produced skeletons and stopped for approval; nothing was submitted
    assert out["steps"]["draft"]["awaiting_human_approval"] is True
    files = list(tmp_path.glob("*/application-package.md"))
    assert files and all("DRAFT_NOT_SENT" in f.read_text(encoding="utf-8") for f in files)
    assert store.db.execute("SELECT COUNT(*) c FROM application_packages WHERE status='SUBMITTED'").fetchone()["c"] == 0
    # live-only default view shows nothing: fixture data is not mistaken for real postings
    assert shortlist(store, 10) == []


def test_pipeline_resume_skips_completed_steps(store, evidence, profile, tmp_path):
    run_pipeline(store, evidence, profile, _companies(), http=_http(), run_id="t2", origin="fixture", out_dir=tmp_path)
    again = run_pipeline(store, evidence, profile, _companies(), http=_http(), run_id="t2", origin="fixture", out_dir=tmp_path)
    assert all("skipped" in v for v in again["steps"].values())


def test_failed_step_stops_the_run_and_is_logged(store, evidence, profile, tmp_path):
    class Boom:
        def fetch_jobs(self, company):
            raise RuntimeError("connector crashed")
    out = run_pipeline(store, evidence, profile, [Company("x", "x", "greenhouse")], connectors={"greenhouse": Boom()},
                       run_id="t3", origin="fixture", out_dir=tmp_path)
    assert out["stopped_at"] == "ingest" and "score" not in out["steps"]
    row = store.db.execute("SELECT status, detail FROM pipeline_runs WHERE run_id='t3' AND step='ingest'").fetchone()
    assert row["status"] == "failed" and "connector crashed" in row["detail"]


def test_access_denied_source_is_reported_not_retried_or_hidden(store, evidence, profile, tmp_path):
    from jobintel.http import Response
    http, t = fake_http({"greenhouse.io": Response(403, {}, b"")})
    out = run_pipeline(store, evidence, profile, [Company("x", "x", "greenhouse")], http=http, run_id="t4",
                       steps=["ingest"], origin="fixture", out_dir=tmp_path)
    assert out["steps"]["ingest"]["failed"][0]["status"] == "access_denied" and len(t.calls) == 1
