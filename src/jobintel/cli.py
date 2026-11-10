"""Command line: doctor, sources test, ingest, search, shortlist, draft, evidence, approve, confirm-submitted.

Run from the project root:  python -m jobintel <command>   (PYTHONPATH=src, or use jh.cmd)
Nothing here submits an application or sends a message.
"""
from __future__ import annotations

import argparse
import importlib
import json
import sqlite3
import sys
from pathlib import Path

from . import __version__
from .config import ROOT, companies_from_watchlist, load_profile, load_sources
from .connectors import CONNECTORS
from .evidence import EvidenceBase, EvidenceError
from .http import HttpClient
from .models import Company
from .pipeline import (draft_package_skeleton, ingest_company, run_pipeline, score_jobs, shortlist)
from .store import Store

DEFAULT_DB = ROOT / "data" / "jobintel.db"
EVIDENCE = ROOT / "data" / "evidence" / "evidence.json"
SKILLS = ROOT / "data" / "evidence" / "skills.json"


def _store(args) -> Store:
    return Store(args.db)


def _evidence() -> EvidenceBase:
    if not EVIDENCE.exists():
        raise SystemExit("data/evidence/evidence.json not found (private file). Run the interview or restore the seed.")
    return EvidenceBase.load(EVIDENCE, SKILLS)


def cmd_doctor(args) -> int:
    ok = True

    def line(level, msg):
        nonlocal ok
        ok = ok and level != "FAIL"
        print(f"[{level:4}] {msg}")

    line("ok" if sys.version_info >= (3, 10) else "FAIL", f"python {sys.version.split()[0]}")
    for mod in ("yaml", "jsonschema", "pytest"):
        try:
            importlib.import_module(mod)
            line("ok", f"module {mod}")
        except ImportError:
            line("FAIL" if mod != "pytest" else "warn", f"module {mod} missing (pip install -r requirements.txt)")
    try:
        c = sqlite3.connect(":memory:")
        c.execute("CREATE VIRTUAL TABLE t USING fts5(a)")
        line("ok", f"sqlite {sqlite3.sqlite_version} with FTS5")
    except sqlite3.OperationalError:
        line("FAIL", "sqlite without FTS5")
    try:
        prof = load_profile(args.profile)
        load_sources()
        if prof.get("onboarded") and prof.get("candidate_country"):
            line("ok", f"config loaded (profile '{args.profile or 'active'}', country {prof['candidate_country']})")
        else:
            line("warn", "profile not onboarded yet: open the folder in Claude Code and say hello to start the onboarding interview")
    except Exception as e:
        line("FAIL", f"config: {e}")
    try:
        base = _evidence()
        line("ok", f"evidence valid: {len(base.records)} records, {len(base.skills)} skills, "
                   f"{len(base.conflicts())} open conflicts to resolve in the interview")
    except (EvidenceError, SystemExit, Exception) as e:
        line("warn", f"evidence: {e}")
    try:
        st = Store(args.db)
        line("ok", f"database {args.db}: {st.count('job_postings')} postings, {st.count('companies')} companies")
        st.close()
    except Exception as e:
        line("FAIL", f"database: {e}")
    wl = ROOT / "scripts" / "watchlist.txt"
    line("ok" if wl.exists() else "warn", f"watchlist {wl.name}")
    for name, tool in (("postgresql", "psql"), ("docker", "docker"), ("ollama", "ollama")):
        import shutil
        line("info", f"{name}: {'found' if shutil.which(tool) else 'not installed (optional, see docs)'}")
    if args.online:
        res = CONNECTORS["greenhouse"](http=HttpClient()).health_check(Company("anthropic", "anthropic", "greenhouse"))
        line("ok" if res.status in ("ok", "empty") else "FAIL", f"live check greenhouse/anthropic: {res.status}, {len(res.jobs)} jobs, {res.latency_ms} ms")
    return 0 if ok else 1


