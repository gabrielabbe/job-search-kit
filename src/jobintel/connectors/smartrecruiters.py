"""SmartRecruiters public postings API.

GET https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=100&offset=N
Traps: `limit` above 100 is ignored, so paging on offset is mandatory (silently losing everything past 100 looks
like a successful fetch); an unknown slug answers 200 with totalFound 0, so zero rows can never be called an
empty board (status `empty_or_unknown`, never authoritative). Descriptions need the detail endpoint
GET /v1/companies/{slug}/postings/{id}, fetched on demand by fetch_job().
"""
from __future__ import annotations

from ..models import Company, FetchResult, JobPosting, content_hash, html_to_text
from .base import Connector, now_iso

BASE = "https://api.smartrecruiters.com/v1/companies/{slug}/postings"
PAGE = 100
MAX_PAGES = 50  # hard stop: 5,000 postings per board


class SmartRecruitersConnector(Connector):
    provider = "smartrecruiters"

    def fetch_jobs(self, company: Company, since: str | None = None) -> FetchResult:
        url = BASE.format(slug=company.slug)

        def run():
            fetched = now_iso()
            jobs: list[JobPosting] = []
            offset = 0
            for _ in range(MAX_PAGES):
                data = self.http.get(url, {"limit": PAGE, "offset": offset}).json()
                items = data["content"]
                jobs.extend(self._normalize(company, j, url, fetched) for j in items)
                total = int(data.get("totalFound", len(jobs)))
                offset += PAGE
                if not items or offset >= total:
                    break
            if since:
                jobs = [j for j in jobs if not j.posted_at or j.posted_at >= since]
            return jobs, False  # zero rows is ambiguous on this provider

        return self._guarded(company, url, run)

    def fetch_job(self, company: Company, external_id: str) -> JobPosting | None:
        url = f"{BASE.format(slug=company.slug)}/{external_id}"
        data = self.http.get(url).json()
        job = self._normalize(company, data, url, now_iso())
        sections = ((data.get("jobAd") or {}).get("sections") or {})
        html = "\n".join((sections.get(k) or {}).get("text", "") for k in
                         ("companyDescription", "jobDescription", "qualifications", "additionalInformation"))
        job.description_html = html
        job.description_text = html_to_text(html)
        job.apply_url = data.get("applyUrl", job.apply_url) or job.apply_url
        job.raw_hash = content_hash(job.title, job.location_raw, job.description_text)
        return job

    def _normalize(self, company: Company, j: dict, url: str, fetched: str) -> JobPosting:
        loc = j.get("location") or {}
        where = loc.get("fullLocation") or ", ".join(
            x for x in (loc.get("city"), loc.get("region"), loc.get("country")) if x)
        country = (loc.get("country") or "")
        if loc.get("remote") is True:
            rtype = "remote"
        elif loc.get("hybrid") is True:
            rtype = "hybrid"
        elif where:
            rtype = "onsite"
        else:
            rtype = "unknown"
        ext = str(j["id"])
        public = f"https://jobs.smartrecruiters.com/{company.slug}/{ext}"
        dept = (j.get("department") or {}).get("label", "") or ""
        emp = (j.get("typeOfEmployment") or {}).get("label", "") or ""
        # keep the ISO country code visible to the eligibility step
        loc_raw = f"{where} ({country.upper()})" if country and country.upper() not in where.upper() else where
        return JobPosting(
            provider=self.provider, company_slug=company.slug, external_id=ext,
            company_name=(j.get("company") or {}).get("name") or company.name or company.slug,
            title=j.get("name", ""), source_url=url, fetched_at=fetched,
            canonical_url=public, apply_url=public, department=dept,
            location_raw=loc_raw, remote_type=rtype, employment_type=emp,
            posted_at=j.get("releasedDate", "") or "",
            raw_hash=content_hash(j.get("name"), loc_raw, rtype),
        )
