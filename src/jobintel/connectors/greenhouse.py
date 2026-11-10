"""Greenhouse Job Board API (public).

GET https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true&pay_transparency=true
Traps handled (see GregoryBolshakov/ats-job-boards-reference):
- 404 = unknown slug; 200 with jobs=[] = real board, nothing open.
- `content=false` also removes departments/offices, so content=true is requested.
- Pay is only present with pay_transparency=true, as an ARRAY of ranges in integer CENTS; the period is only
  in the free-text title, so it is never defaulted to annual.
"""
from __future__ import annotations

from ..models import Company, FetchResult, JobPosting, content_hash, html_to_text
from .base import Connector, now_iso, period_from_text

BASE = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"


class GreenhouseConnector(Connector):
    provider = "greenhouse"

    def fetch_jobs(self, company: Company, since: str | None = None) -> FetchResult:
        url = BASE.format(slug=company.slug)

        def run():
            resp = self.http.get(url, {"content": "true", "pay_transparency": "true"})
            data = resp.json()
            fetched = now_iso()
            jobs = [self._normalize(company, j, url, fetched) for j in data["jobs"]]
            if since:
                jobs = [j for j in jobs if not j.updated_at or j.updated_at >= since]
            return jobs, True  # an empty 200 is a real, empty board on Greenhouse

        return self._guarded(company, url, run)

    def _normalize(self, company: Company, j: dict, url: str, fetched: str) -> JobPosting:
        loc = (j.get("location") or {}).get("name", "") or ""
        offices = [o.get("name", "") for o in (j.get("offices") or []) if o.get("name")]
        depts = [d.get("name", "") for d in (j.get("departments") or []) if d.get("name")]
        html = j.get("content", "") or ""
        text = html_to_text(html)
        pay = (j.get("pay_input_ranges") or [None])[0]
        smin = smax = None
        cur = note = ""
        period = "unknown"
        if pay:
            if pay.get("min_cents") is not None:
                smin = pay["min_cents"] / 100
            if pay.get("max_cents") is not None:
                smax = pay["max_cents"] / 100
            cur = pay.get("currency_type", "") or ""
            period = period_from_text(pay.get("title", ""))
            note = html_to_text(pay.get("blurb", ""))[:300]  # may say "On Target Earnings"
        lowered = (loc + " " + " ".join(offices)).lower()
        rtype = "remote" if "remote" in lowered else "unknown"
        return JobPosting(
            provider=self.provider, company_slug=company.slug, external_id=str(j["id"]),
            company_name=company.name or company.slug, title=j.get("title", ""),
            source_url=url, fetched_at=fetched,
            canonical_url=j.get("absolute_url", ""), apply_url=j.get("absolute_url", ""),
            department="; ".join(depts), description_text=text, description_html=html,
            location_raw=loc, extra_locations=[o for o in offices if o and o != loc],
            remote_type=rtype, salary_min=smin, salary_max=smax, currency=cur, salary_period=period,
            pay_note=note, posted_at=j.get("first_published", "") or "", updated_at=j.get("updated_at", "") or "",
            raw_hash=content_hash(j.get("title"), loc, text, j.get("updated_at")),
        )
