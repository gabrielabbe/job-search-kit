"""Connector interface from job-turbo-upgrade/01-SOURCE-CONNECTORS.md.

discover_companies(), fetch_jobs(company, since?), fetch_job(id), health_check().
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

from ..http import AccessDenied, FetchError, HttpClient, NotFound
from ..models import Company, FetchResult, JobPosting, content_hash


import re

SLUG_RX = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,80}$")


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def period_from_text(text: str) -> str:
    """Pay period is only trusted when the text says it. Never default to annual."""
    t = (text or "").lower()
    if any(w in t for w in ("hour", "hourly", "/hr", "per hr")):
        return "hourly"
    if any(w in t for w in ("month", "monthly")):
        return "monthly"
    if any(w in t for w in ("annual", "year", "yearly", "salary", "per annum")):
        return "annual"
    return "unknown"


class Connector:
    provider = "base"

    def __init__(self, http: HttpClient | None = None, registry: list[Company] | None = None):
        self.http = http or HttpClient()
        self.registry = registry or []

    # -- interface -----------------------------------------------------------------
    def discover_companies(self) -> list[Company]:
        """Companies come only from the user's registry. Slugs are never guessed or brute-forced."""
        return [c for c in self.registry if c.provider == self.provider]

    def fetch_jobs(self, company: Company, since: str | None = None) -> FetchResult:
        raise NotImplementedError

    def fetch_job(self, company: Company, external_id: str) -> JobPosting | None:
        for j in self.fetch_jobs(company).jobs:
            if j.external_id == external_id:
                return j
        return None

    def health_check(self, company: Company) -> FetchResult:
        """A real fetch, reported honestly. Used by `sources test`."""
        return self.fetch_jobs(company)

    # -- helpers -------------------------------------------------------------------
    def _guarded(self, company: Company, url: str, fn) -> FetchResult:
        """Run `fn()` -> (jobs, authoritative, empty_status) and map failures to explicit statuses."""
        t0 = time.monotonic()
        res = FetchResult(provider=self.provider, slug=company.slug, source_url=url, status="error")
        if not SLUG_RX.match(company.slug or ""):  # never build a URL from a slug that is not a plain board token
            res.error = f"invalid slug {company.slug[:40]!r}: not requested"
            return res
        try:
            jobs, authoritative_empty = fn()
            for j in jobs:
                j.data_origin = self.http.origin
            res.jobs = jobs
            if jobs:
                res.status, res.authoritative = "ok", True
            elif authoritative_empty:
                res.status, res.authoritative = "empty", True  # real board, nothing open
            else:
                res.status = "empty_or_unknown"  # cannot tell a wrong slug from an empty board
            res.http_status = 200
            res.snapshot_hash = content_hash(sorted(j.raw_hash for j in jobs))
        except NotFound:
            res.status, res.http_status = "not_found", 404
        except AccessDenied as e:
            res.status, res.error = "access_denied", str(e)
        except FetchError as e:
            res.status, res.error = "error", str(e)
        except (ValueError, KeyError, TypeError) as e:  # malformed payload
            res.status, res.error = "error", f"malformed payload: {type(e).__name__}: {e}"
        res.latency_ms = int((time.monotonic() - t0) * 1000)
        return res
