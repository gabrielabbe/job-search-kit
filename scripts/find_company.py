"""Quick company lookup: find a company's official job boards and list the roles that fit the candidate.

Usage: python scripts/find_company.py "Supabase" ["Deel" ...] [--all] [--add]
Guesses ATS slugs from the company name, tries every fetcher in scan_jobs.py (Greenhouse, Lever, Ashby, Workable,
SmartRecruiters, Breezy, Recruitee, Teamtailor, Personio), then prints jobs whose title matches the profile
and whose location is the candidate's country/region/worldwide/remote (or every job with --all). --add appends the live slugs to
scripts/watchlist.txt so the scheduled scans cover the company from then on. Read-only.
"""
import re
import sys
from concurrent.futures import ThreadPoolExecutor

import scan_jobs
from scan_jobs import TITLE_DROP, TITLE_KEEP, WATCHLIST, classify, scan_slug

SUFFIX = re.compile(r"\b(inc|llc|ltd|limited|gmbh|co|corp|corporation|company|sa|ag|plc|group|the)\b\.?", re.I)


def variants(name):
    base = SUFFIX.sub("", re.sub(r"[^\w\s-]", "", name.lower())).strip()
    parts = base.split()
    out = {base.replace(" ", ""), base.replace(" ", "-"), parts[0] if parts else "", "".join(parts[:2]),
           base.replace(" ", "") + "hq", base.replace(" ", "") + "careers", base.replace(" ", "") + "inc",
           base.replace(" ", "") + "global", "get" + base.replace(" ", ""), "join" + base.replace(" ", "")}
    return sorted(v for v in out if 2 < len(v) < 40)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    show_all, add = "--all" in sys.argv, "--add" in sys.argv
    if not args:
        sys.exit(__doc__)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    for name in args:
        print(f"\n=== {name} ===")
        with ThreadPoolExecutor(12) as ex:
            res = list(ex.map(scan_slug, variants(name)))
        live = [(s, f, j) for s, f, j in res if f and j]
        if not live:
            print("no public ATS board found under the usual slugs (the company may use Workday, a custom site or an unlisted ATS)")
            continue
        for slug, found, jobs in live:
            print(f"board: {slug} on {', '.join(found)}: {len(jobs)} open jobs")
            shown = 0
            for j in jobs:
                fit = (not TITLE_DROP.search(j["title"])) and TITLE_KEEP.search(j["title"] + " ")
                loc = classify(j)
                if show_all or (fit and loc):
                    shown += 1
                    print(f"  [{loc or '-'}] {j['title']} | {j['location'][:70]} | {j['url']}")
            if not shown:
                print("  no roles matching the profile and an eligible location right now")
            if add:
                known = {s.strip().lower() for s in WATCHLIST.read_text().split() if s.strip()}
                if slug not in known:
                    with open(WATCHLIST, "a", encoding="utf-8") as fh:
                        fh.write(slug + "\n")
                    print(f"  added {slug} to the watchlist")


if __name__ == "__main__":
    main()
