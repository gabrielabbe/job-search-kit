import copy
import json
from datetime import date

import pytest

from conftest import FIX, make_job
from jobintel import eligibility
from jobintel.evidence import EvidenceBase, EvidenceError, check_claim
from jobintel.fit import analyse, candidate_years, extract_requirements
from jobintel.models import FetchResult

TODAY = date(2026, 11, 6)


# ------------------------------------------------------------- evidence schema
def test_sample_evidence_validates(evidence):
    assert len(evidence.records) == 3 and len(evidence.skills) == 5


def test_invalid_record_is_rejected(tmp_path):
    data = json.loads((FIX / "evidence_sample.json").read_text(encoding="utf-8"))
    del data["records"][0]["verification"]
    p = tmp_path / "e.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(EvidenceError):
        EvidenceBase.load(p)


def test_duplicate_ids_and_unknown_skill_evidence_are_rejected(tmp_path):
    data = json.loads((FIX / "evidence_sample.json").read_text(encoding="utf-8"))
    data["records"].append(copy.deepcopy(data["records"][0]))
    p = tmp_path / "e.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(EvidenceError, match="duplicate"):
        EvidenceBase.load(p)
    sk = json.loads((FIX / "skills_sample.json").read_text(encoding="utf-8"))
    sk["skills"][0]["evidence_ids"] = ["EV-9999"]
    q = tmp_path / "s.json"
    q.write_text(json.dumps(sk), encoding="utf-8")
    with pytest.raises(EvidenceError, match="unknown evidence"):
        EvidenceBase.load(FIX / "evidence_sample.json", q)


def test_private_seed_validates_when_present():
    from jobintel.cli import EVIDENCE, SKILLS
    if not EVIDENCE.exists():
        pytest.skip("private seed not present")
    base = EvidenceBase.load(EVIDENCE, SKILLS)
    assert base.records and not [r for r in base.records.values() if r["verification"] == "contradicted"]
    # confirmed facts carry the interview source; open conflicts stay visible until resolved
    assert base.records["EV-0001"]["verification"] == "candidate_confirmed" and base.conflicts()
    assert base.records["EV-0015"]["disclosure"] == "restricted"  # the budget figure is not public: claims citing it are blocked


# ------------------------------------------------------------- adversarial claim fixtures
def test_200_person_organization_is_not_200_direct_reports(evidence):
    assert check_claim(evidence, "Manage 200 direct reports", ["EV-0001"]).status == "blocked"
    assert check_claim(evidence, "I run IT for a 200-person organization", ["EV-0001"]).status == "blocked"  # 200 not in evidence
    assert check_claim(evidence, "Lead a team of 3", ["EV-0001"]).status == "ok"


def test_reporting_line_needs_confirmation(evidence):
    assert check_claim(evidence, "Reports directly to the CEO", ["EV-0001"]).status == "ok"  # candidate_confirmed
    assert check_claim(evidence, "Reports directly to the CEO", ["EV-0002"]).status == "blocked"  # no reporting line recorded
    reported = copy.deepcopy(evidence)
    reported.records["EV-0001"]["verification"] = "candidate_reported"
    r = check_claim(reported, "Reports directly to the CEO", ["EV-0001"])
    assert r.status == "blocked" and any("not candidate_confirmed" in p for p in r.problems)
    assert check_claim(evidence, "Reports directly to the CFO", ["EV-0001"]).status == "blocked"  # CFO not in the recorded line


def test_invented_metric_and_missing_evidence_are_blocked(evidence):
    assert check_claim(evidence, "Cut ticket time by 80%", ["EV-0001"]).status == "blocked"
    assert check_claim(evidence, "Led IT", []).status == "blocked"
    assert check_claim(evidence, "Led IT", ["EV-9999"]).status == "blocked"
    assert check_claim(evidence, "Something", ["EV-0003"]).status == "blocked"  # unverified


def test_candidate_reported_needs_confirmation_not_block(evidence):
    r = check_claim(evidence, "Cut onboarding from 30-45 minutes to a few minutes", ["EV-0002"])
    assert r.status == "needs_confirmation" and r.warnings


def test_documented_gaps_and_unrecorded_tools_cannot_be_claimed(evidence):
    assert check_claim(evidence, "Deployed infrastructure on AWS", ["EV-0001"]).status == "blocked"
    assert check_claim(evidence, "Administered Okta for SSO", ["EV-0002"]).status == "blocked"


# ------------------------------------------------------------- fit analyst
def _row(store, **kw):
    j = eligibility.apply(make_job(**kw))
    store.ingest(FetchResult("greenhouse", j.company_slug, "u", "ok", [j], authoritative=True))
    return store.job(j.job_id)


