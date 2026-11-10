"""Find companies that hire in the candidate's country / worldwide, then locate their official job boards.

Usage: python scripts/discover_companies.py
Pulls company names from Himalayas' server-side country and worldwide searches (broad titles, many pages),
tries slug variants against every ATS fetcher in scan_jobs.py, and appends live boards to scripts/watchlist.txt.
Company career pages are where the roles that never reach LinkedIn or Indeed live. Read-only, nothing is submitted.
"""
import re
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import profile_loader
import scan_jobs
from scan_jobs import WATCHLIST, get, scan_slug

QUERIES = ["manager", "operations", "IT", "systems", "analyst", "director", "lead", "specialist", "automation",
           "AI", "security", "data", "marketing", "customer success", "implementation", "program", "support",
           "administrator", "consultant", "education", "learning", "finance", "people", "revenue"]
SUFFIX = re.compile(r"\b(inc|llc|ltd|limited|gmbh|co|corp|corporation|company|sa|s\.a\.|ag|plc|labs?|technologies|technology|group)\b\.?", re.I)


def variants(name, himalayas_slug=""):
    base = SUFFIX.sub("", re.sub(r"[^\w\s-]", "", name.lower())).strip()
    out = {himalayas_slug, base.replace(" ", ""), base.replace(" ", "-"), base.split(" ")[0] if base else ""}
    return {v for v in out if v and 2 < len(v) < 40}


def companies():
    found = {}
    for q in QUERIES:
        for geo in (f"country={urllib.parse.quote(profile_loader.country_name(profile_loader.require_onboarded()))}", "worldwide=true"):
            for off in (0, 100, 200):
                try:
                    d = get(f"https://himalayas.app/jobs/api/search?q={urllib.parse.quote(q)}&{geo}&limit=100&offset={off}", timeout=40)
                except Exception:
                    break
                jobs = d.get("jobs", [])
                for j in jobs:
                    found.setdefault(j.get("companyName", ""), j.get("companySlug", ""))
                if len(jobs) < 100:
                    break
    found.pop("", None)
    return found


def main():
    known = {s.strip().lower() for s in WATCHLIST.read_text().split() if s.strip()}
    comps = companies()
    cand = set()
    for name, slug in comps.items():
        cand |= variants(name, slug)
    cand = sorted(c for c in cand if c not in known)
    print(f"{len(comps)} companies hiring in the candidate's country/worldwide, {len(cand)} new slug candidates", flush=True)
    with ThreadPoolExecutor(16) as ex:
        results = list(ex.map(scan_slug, cand))
    live = [(s, f, len(j)) for s, f, j in results if f and j]
    for s, f, n in sorted(live):
        print(f"{s}: {','.join(f)} ({n} jobs)")
    if live:
        with open(WATCHLIST, "a", encoding="utf-8") as fh:
            fh.write("\n# discovered " + __import__("datetime").date.today().isoformat() + "\n")
            fh.write("\n".join(s for s, _, _ in sorted(live)) + "\n")
    print(f"added {len(live)} live boards to the watchlist")


if __name__ == "__main__":
    main()
