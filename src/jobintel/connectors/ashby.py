"""Ashby public job posting API.

GET https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true  (REST, no key).
Traps: the company name is not in the payload; there is no updated timestamp; unlisted jobs
(isListed false) are skipped.
"""
from __future__ import annotations

from ..models import Company, FetchResult, JobPosting, content_hash, html_to_text
from .base import Connector, now_iso, period_from_text

BASE = "https://api.ashbyhq.com/posting-api/job-board/{slug}"


class AshbyConnector(Connector):
    provider = "ashby"

    def fetch_jobs(self, company: Company, since: str | None = None) -> FetchResult:
        url = BASE.format(slug=company.slug)

        def run():
            resp = self.http.get(url, {"includeCompensation": "true"})
            data = resp.json()
            fetched = now_iso()
            raw_jobs = [j for j in data["jobs"] if j.get("isListed", True)]
            jobs = [self._normalize(company, j, url, fetched) for j in raw_jobs]
            if since:
                jobs = [j for j in jobs if not j.posted_at or j.posted_at >= since]
            return jobs, True

        return self._guarded(company, url, run)

    def _normalize(self, company: Company, j: dict, url: str, fetched: str) -> JobPosting:
        loc = j.get("location", "") or ""
        secondary = [s.get("location", "") for s in (j.get("secondaryLocations") or []) if s.get("location")]
        wt = (j.get("workplaceType") or "").lower()
        if wt == "remote" or j.get("isRemote") is True:
            rtype = "remote"
        elif wt == "hybrid":
            rtype = "hybrid"
        elif wt in ("onsite", "on-site", "on_site"):
            rtype = "onsite"
        else:
            rtype = "unknown"
        country = ((j.get("address") or {}).get("postalAddress") or {}).get("addressCountry", "") or ""
        if country and country not in loc:
            secondary.append(country)
        html = j.get("descriptionHtml", "") or ""
        text = j.get("descriptionPlain") or html_to_text(html)
        smin = smax = None
        cur = note = ""
        period = "unknown"
        comp = j.get("compensation") or {}
        for comp_item in comp.get("summaryComponents") or []:
            if (comp_item.get("compensationType") or "").lower() == "salary":
                smin, smax = comp_item.get("minValue"), comp_item.get("maxValue")
                cur = comp_item.get("currencyCode", "") or ""
                period = period_from_text(str(comp_item.get("interval", "")))
                break
        note = (comp.get("compensationTierSummary") or "")[:300]
        return JobPosting(
            provider=self.provider, company_slug=company.slug, external_id=str(j["id"]),
            company_name=company.name or company.slug, title=j.get("title", ""),
            source_url=url, fetched_at=fetched,
            canonical_url=j.get("jobUrl", ""), apply_url=j.get("applyUrl", "") or j.get("jobUrl", ""),
            department=j.get("department", "") or j.get("team", "") or "",
            description_text=text, description_html=html,
            location_raw=loc, extra_locations=secondary, remote_type=rtype,
            employment_type=j.get("employmentType", "") or "",
            salary_min=smin, salary_max=smax, currency=cur, salary_period=period, pay_note=note,
            posted_at=j.get("publishedAt", "") or "", updated_at="",
            raw_hash=content_hash(j.get("title"), loc, text, wt),
        )