REQ_TEXT = ("About the role\nOwn IT.\nRequirements\n- 5+ years of experience in IT operations\n- Strong Google Workspace administration\n"
            "- Identity and access management (SSO, MFA)\n- Experience with Okta\n- AWS certification required\n"
            "Nice to have\n- Experience supporting a BYOD workforce\n")


def test_extract_requirements_marks_must_and_preferred():
    reqs = extract_requirements(REQ_TEXT)
    assert [r.must for r in reqs] == [True, True, True, True, True, False]


def test_requirements_from_html_lists_without_bullet_markers():
    """Regression: short requirement lines were mistaken for headers (found by the end-to-end run)."""
    from jobintel.models import html_to_text
    html = ("<h3>Requirements</h3><ul><li>Experience with Okta</li><li>AWS certification required</li></ul>"
            "<h3>Nice to have</h3><ul><li>BYOD</li></ul><h3>Benefits</h3><ul><li>Health plan for the whole family</li></ul>")
    reqs = extract_requirements(html_to_text(html))
    assert [(r.text, r.must) for r in reqs] == [("Experience with Okta", True), ("AWS certification required", True), ("BYOD", False)]


def test_candidate_years_come_from_dated_roles_only(evidence):
    assert candidate_years(evidence, TODAY) == 3.8  # 2023-01 to 2026-11


def test_fit_matrix_separates_gap_unknown_and_borderline_years(store, evidence, profile):
    row = _row(store, title="IT Manager", description_text=REQ_TEXT, location_raw="Remote - Brazil")
    f = analyse(row, evidence, profile, today=TODAY)

    def req(prefix):
        return next(r for r in f.matrix if r["requirement"].startswith(prefix))
    assert f.gate_decision == "PASS"
    assert req("AWS certification")["rating"] == 0                       # documented gap
    assert req("Experience with Okta")["rating"] is None                # unrecorded: unknown, not zero
    years = req("5+ years")
    assert years["rating"] == 2 and "3.8 years" in years["gap"]
    assert any("cloud" in g for g in f.gaps)
    assert f.decision == "REVIEW"                                       # a required gap prevents PRIORITY
    assert f.priority is not None and f.fit_provisional is not None


def test_unknown_evidence_is_not_a_zero(store, evidence, profile):
    row = _row(store, title="IT Manager", description_text="Requirements\n- Experience with Okta\n- Experience with Slack administration\n")
    f = analyse(row, evidence, profile, today=TODAY)
    assert f.categories["skills"]["rating"] is None
    assert any("unknown" in u.lower() for u in f.unknowns)


def test_hard_gates_override_scores(store, evidence, profile):
    us = analyse(_row(store, external_id="a", canonical_url="https://t/a", location_raw="Remote - US", description_text=REQ_TEXT), evidence, profile, today=TODAY)
    assert us.gate_decision == "FAIL" and us.decision == "EXCLUDE" and us.priority is None
    hold = analyse(_row(store, external_id="b", canonical_url="https://t/b", location_raw="Remote", description_text=REQ_TEXT), evidence, profile, today=TODAY)
    assert hold.gate_decision == "HOLD_UNVERIFIED" and hold.priority is None
    low_pay = analyse(_row(store, external_id="c", canonical_url="https://t/c", salary_min=1500, salary_max=2000, currency="USD",
                           salary_period="monthly", description_text=REQ_TEXT), evidence, profile, today=TODAY)
    assert low_pay.gate_decision == "FAIL"
    hybrid = analyse(_row(store, external_id="d", canonical_url="https://t/d", remote_type="hybrid", description_text=REQ_TEXT), evidence, profile, today=TODAY)
    assert hybrid.gate_decision == "FAIL"


def test_closed_posting_fails_gate(store, evidence, profile):
    row = dict(_row(store, description_text=REQ_TEXT))
    row["status"] = "CLOSED"
    assert analyse(row, evidence, profile, today=TODAY).gate_decision == "FAIL"


def test_low_coverage_gives_a_band_not_a_precise_number(store, evidence, profile):
    row = _row(store, title="Quality Coordinator", description_text="We value teamwork.", location_raw="Remote - Brazil")
    f = analyse(row, evidence, profile, today=TODAY)
    assert f.fit_score is None and f.coverage < 0.7  # provisional only


def test_scores_are_never_labelled_probabilities(store, evidence, profile):
    f = analyse(_row(store, description_text=REQ_TEXT), evidence, profile, today=TODAY)
    assert "probab" not in json.dumps(f.__dict__, default=str).lower()