def cmd_sources_test(args) -> int:
    conn = CONNECTORS[args.provider](http=HttpClient())
    res = conn.health_check(Company(args.slug, args.slug, args.provider))
    print(f"{args.provider}/{args.slug}: {res.status} http={res.http_status} jobs={len(res.jobs)} {res.latency_ms} ms {res.error}")
    if res.jobs:
        from . import eligibility
        from collections import Counter
        for j in res.jobs:
            eligibility.apply(j, load_profile(args.profile)["candidate_country"])
        print("eligibility:", dict(Counter(j.remote_class for j in res.jobs)))
        for j in res.jobs[: args.show]:
            print(f"  - {j.title} | {j.location_raw} | {j.remote_class} | {j.apply_url}")
    return 0 if res.status in ("ok", "empty", "empty_or_unknown", "not_found") else 1


def cmd_ingest(args) -> int:
    st, prof = _store(args), load_profile(args.profile)
    http = HttpClient(min_interval=args.interval)
    if args.slug:
        comps = [Company(args.slug, args.slug, args.provider, discovery_source="manual")]
    else:
        comps = companies_from_watchlist(providers=tuple(args.providers))[: args.limit]
    for c in comps:
        st.upsert_company(c)
    ok = 0
    for c in comps:
        r = ingest_company(st, CONNECTORS[c.provider](http=http), c, prof["candidate_country"])
        if r["status"] == "ok":
            ok += 1
        print(f"{c.provider:16}{c.slug:28}{r['status']:18} new={r['new']} upd={r['updated']} closed={r['closed']} {r['error']}")
    print(f"boards with postings: {ok}/{len(comps)}; total postings in database: {st.count('job_postings')}")
    return 0


def cmd_search(args) -> int:
    from .search import search
    st, prof = _store(args), load_profile(args.profile)
    res = search(st, prof, query=args.query, include_unverified=args.include_unverified, limit=args.limit)
    print("funnel:", json.dumps(res.funnel))
    for r in res.rows:
        print(f"{r['job_id']:48} {r['remote_class']:18} {r['title'][:60]} | {r['location_raw'][:40]}")
    if args.show_excluded:
        for jid, why in res.excluded:
            print(f"  excluded {jid}: {why}")
    return 0


def cmd_shortlist(args) -> int:
    st, prof, base = _store(args), load_profile(args.profile), _evidence()
    n = score_jobs(st, base, prof, run_id="cli")
    rows = shortlist(st, args.limit)
    print(f"scored {n} open eligible/unverified postings; showing up to {args.limit} (heuristic scores, not probabilities)")
    for r in rows:
        print(f"{r['priority']:5} {r['decision']:9} fit={r['fit_score']} ({r['fit_band']}) conf={r['confidence']} {r['company_name']}: {r['title']} [{r['job_id']}]")
    return 0


def cmd_draft(args) -> int:
    st, base = _store(args), _evidence()
    row = st.db.execute("SELECT s.* FROM job_scores s WHERE job_id=? ORDER BY id DESC LIMIT 1", (args.job_id,)).fetchone()
    if row is None:
        print("no score for this job: run `shortlist` first")
        return 1
    print(draft_package_skeleton(st, base, row, ROOT / "output" / "applications"))
    return 0


def cmd_evidence(args) -> int:
    try:
        base = _evidence()
    except EvidenceError as e:
        print("INVALID:", e)
        return 1
    print(f"valid: {len(base.records)} records, {len(base.skills)} skills")
    for ev, c in base.conflicts():
        print(f"  CONFLICT {ev}: {c}")
    states = {}
    for r in base.records.values():
        states[r["verification"]] = states.get(r["verification"], 0) + 1
    print("verification states:", states)
    return 0


def cmd_approve(args) -> int:
    from .approval import ApprovalError, approve
    st = _store(args)
    claims = json.loads(Path(args.claims).read_text(encoding="utf-8")) if args.claims else []
    try:
        print(approve(st, args.package, args.by, claims, acknowledge_unconfirmed=args.acknowledge_unconfirmed))
    except ApprovalError as e:
        print("REFUSED:", e)
        return 1
    return 0


