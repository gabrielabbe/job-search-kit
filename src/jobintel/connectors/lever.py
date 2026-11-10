"""Lever Postings API (public).

GET https://api.lever.co/v0/postings/{slug}?mode=json  -> a bare array (whole board).
Traps: the payload never carries the company name (filled from the registry); no updated timestamp
(changes are detected by content hash); an ATS migration can leave a dead board answering 200 [].
"""
from __future__ import annotations

from datetime import datetime, timezone

from ..models import Company, FetchResult, JobPosting, content_hash, html_to_text
from .base import Connector, now_iso, period_from_text

BASE = "https://api.lever.co/v0/postings/{slug}"


def _ms_to_iso(ms) -> str:
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError, OSError):
        return ""


class LeverConnector(Connector):
    provider = "lever"

    def fetch_jobs(self, company: Company, since: str | None = None) -> FetchResult:
        url = BASE.format(slug=company.slug)

        def run():
            resp = self.http.get(url, {"mode": "json"})
            data = resp.json()
            if not isinstance(data, list):
                raise ValueError("expected a JSON array")
            fetched = now_iso()
            jobs = [self._normalize(company, j, url, fetched) for j in data]
            if since:
                jobs = [j for j in jobs if not j.posted_at or j.posted_at >= since]
            return jobs, True

        return self._guarded(company, url, run)

    def _normalize(self, company: Company, j: dict, url: str, fetched: str) -> JobPosting:
        cats = j.get("categories") or {}
        loc = cats.get("location", "") or ""
        all_locs = [x for x in (cats.get("allLocations") or []) if x and x != loc]
        wt = (j.get("workplaceType") or "").lower()
        rtype = {"remote": "remote", "hybrid": "hybrid", "on-site": "onsite", "onsite": "onsite"}.get(wt, "unknown")
        text = j.get("descriptionPlain") or html_to_text(j.get("description", ""))
        extra = j.get("additionalPlain") or ""
        if extra:
            text = f"{text}\n{extra}"
        sr = j.get("salaryRange") or {}
        smin, smax = sr.get("min"), sr.get("max")
        period = period_from_text(sr.get("interval", ""))
        country = j.get("country") or ""
        if country and country not in loc:
            all_locs.append(country)
        return JobPosting(
            provider=self.provider, company_slug=company.slug, external_id=str(j["id"]),
            company_name=company.name or company.slug, title=j.get("text", ""),
            source_url=url, fetched_at=fetched,
            canonical_url=j.get("hostedUrl", ""), apply_url=j.get("applyUrl", "") or j.get("hostedUrl", ""),
            department=cats.get("department", "") or cats.get("team", "") or "",
            description_text=text, description_html=j.get("description", "") or "",
            location_raw=loc, extra_locations=all_locs, remote_type=rtype,
            employment_type=cats.get("commitment", "") or "",
            salary_min=smin, salary_max=smax, currency=sr.get("currency", "") or "", salary_period=period,
            pay_note=(j.get("salaryDescriptionPlain") or "")[:300],
            posted_at=_ms_to_iso(j.get("createdAt")), updated_at="",
            raw_hash=content_hash(j.get("text"), loc, text, wt),
        )
