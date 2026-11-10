"""SQLite store (FTS5 for full-text search). Candidate-private evidence stays in JSON files, not here.

Closure rule: a posting becomes CLOSED only when a *successful, authoritative* fetch of its board no longer
contains it. Timeouts, 5xx, 429 and 'empty_or_unknown' never close anything.
"""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse

from .models import CLOSED, OPEN, Company, FetchResult, JobPosting

MIGRATIONS = [
    # 1: core
    """
    CREATE TABLE companies (
        provider TEXT NOT NULL, slug TEXT NOT NULL, name TEXT, domain TEXT,
        discovery_source TEXT, ats_confidence TEXT DEFAULT 'unverified', last_verified TEXT,
        monitoring_priority INTEGER DEFAULT 3, PRIMARY KEY (provider, slug));
    CREATE TABLE source_fetches (
        id INTEGER PRIMARY KEY, provider TEXT, slug TEXT, source_url TEXT, fetched_at TEXT, status TEXT,
        http_status INTEGER, n_jobs INTEGER, snapshot_hash TEXT, error TEXT, latency_ms INTEGER);
    CREATE TABLE job_postings (
        id INTEGER PRIMARY KEY, job_id TEXT UNIQUE NOT NULL, provider TEXT, company_slug TEXT, external_id TEXT,
        company_name TEXT, title TEXT, department TEXT, description_text TEXT, location_raw TEXT,
        extra_locations TEXT, remote_type TEXT, employment_type TEXT, salary_min REAL, salary_max REAL,
        currency TEXT, salary_period TEXT, pay_note TEXT, posted_at TEXT, updated_at TEXT,
        first_seen_at TEXT, last_seen_at TEXT, status TEXT, closed_at TEXT,
        apply_url TEXT, canonical_url TEXT, canonical_key TEXT, source_url TEXT, raw_hash TEXT,
        remote_class TEXT, eligible_for_candidate TEXT, eligibility_evidence TEXT, time_zone_limits TEXT,
        work_from_anywhere_verified INTEGER DEFAULT 0, fuzzy_key TEXT, retrieval_status TEXT);
    CREATE INDEX idx_jobs_status ON job_postings(status, eligible_for_candidate);
    CREATE INDEX idx_jobs_canonical ON job_postings(canonical_key);
    CREATE INDEX idx_jobs_fuzzy ON job_postings(fuzzy_key);
    CREATE TABLE job_versions (
        id INTEGER PRIMARY KEY, job_id TEXT, raw_hash TEXT, seen_at TEXT, title TEXT, location_raw TEXT,
        description_text TEXT);
    CREATE TABLE duplicates (
        id INTEGER PRIMARY KEY, job_id TEXT, duplicate_of TEXT, method TEXT, needs_review INTEGER, found_at TEXT,
        UNIQUE(job_id, duplicate_of, method));
    CREATE VIRTUAL TABLE job_fts USING fts5(title, company_name, department, location_raw, description_text);
    """,
    # 2: scoring, contacts, applications, audit, pipeline
    """
    CREATE TABLE job_scores (
        id INTEGER PRIMARY KEY, job_id TEXT, scored_at TEXT, fit_score REAL, fit_band TEXT, coverage REAL,
        desirability REAL, contactability REAL, hiring_signal REAL, priority REAL, confidence TEXT,
        decision TEXT, detail_json TEXT);
    CREATE TABLE contacts (
        id INTEGER PRIMARY KEY, job_id TEXT, company TEXT, name TEXT, title TEXT, relation_to_role TEXT,
        profile_url TEXT, business_email TEXT, email_verification TEXT, source_url TEXT NOT NULL,
        checked_at TEXT NOT NULL, confidence TEXT, permitted_channel TEXT, opt_out INTEGER DEFAULT 0);
    CREATE TABLE application_packages (
        id INTEGER PRIMARY KEY, job_id TEXT, kind TEXT, status TEXT, version_hash TEXT, content_path TEXT,
        evidence_ids TEXT, created_at TEXT, approved_by TEXT, approved_at TEXT, approved_hash TEXT,
        submitted_at TEXT, confirmation_ref TEXT);
    CREATE TABLE application_events (
        id INTEGER PRIMARY KEY, package_id INTEGER, at TEXT, event TEXT, actor TEXT, detail TEXT);
    CREATE TABLE audit_events (id INTEGER PRIMARY KEY, at TEXT, actor TEXT, action TEXT, subject TEXT, detail TEXT);
    CREATE TABLE pipeline_runs (
        id INTEGER PRIMARY KEY, run_id TEXT, step TEXT, status TEXT, started_at TEXT, finished_at TEXT, detail TEXT,
        UNIQUE(run_id, step));
    """,
    # 3: real postings are distinguishable from test fixtures
    "ALTER TABLE job_postings ADD COLUMN data_origin TEXT DEFAULT 'live';",
]