def cmd_confirm_submitted(args) -> int:
    from .approval import ApprovalError, mark_submitted
    st = _store(args)
    claims = json.loads(Path(args.claims).read_text(encoding="utf-8")) if args.claims else []
    try:
        print(mark_submitted(st, args.package, args.by, args.ref, claims))
    except ApprovalError as e:
        print("REFUSED:", e)
        return 1
    return 0


def cmd_health(args) -> int:
    st = _store(args)
    rows = st.source_health()
    if not rows:
        print("no fetches recorded yet: run `ingest` first")
        return 0
    print(f"{'provider':16}{'slug':28}{'fetches':>8}{'ok':>4}{'err':>5}{'403':>5}{'404':>5}  last_status       last_fetch")
    for r in rows:
        print(f"{r['provider']:16}{r['slug'][:27]:28}{r['fetches']:>8}{r['ok']:>4}{r['errors']:>5}{r['denied']:>5}{r['not_found']:>5}  {r['last_status']:18}{r['last_fetch']}")
    by = st.db.execute("SELECT status, COUNT(*) c FROM source_fetches GROUP BY status").fetchall()
    print("fetch outcomes:", {r["status"]: r["c"] for r in by})
    return 0


def cmd_run(args) -> int:
    st, prof, base = _store(args), load_profile(args.profile), _evidence()
    comps = companies_from_watchlist(providers=tuple(args.providers))[: args.limit]
    for c in comps:
        st.upsert_company(c)
    print(json.dumps(run_pipeline(st, base, prof, comps, http=HttpClient(min_interval=args.interval),
                                  run_id=args.run_id, shortlist_limit=args.shortlist), indent=2, default=str))
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="jobintel", description=f"Career intelligence engine {__version__} (never submits or sends)")
    p.add_argument("--db", default=str(DEFAULT_DB))
    p.add_argument("--profile", default=None, help="profile name; default is active_profile in config/search-profiles.yaml")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("doctor"); s.add_argument("--online", action="store_true"); s.set_defaults(fn=cmd_doctor)
    s = sub.add_parser("sources-test"); s.add_argument("provider", choices=sorted(CONNECTORS)); s.add_argument("slug")
    s.add_argument("--show", type=int, default=5); s.set_defaults(fn=cmd_sources_test)
    s = sub.add_parser("ingest"); s.add_argument("--provider", choices=sorted(CONNECTORS), default="greenhouse"); s.add_argument("--slug")
    s.add_argument("--providers", nargs="+", default=sorted(CONNECTORS)); s.add_argument("--limit", type=int, default=25)
    s.add_argument("--interval", type=float, default=1.0); s.set_defaults(fn=cmd_ingest)
    s = sub.add_parser("search"); s.add_argument("--query"); s.add_argument("--limit", type=int, default=25)
    s.add_argument("--include-unverified", action="store_true"); s.add_argument("--show-excluded", action="store_true"); s.set_defaults(fn=cmd_search)
    s = sub.add_parser("shortlist"); s.add_argument("--limit", type=int, default=10); s.set_defaults(fn=cmd_shortlist)
    s = sub.add_parser("draft"); s.add_argument("--job-id", required=True); s.set_defaults(fn=cmd_draft)
    s = sub.add_parser("evidence"); s.set_defaults(fn=cmd_evidence)
    s = sub.add_parser("approve"); s.add_argument("--package", type=int, required=True); s.add_argument("--by", required=True)
    s.add_argument("--claims"); s.add_argument("--acknowledge-unconfirmed", action="store_true"); s.set_defaults(fn=cmd_approve)
    s = sub.add_parser("confirm-submitted"); s.add_argument("--package", type=int, required=True); s.add_argument("--by", required=True)
    s.add_argument("--ref", required=True); s.add_argument("--claims"); s.set_defaults(fn=cmd_confirm_submitted)
    s = sub.add_parser("health"); s.set_defaults(fn=cmd_health)
    s = sub.add_parser("run"); s.add_argument("--limit", type=int, default=25); s.add_argument("--providers", nargs="+", default=sorted(CONNECTORS))
    s.add_argument("--interval", type=float, default=1.0); s.add_argument("--run-id"); s.add_argument("--shortlist", type=int, default=10)
    s.set_defaults(fn=cmd_run)
    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
