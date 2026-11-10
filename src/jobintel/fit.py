"""Evidence-based Fit Analyst (deterministic, no LLM in the scoring path: decision D-8).

Implements Agents/fit-analyst.agent.md and data-contracts Contract B. Fit, priority and confidence are separate.
None of them is an interview probability. Unknown evidence is reported as unknown, never as a confirmed gap.

Rubric per criterion (0-4): 0 documented gap, 1 adjacent, 2 partial direct, 3 clear direct, 4 several outcomes.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime

from .evidence import EvidenceBase
from .models import INELIGIBLE
from .search import monthly_usd

# Headers are anchored at the start of a short line, so "AWS certification required" is a requirement, not a header.
MUST_HEADERS = re.compile(r"^(?:key |minimum |basic )?(requirements?|qualifications?|what you'?ll need|what we'?re looking for|"
                          r"must[- ]have|you have|about you|you bring|required (?:skills|qualifications|experience)|who you are)", re.I)
PREF_HEADERS = re.compile(r"^(?:nice[- ]to[- ]have|preferred|bonus|desirable|a plus|extra credit|bonus points)", re.I)
RESP_HEADERS = re.compile(r"^(?:key )?(responsibilit|what you'?ll do|the role|your role|about the role|in this role)", re.I)
BULLET = re.compile(r"^\s*(?:[-•*·▪–]|\d+[.)])\s+")
YEARS = re.compile(r"(\d+)\s*\+?\s*(?:or more\s*)?years?", re.I)

LEVELS = [(5, r"\b(chief|cto|cio|ciso)\b"), (4, r"\b(vp|vice president|director|head of)\b"),
          (3, r"\b(manager|lead|principal|staff|senior)\b"), (2, r"\b(engineer|specialist|analyst|administrator|associate|consultant)\b"),
          (1, r"\b(intern|junior|assistant)\b")]


@dataclass
class Requirement:
    text: str
    must: bool


@dataclass
class FitResult:
    job_id: str
    gate_decision: str  # PASS | HOLD_UNVERIFIED | FAIL
    hard_gate_reasons: list = field(default_factory=list)
    matrix: list = field(default_factory=list)
    categories: dict = field(default_factory=dict)
    fit_score: float | None = None
    fit_provisional: float | None = None
    fit_band: str = "unknown"
    coverage: float = 0.0
    desirability: float = 0.0
    contactability: float = 0.0
    hiring_signal: float = 0.0
    priority: float | None = None
    confidence: str = "LOW"
    decision: str = "DEFER"
    gaps: list = field(default_factory=list)
    unknowns: list = field(default_factory=list)
    open_questions: list = field(default_factory=list)


OTHER_HEADERS = re.compile(r"^(benefits?|perks|compensation|salary|about (us|the company|\w+)|our (values|culture|team|mission)|"
                           r"how to apply|equal opportunity|why (join|work)|what we offer|location|the team)", re.I)


def extract_requirements(text: str) -> list[Requirement]:
    """Section-aware extraction. A line is a header only if it names a known section (or ends with a colon) and is short;
    other short lines inside a requirements section are requirements (HTML lists often arrive without bullet markers).
    Falls back to every bullet as 'must' when no header is found."""
    reqs, mode, seen_header = [], None, False
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        is_bullet = bool(BULLET.match(line))
        body = BULLET.sub("", line).strip()
        if not is_bullet and len(line) <= 60:
            short = len(line.split()) <= 6
            hdr = ("pref" if PREF_HEADERS.search(line) and short else "must" if MUST_HEADERS.search(line) and short
                   else "resp" if RESP_HEADERS.search(line) and short else "other"
                   if (OTHER_HEADERS.search(line) and short) or line.endswith(":") else None)
            if hdr:
                mode, seen_header = (None if hdr == "other" else hdr), True
                continue
        if mode == "resp":
            continue
        collect = (mode in ("must", "pref") and (is_bullet or 8 < len(line) < 260)) or (mode is None and not seen_header and is_bullet)
        if collect:
            must = mode != "pref" and not re.search(r"\b(preferred|nice to have|bonus|a plus|desirable)\b", body, re.I)
            reqs.append(Requirement(body[:300], must))
    return reqs


def title_level(title: str) -> int | None:
    t = (title or "").lower()
    for lvl, rx in LEVELS:
        if re.search(rx, t):
            return lvl
    return None


def candidate_years(base: EvidenceBase, today: date | None = None) -> float:
    """Years derived from dated roles only (never a rounded-up figure). Earliest dated period start to today."""
    starts = []
    for r in base.records.values():
        s = (r.get("period") or {}).get("start")
        if s and re.match(r"\d{4}-\d{2}$", s) and r.get("role") not in ("Student",):
            starts.append(s)
    if not starts:
        return 0.0
    y, m = map(int, min(starts).split("-"))
    t = today or date.today()
    return round(((t.year - y) * 12 + (t.month - m)) / 12, 1)


def _skill_rating(base: EvidenceBase, skill: dict) -> int:
    p = skill.get("proficiency")
    if skill.get("kind") == "transferable":
        return 1
    if skill.get("kind") == "conceptual":
        return 1
    outcomes = sum(1 for ev in skill.get("evidence_ids", []) if base.records.get(ev, {}).get("outcomes"))
    if p is not None and p >= 4 and len(skill.get("evidence_ids", [])) >= 2 and outcomes >= 1:
        return 4
    if p is not None and p >= 4:
        return 3
    if p == 3 or p is None:
        return 2
    return 1


def _age_days(posted: str, first_seen: str, today: date) -> int | None:
    for s in (posted, first_seen):
        if s:
            try:
                return (today - datetime.fromisoformat(s.replace("Z", "+00:00")).date()).days
            except ValueError:
                continue
    return None


def analyse(job, base: EvidenceBase, profile: dict, contacts: int = 0, hiring_manager_contact: bool = False,
            today: date | None = None) -> FitResult:
    """`job` is a sqlite Row or dict from job_postings."""
    today = today or date.today()
    j = dict(job)
    res = FitResult(job_id=j["job_id"], gate_decision="PASS")
    thr, w = profile["thresholds"], profile["weights"]
    fx, pay_cfg = profile["pay"]["fx_to_usd"], profile["pay"]

    # ---- Stage 1: hard gates -------------------------------------------------
    if j["status"] != "OPEN":
        res.gate_decision = "FAIL"
        res.hard_gate_reasons.append(f"posting status is {j['status']}")
    if j["eligible_for_candidate"] == "no":
        res.gate_decision = "FAIL"
        res.hard_gate_reasons.append(f"geography: {j['eligibility_evidence']}")
    elif j["eligible_for_candidate"] != "yes" and res.gate_decision == "PASS":
        res.gate_decision = "HOLD_UNVERIFIED"
        res.hard_gate_reasons.append(f"geography unverified: {j['eligibility_evidence']}")
        res.open_questions.append("Ask the employer or recruiter whether a contractor or employee living in the candidate's country can be hired.")
    pay = monthly_usd(j, fx)
    if pay is not None and pay < pay_cfg["floor_monthly"]:
        res.gate_decision = "FAIL"
        res.hard_gate_reasons.append(f"stated pay about ${pay:,.0f}/month is below the ${pay_cfg['floor_monthly']:,} floor")
    elif pay is None:
        res.open_questions.append("Pay is not stated in a comparable form (amount, currency and period); ask before investing.")
    if profile.get("require_fully_remote") and j["remote_type"] in ("hybrid", "onsite"):
        res.gate_decision = "FAIL"
        res.hard_gate_reasons.append(f"work model is {j['remote_type']}")

    # ---- Stage 2: requirement -> evidence matrix --------------------------------
    reqs = extract_requirements(j.get("description_text") or "")
    years = candidate_years(base, today)
    must_ratings, matched_ev = [], set()
    for rq in reqs:
        row = {"requirement": rq.text, "must": rq.must, "evidence_ids": [], "rating": None, "certainty": "unknown", "gap": ""}
        skill = base.find_skill(rq.text)
        gap = base.find_gap(rq.text)
        ym = YEARS.search(rq.text)
        if skill:
            rating = _skill_rating(base, skill)
            row.update(evidence_ids=list(skill["evidence_ids"]), rating=rating,
                       certainty="medium" if skill["confidence"] != "high" else "high")
            matched_ev.update(skill["evidence_ids"])
            if skill.get("gaps"):
                row["gap"] = "; ".join(skill["gaps"])
        if gap and gap["status"] == "confirmed_gap" and not skill:
            row.update(rating=0, certainty="high", gap=f"documented gap: {gap['name']} ({gap['note']})")
            res.gaps.append(f"{gap['name']}: {gap['note']}" + ("" if not rq.must else " (REQUIRED)"))
        elif gap and gap["status"] == "unrecorded" and not skill:
            row["gap"] = f"{gap['name']} is not recorded (unknown, not a confirmed gap)"
            res.unknowns.append(f"{gap['name']}: {gap['note']}")
        if ym and row["rating"] is not None:
            need = int(ym.group(1))
            if need > years:
                row["rating"] = min(row["rating"], 2)
                row["gap"] = (row["gap"] + "; " if row["gap"] else "") + f"asks {need}+ years; dated roles total about {years} years"
                res.gaps.append(f"years: asks {need}+, dated roles about {years} (borderline, not an invented figure)")
        res.matrix.append(row)
        if row["rating"] is not None and rq.must:
            must_ratings.append(row["rating"])
    must_total = sum(1 for r in reqs if r.must)
    skills_cat = None
    if must_ratings:
        skills_cat = sum(must_ratings) / len(must_ratings)
    must_cov = (len(must_ratings) / must_total) if must_total else 0.0

    # achievements: matched evidence records that carry outcomes
    with_outcomes = [e for e in matched_ev if base.records.get(e, {}).get("outcomes")]
    ach = None
    if matched_ev:
        ach = 4 if len(with_outcomes) >= 3 else 3 if len(with_outcomes) == 2 else 2 if len(with_outcomes) == 1 else 1

    # seniority
    lvl = title_level(j["title"])
    sen = None
    if lvl is not None:
        d = lvl - profile["seniority_target"]
        sen = {0: 4, 1: 2, 2: 0, -1: 3, -2: 1}.get(d, 0 if d > 2 else 1)

    # domain
    text_l = f"{j['title']} {j.get('department') or ''} {(j.get('description_text') or '')[:4000]}".lower()
    dom_hits = [d for d in profile.get("domains", []) if d in text_l]
    dom = None if not dom_hits else (4 if len(dom_hits) >= 3 else 3 if len(dom_hits) == 2 else 2)

    # career alignment
    fam_level = None
    for fam in profile["role_families"].values():
        if any(t in f"{j['title'].lower()} {(j.get('department') or '').lower()}" for t in fam["terms"]):
            lv = {"north_star": 4, "target": 3, "adjacent": 2}[fam["level"]]
            fam_level = max(fam_level or 0, lv)
    career = fam_level if fam_level is not None else 0

    cats = {"skills": (skills_cat, w["fit"]["skills"]), "achievements": (ach, w["fit"]["achievements"]),
            "seniority": (sen, w["fit"]["seniority"]), "domain": (dom, w["fit"]["domain"]),
            "career": (career, w["fit"]["career"])}
    known_w = sum(wt for r, wt in cats.values() if r is not None)
    total_w = sum(wt for _, wt in cats.values())
    res.categories = {k: {"rating": (None if r is None else round(r, 2)), "weight": wt} for k, (r, wt) in cats.items()}
    res.coverage = round(known_w / total_w, 2) if total_w else 0.0
    if known_w:
        res.fit_provisional = round(sum((r / 4) * wt for r, wt in cats.values() if r is not None) / known_w * 100, 1)
        if res.coverage >= thr["min_coverage_for_number"]:
            res.fit_score = res.fit_provisional
    shown = res.fit_provisional
    res.fit_band = ("unknown" if shown is None else "strong" if shown >= thr["strong_fit"] else "moderate" if shown >= 50 else "weak")
    if skills_cat is None:
        res.unknowns.append("No requirement could be matched to evidence: skills category is unknown, not zero.")
    if must_total and must_cov < 0.5:
        res.unknowns.append(f"only {len(must_ratings)} of {must_total} required items map to known skills or gaps")

    # ---- Stage 3: desirability, contactability, hiring signal ---------------------
    des = 50.0
    if j["remote_type"] == "remote" or j["eligible_for_candidate"] == "yes":
        des += 15
    if pay is not None:
        des += 25 if pay >= pay_cfg["sweet_spot_monthly"] else 15 if pay >= pay_cfg["good_monthly"] else 5
    des += {4: 10, 3: 5}.get(fam_level or 0, 0)
    res.desirability = min(des, 100.0)
    res.contactability = 100.0 if hiring_manager_contact else 60.0 if contacts == 1 else 80.0 if contacts >= 2 else 0.0
    age = _age_days(j.get("posted_at", ""), j.get("first_seen_at", ""), today)
    res.hiring_signal = 40.0 if age is None else 100.0 if age <= 14 else 80.0 if age <= 30 else 50.0 if age <= 60 else 20.0
    if res.gate_decision == "PASS" and shown is not None:
        pw = w["priority"]
        res.priority = round(pw["fit"] * shown + pw["desirability"] * res.desirability +
                             pw["contactability"] * res.contactability + pw["hiring_signal"] * res.hiring_signal, 1)

    # ---- confidence and decision --------------------------------------------------
    long_text = len(j.get("description_text") or "") > 500
    res.confidence = "HIGH" if res.coverage >= 0.8 and long_text and must_cov >= 0.6 else \
        "MEDIUM" if res.coverage >= 0.6 and long_text else "LOW"
    required_gaps = [g for g in res.gaps if "(REQUIRED)" in g]
    if res.gate_decision == "FAIL":
        res.decision = "EXCLUDE"
    elif res.gate_decision == "HOLD_UNVERIFIED":
        res.decision = "REVIEW"
    elif len(required_gaps) >= 3 or res.fit_band in ("weak", "moderate") or shown is None:
        res.decision = "DEFER"  # below the 'strong' threshold (configurable, default 70): weak strategic or competency fit
    elif required_gaps or res.confidence == "LOW":
        res.decision = "REVIEW"
    elif res.fit_score is not None and res.fit_score >= thr["priority_fit"]:
        res.decision = "PRIORITY"
    else:
        res.decision = "REVIEW"
    if required_gaps and res.decision == "PRIORITY":
        res.decision = "REVIEW"
    return res