_TRACKING = re.compile(r"^(utm_|gh_src$|source$|src$|ref$|referrer$|lever-|fbclid$|gclid$)", re.I)


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def canonical_key(url: str) -> str:
    """Host + path + the query parameters that identify the posting (for example gh_jid), without tracking
    parameters (utm_*, gh_src, source, ref...) or a trailing slash; empty if no url.
    Dropping every parameter would merge distinct jobs on a careers page that selects the job by ?gh_jid=ID."""
    if not url:
        return ""
    p = urlparse(url.strip())
    keep = sorted((k.lower(), v) for k, v in parse_qsl(p.query) if not _TRACKING.match(k))
    base = f"{p.netloc.lower()}{p.path.rstrip('/').lower()}"
    return base + ("?" + urlencode(keep) if keep else "")


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def fuzzy_key(company: str, title: str, location: str) -> str:
    return f"{_norm(company)}|{_norm(title)}|{_norm(location)}"


class Store:
    def __init__(self, path: str | Path = ":memory:"):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, timeout=30)  # wait for a concurrent writer instead of failing
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.migrate()

    # -- migrations ---------------------------------------------------------------
    def migrate(self) -> int:
        self.db.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER)")
        row = self.db.execute("SELECT MAX(version) v FROM schema_version").fetchone()
        current = row["v"] or 0
        for i, script in enumerate(MIGRATIONS, start=1):
            if i > current:
                self.db.executescript(script)
                self.db.execute("INSERT INTO schema_version VALUES (?)", (i,))
                self.db.commit()
        return len(MIGRATIONS)

    def audit(self, actor: str, action: str, subject: str = "", detail: str = "") -> None:
        self.db.execute("INSERT INTO audit_events(at,actor,action,subject,detail) VALUES (?,?,?,?,?)",
                        (now_iso(), actor, action, subject, detail))
        self.db.commit()

    # -- companies ----------------------------------------------------------------
    def upsert_company(self, c: Company) -> None:
        self.db.execute(
            """INSERT INTO companies(provider,slug,name,domain,discovery_source,ats_confidence,last_verified,monitoring_priority)
               VALUES (?,?,?,?,?,?,?,?)
               ON CONFLICT(provider,slug) DO UPDATE SET name=COALESCE(NULLIF(excluded.name,''),name),
                 domain=COALESCE(NULLIF(excluded.domain,''),domain)""",
            (c.provider, c.slug, c.name, c.domain, c.discovery_source, c.ats_confidence, c.last_verified,
             c.monitoring_priority))
        self.db.commit()

    def companies(self, provider: str | None = None) -> list[Company]:
        q, args = "SELECT * FROM companies", ()
        if provider:
            q, args = q + " WHERE provider=?", (provider,)
        return [Company(name=r["name"] or r["slug"], slug=r["slug"], provider=r["provider"], domain=r["domain"] or "",
                        discovery_source=r["discovery_source"] or "", ats_confidence=r["ats_confidence"] or "unverified",
                        last_verified=r["last_verified"] or "", monitoring_priority=r["monitoring_priority"] or 3)
                for r in self.db.execute(q + " ORDER BY monitoring_priority, slug", args)]

    # -- ingest -------------------------------------------------------------------
    def ingest(self, result: FetchResult) -> dict:
        """Persist one fetch: log it, upsert postings, version changes, flag duplicates, close only if authoritative."""
        now = now_iso()
        counts = {"new": 0, "updated": 0, "unchanged": 0, "closed": 0, "reopened": 0, "duplicates": 0}
        self.db.execute(
            "INSERT INTO source_fetches(provider,slug,source_url,fetched_at,status,http_status,n_jobs,snapshot_hash,error,latency_ms)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            (result.provider, result.slug, result.source_url, now, result.status, result.http_status,
             len(result.jobs), result.snapshot_hash, result.error, result.latency_ms))
        if result.status == "ok":
            self.db.execute("UPDATE companies SET ats_confidence='confirmed', last_verified=? WHERE provider=? AND slug=?",
                            (now, result.provider, result.slug))
        seen_ids = set()
        for j in result.jobs:
            seen_ids.add(j.job_id)
            counts_key = self._upsert_job(j, now)
            self.db.execute("UPDATE job_postings SET data_origin=? WHERE job_id=?", (j.data_origin, j.job_id))
            counts[counts_key] += 1
            if self._flag_duplicates(j, now):
                counts["duplicates"] += 1
        if result.authoritative:
            rows = self.db.execute(
                "SELECT job_id FROM job_postings WHERE provider=? AND company_slug=? AND status=?",
                (result.provider, result.slug, OPEN)).fetchall()
            for r in rows:
                if r["job_id"] not in seen_ids:
                    self.db.execute("UPDATE job_postings SET status=?, closed_at=? WHERE job_id=?",
                                    (CLOSED, now, r["job_id"]))
                    counts["closed"] += 1
        self.db.commit()
        return counts

    def _upsert_job(self, j: JobPosting, now: str) -> str:
        row = self.db.execute("SELECT id, raw_hash, status FROM job_postings WHERE job_id=?", (j.job_id,)).fetchone()
        ck = canonical_key(j.canonical_url)
        fk = fuzzy_key(j.company_name, j.title, j.location_raw)
        vals = (j.company_name, j.title, j.department, j.description_text, j.location_raw,
                json.dumps(j.extra_locations, ensure_ascii=False), j.remote_type, j.employment_type, j.salary_min,
                j.salary_max, j.currency, j.salary_period, j.pay_note, j.posted_at, j.updated_at, now,
                j.apply_url, j.canonical_url, ck, j.source_url, j.raw_hash, j.remote_class, j.eligible_for_candidate,
                j.eligibility_evidence, j.time_zone_limits, int(j.work_from_anywhere_verified), fk)
        if row is None:
            cur = self.db.execute(
                """INSERT INTO job_postings(company_name,title,department,description_text,location_raw,extra_locations,
                   remote_type,employment_type,salary_min,salary_max,currency,salary_period,pay_note,posted_at,updated_at,
                   last_seen_at,apply_url,canonical_url,canonical_key,source_url,raw_hash,remote_class,
                   eligible_for_candidate,eligibility_evidence,time_zone_limits,work_from_anywhere_verified,fuzzy_key,
                   job_id,provider,company_slug,external_id,first_seen_at,status,retrieval_status)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'ok')""",
                vals + (j.job_id, j.provider, j.company_slug, j.external_id, now, OPEN))
            rowid = cur.lastrowid
            self._version(j, now)
            self._fts(rowid, j)
            return "new"
        rowid = row["id"]
        changed = row["raw_hash"] != j.raw_hash
        reopened = row["status"] == CLOSED
        self.db.execute(
            """UPDATE job_postings SET company_name=?,title=?,department=?,description_text=?,location_raw=?,
               extra_locations=?,remote_type=?,employment_type=?,salary_min=?,salary_max=?,currency=?,salary_period=?,
               pay_note=?,posted_at=?,updated_at=?,last_seen_at=?,apply_url=?,canonical_url=?,canonical_key=?,
               source_url=?,raw_hash=?,remote_class=?,eligible_for_candidate=?,eligibility_evidence=?,
               time_zone_limits=?,work_from_anywhere_verified=?,fuzzy_key=?,status='OPEN',closed_at=NULL,
               retrieval_status='ok' WHERE job_id=?""", vals + (j.job_id,))
        if changed:
            self._version(j, now)
            self._fts(rowid, j)
        if reopened:
            return "reopened"
        return "updated" if changed else "unchanged"

    def _version(self, j: JobPosting, now: str) -> None:
        self.db.execute("INSERT INTO job_versions(job_id,raw_hash,seen_at,title,location_raw,description_text) VALUES (?,?,?,?,?,?)",
                        (j.job_id, j.raw_hash, now, j.title, j.location_raw, j.description_text))

    def _fts(self, rowid: int, j: JobPosting) -> None:
        self.db.execute("DELETE FROM job_fts WHERE rowid=?", (rowid,))
        self.db.execute("INSERT INTO job_fts(rowid,title,company_name,department,location_raw,description_text) VALUES (?,?,?,?,?,?)",
                        (rowid, j.title, j.company_name, j.department, j.location_raw, j.description_text))

    def _flag_duplicates(self, j: JobPosting, now: str) -> bool:
        """Dedupe order: provider+external_id (the primary key), canonical URL, then fuzzy (needs human review)."""
        found = False
        ck = canonical_key(j.canonical_url)
        if ck:
            for r in self.db.execute("SELECT job_id FROM job_postings WHERE canonical_key=? AND job_id<>?", (ck, j.job_id)):
                found |= self._dup(j.job_id, r["job_id"], "canonical_url", 0, now)
        fk = fuzzy_key(j.company_name, j.title, j.location_raw)
        for r in self.db.execute("SELECT job_id FROM job_postings WHERE fuzzy_key=? AND job_id<>? AND provider<>?",
                                 (fk, j.job_id, j.provider)):
            found |= self._dup(j.job_id, r["job_id"], "fuzzy", 1, now)
        return found

    def _dup(self, job_id: str, other: str, method: str, review: int, now: str) -> bool:
        a, b = sorted([job_id, other])
        cur = self.db.execute("INSERT OR IGNORE INTO duplicates(job_id,duplicate_of,method,needs_review,found_at) VALUES (?,?,?,?,?)",
                              (a, b, method, review, now))
        return cur.rowcount > 0

    def rebuild_dedupe(self) -> dict:
        """Recompute canonical and fuzzy keys for every posting and redo duplicate flags (used after a key-rule change)."""
        now = now_iso()
        self.db.execute("DELETE FROM duplicates")
        for r in self.db.execute("SELECT job_id, canonical_url, company_name, title, location_raw FROM job_postings").fetchall():
            self.db.execute("UPDATE job_postings SET canonical_key=?, fuzzy_key=? WHERE job_id=?",
                            (canonical_key(r["canonical_url"]), fuzzy_key(r["company_name"], r["title"], r["location_raw"]), r["job_id"]))
        n = 0
        for col, method, review, extra in (("canonical_key", "canonical_url", 0, ""), ("fuzzy_key", "fuzzy", 1, " AND provider<>(SELECT provider FROM job_postings q WHERE q.job_id=job_postings.job_id)")):
            keys = [r[0] for r in self.db.execute(f"SELECT {col} FROM job_postings WHERE {col}<>'' GROUP BY {col} HAVING COUNT(*)>1")]
            for k in keys:
                ids = [r[0] for r in self.db.execute(f"SELECT job_id FROM job_postings WHERE {col}=? ORDER BY job_id", (k,))]
                for other in ids[1:]:
                    if method == "fuzzy" and other.split(":")[0] == ids[0].split(":")[0]:
                        continue  # same provider: not a cross-source duplicate
                    n += self._dup(other, ids[0], method, review, now)
        self.db.commit()
        return {"duplicate_flags": n}

    # -- reads --------------------------------------------------------------------
    def job(self, job_id: str) -> sqlite3.Row | None:
        return self.db.execute("SELECT * FROM job_postings WHERE job_id=?", (job_id,)).fetchone()

    def count(self, table: str) -> int:
        return self.db.execute(f"SELECT COUNT(*) c FROM {table}").fetchone()["c"]  # table names are internal constants

    def duplicates(self, only_review: bool = False) -> list[sqlite3.Row]:
        q = "SELECT * FROM duplicates" + (" WHERE needs_review=1" if only_review else "")
        return self.db.execute(q).fetchall()

    def source_health(self) -> list[sqlite3.Row]:
        return self.db.execute(
            """SELECT provider, slug, COUNT(*) fetches, SUM(status='ok') ok, SUM(status='error') errors,
                      SUM(status='access_denied') denied, SUM(status='not_found') not_found,
                      MAX(fetched_at) last_fetch, AVG(latency_ms) avg_latency_ms,
                      (SELECT status FROM source_fetches f2 WHERE f2.provider=f.provider AND f2.slug=f.slug
                        ORDER BY id DESC LIMIT 1) last_status
               FROM source_fetches f GROUP BY provider, slug ORDER BY provider, slug""").fetchall()

    def close(self) -> None:
        self.db.close()
