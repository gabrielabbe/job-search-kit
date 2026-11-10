"""Hybrid retrieval: hard filters first, then full-text (FTS5 bm25) over role-family terms.

Semantic retrieval is intentionally absent (decision D-1). Fit and desirability are separate from this step.
"""
from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, field

from .store import Store

_PERIOD_TO_MONTHLY = {"monthly": 1.0, "annual": 1 / 12, "hourly": 173.33}


def monthly_usd(row, fx: dict) -> float | None:
    """Monthly USD pay, or None when amount, currency or period is unknown. Never defaults the period."""
    amt = row["salary_min"] if row["salary_min"] is not None else row["salary_max"]
    period = (row["salary_period"] or "unknown")
    cur = (row["currency"] or "").upper()
    if amt is None or period not in _PERIOD_TO_MONTHLY or cur not in fx:
        return None
    return float(amt) * _PERIOD_TO_MONTHLY[period] * fx[cur]


def fts_query(terms: list[str]) -> str:
    """OR of quoted phrases; quotes stripped so job text and config can never inject FTS syntax."""
    parts = ['"' + re.sub(r'["\']', " ", t).strip() + '"' for t in terms if t.strip()]
    return " OR ".join(parts)


@dataclass
class SearchResult:
    rows: list = field(default_factory=list)
    funnel: dict = field(default_factory=dict)
    excluded: list = field(default_factory=list)  # (job_id, reason)


def role_terms(profile: dict) -> list[str]:
    out = []
    for fam in profile["role_families"].values():
        out.extend(fam["terms"])
    return out


def search(store: Store, profile: dict, query: str | None = None, include_unverified: bool = False,
           limit: int = 50, origin: str = "live") -> SearchResult:
    """`origin` is 'live' (real postings only, the default), 'fixture' or 'any'."""
    res = SearchResult()
    fx = profile["pay"]["fx_to_usd"]
    floor = profile["pay"]["floor_monthly"]
    excl_terms = [t.lower() for t in profile.get("exclude_title_terms", [])]
    terms = [query] if query else role_terms(profile)
    q = fts_query(terms)
    db = store.db
    res.funnel["open_postings"] = db.execute("SELECT COUNT(*) c FROM job_postings WHERE status='OPEN'").fetchone()["c"]
    allowed = ("yes", "unknown") if include_unverified else ("yes",)
    try:
        rows = db.execute(
            f"""SELECT p.*, bm25(job_fts, 10.0, 1.0, 3.0, 1.0, 1.0) AS rank
                FROM job_fts JOIN job_postings p ON p.id = job_fts.rowid
                WHERE job_fts MATCH ? AND p.status='OPEN' AND p.eligible_for_candidate IN ({",".join("?" * len(allowed))})
                  AND (? = 'any' OR p.data_origin = ?)
                ORDER BY rank LIMIT ?""", (q, *allowed, origin, origin, 5000)).fetchall()
    except sqlite3.OperationalError as e:
        raise ValueError(f"search query rejected by FTS5: {e}") from e
    res.funnel["text_and_eligibility_match"] = len(rows)
    kept = []
    for r in rows:
        title = (r["title"] or "").lower()
        bad = next((t for t in excl_terms if re.search(rf"(?<![\w]){re.escape(t)}(?![\w])", title)), None)
        if bad:
            res.excluded.append((r["job_id"], f"excluded title term '{bad}'"))
            continue
        pay = monthly_usd(r, fx)
        if pay is not None and pay < floor:
            res.excluded.append((r["job_id"], f"stated pay about ${pay:,.0f}/month is below the ${floor:,} floor"))
            continue
        kept.append(r)
    res.funnel["after_title_and_pay_filters"] = len(kept)
    res.rows = kept[:limit]
    return res
