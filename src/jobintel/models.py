"""Typed records shared by connectors, store, eligibility, fit and approval."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from html import unescape
from typing import Any

# Geography classes (Agents/data-contracts.md Contract A)
CONFIRMED_GLOBAL = "CONFIRMED_GLOBAL"
CONFIRMED_COUNTRY = "CONFIRMED_COUNTRY"
CONFIRMED_REGION = "CONFIRMED_REGION"
UNVERIFIED = "UNVERIFIED"
INELIGIBLE = "INELIGIBLE"
REMOTE_CLASSES = (CONFIRMED_GLOBAL, CONFIRMED_COUNTRY, CONFIRMED_REGION, UNVERIFIED, INELIGIBLE)

# Posting status
OPEN = "OPEN"
CLOSED = "CLOSED"
STATUS_UNVERIFIED = "UNVERIFIED"

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"[ \t\r\f\v]+")
_BREAKS = re.compile(r"</(p|div|li|h[1-6]|ul|ol|br)>|<br\s*/?>", re.I)
_LI = re.compile(r"<li[^>]*>", re.I)
_SCRIPT = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.I | re.S)


def html_to_text(html: str | None) -> str:
    """Reduce HTML to plain text. Scripts and styles are dropped, entities decoded.

    Job text is untrusted data: nothing in it is ever executed or followed as an instruction.
    """
    if not html:
        return ""
    s = unescape(html)  # Greenhouse returns HTML-escaped HTML
    s = _SCRIPT.sub(" ", s)
    s = _LI.sub("\n- ", s)  # keep list items recognizable as bullets
    s = _BREAKS.sub("\n", s)
    s = _TAG.sub(" ", s)
    s = unescape(s)
    lines = [_WS.sub(" ", ln).strip() for ln in s.split("\n")]
    return "\n".join(ln for ln in lines if ln)


@dataclass
class Company:
    name: str
    slug: str
    provider: str
    domain: str = ""
    discovery_source: str = "manual"
    ats_confidence: str = "unverified"  # unverified | confirmed (a fetch returned rows)
    last_verified: str = ""
    monitoring_priority: int = 3


@dataclass
class JobPosting:
    provider: str
    company_slug: str
    external_id: str
    company_name: str
    title: str
    source_url: str  # the API URL the record came from (provenance)
    fetched_at: str
    canonical_url: str = ""
    apply_url: str = ""
    department: str = ""
    description_text: str = ""
    description_html: str = ""
    location_raw: str = ""
    extra_locations: list[str] = field(default_factory=list)
    remote_type: str = "unknown"  # remote | hybrid | onsite | unknown
    employment_type: str = ""
    salary_min: float | None = None
    salary_max: float | None = None
    currency: str = ""
    salary_period: str = "unknown"  # annual | monthly | hourly | unknown
    pay_note: str = ""
    posted_at: str = ""
    updated_at: str = ""
    raw_hash: str = ""
    data_origin: str = "live"  # live (real network fetch) | fixture (test data). Search and shortlist default to live only.
    # filled by eligibility
    remote_class: str = UNVERIFIED
    eligible_for_candidate: str = "unknown"  # yes | no | unknown
    eligibility_evidence: str = ""
    time_zone_limits: str = ""
    work_from_anywhere_verified: bool = False

    @property
    def job_id(self) -> str:
        return f"{self.provider}:{self.company_slug}:{self.external_id}"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["job_id"] = self.job_id
        return d


def content_hash(*parts: Any) -> str:
    """Stable hash of the fields whose change means 'the posting changed'."""
    blob = json.dumps(parts, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


@dataclass
class FetchResult:
    provider: str
    slug: str
    source_url: str
    status: str  # ok | empty | empty_or_unknown | not_found | access_denied | error
    jobs: list[JobPosting] = field(default_factory=list)
    http_status: int | None = None
    error: str = ""
    snapshot_hash: str = ""
    latency_ms: int = 0
    # True only when the board answered successfully and the list is the complete board.
    # Closure of missing postings is allowed only when this is True.
    authoritative: bool = False
