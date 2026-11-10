"""Scan company job-board feeds (Greenhouse, Lever, Ashby, Workable and others) for remote roles
that match the candidate's target titles (config/search-profiles.yaml) and mention the candidate's country,
region or worldwide eligibility.

Usage: python scripts/scan_jobs.py [--max-age DAYS] [--all]
Keeps only postings first published / updated within --max-age days (default 14) so the candidate
applies while a role is still being reviewed. Postings already listed in jobs/_scans/seen.json
are marked "new": false and left out of the printed shortlist unless --all is passed.
Writes jobs/_scans/<timestamp>.json and prints a shortlist.
Nothing is submitted anywhere. This only reads public feeds.
"""
import json
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WATCHLIST = ROOT / "scripts" / "watchlist.txt"
OUT_DIR = ROOT / "jobs" / "_scans"

sys.path.insert(0, str(Path(__file__).resolve().parent))
import profile_loader  # noqa: E402

PROFILE = profile_loader.require_onboarded()
TITLE_KEEP = profile_loader.title_keep(PROFILE)      # target titles come from the profile's role families
TITLE_DROP = profile_loader.title_drop(PROFILE)
LOC_STRONG = profile_loader.location_regex(PROFILE)  # candidate's country and region words, plus worldwide words
LOC_REMOTE = re.compile(r"remote", re.I)
RESTRICT = re.compile(
    r"(must (be )?(located|reside|live|based) in|must be (a )?(us|u\.s\.|united states) |"
    r"authorized to work in the (us|united states)|us[- ]only|u\.s\.[- ]only|"
    r"eligible to work in the (us|united states|uk|eu)|right to work in the (uk|eu)|"
    r"must be (located|based) in the (us|united states)|within (the )?(us|united states) time)",
    re.I,
)


def get(url, timeout=20, raw=False):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 job-scan"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read().decode("utf-8", "replace")
    return body if raw else json.loads(body)


def greenhouse(slug):
    d = get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs")
    for j in d.get("jobs", []):
        yield {
            "ats": "greenhouse", "company": slug, "title": j["title"],
            "location": (j.get("location") or {}).get("name", ""),
            "url": j["absolute_url"], "updated": j.get("updated_at", ""),
            "id": j["id"],
        }


def lever(slug):
    d = get(f"https://api.lever.co/v0/postings/{slug}?mode=json")
    for j in d:
        cats = j.get("categories") or {}
        loc = ", ".join(x for x in [cats.get("location", "")] + (cats.get("allLocations") or []) if x)
        yield {
            "ats": "lever", "company": slug, "title": j["text"],
            "location": f"{loc} | {j.get('workplaceType', '')} | {j.get('country', '')}",
            "url": j["hostedUrl"], "updated": str(j.get("createdAt", "")),
            "desc": j.get("descriptionPlain", ""),
        }


def ashby(slug):
    d = get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}")
    for j in d.get("jobs", []):
        secondary = ", ".join(s.get("location", "") for s in j.get("secondaryLocations", []) or [])
        loc = f"{j.get('location', '')} {secondary} | remote={j.get('isRemote')} | {j.get('workplaceType', '')}"
        yield {
            "ats": "ashby", "company": slug, "title": j["title"], "location": loc,
            "url": j.get("jobUrl", ""), "updated": j.get("publishedAt", ""),
            "desc": j.get("descriptionPlain", ""),
        }


def workable(slug):
    d = get(f"https://apply.workable.com/api/v1/widget/accounts/{slug}")
    seen = {}
    for j in d.get("jobs", []):
        key = j.get("url")
        e = seen.setdefault(key, {
            "ats": "workable", "company": slug, "title": j["title"], "countries": [],
            "url": key, "updated": j.get("published_on", ""), "remote": j.get("telecommuting"),
        })
        e["countries"].append(j.get("country", ""))
    for e in seen.values():
        e["location"] = f"remote={e.pop('remote')} | " + ", ".join(sorted(set(e.pop("countries"))))
        yield e


def smartrecruiters(slug):
    off = 0
    while off < 500:
        d = get(f"https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=100&offset={off}")
        items = d.get("content", [])
        for j in items:
            loc = j.get("location") or {}
            where = ", ".join(x for x in [loc.get("city", ""), loc.get("region", ""), loc.get("country", "")] if x)
            yield {
                "ats": "smartrecruiters", "company": slug, "title": j.get("name", ""),
                "location": f"{where} | remote={loc.get('remote')}", "url": f"https://jobs.smartrecruiters.com/{slug}/{j.get('id')}",
                "updated": j.get("releasedDate", ""),
            }
        if len(items) < 100:
            break
        off += 100


def breezy(slug):
    for j in get(f"https://{slug}.breezy.hr/json"):
        loc = j.get("location") or {}
        country = (loc.get("country") or {}).get("name", "")
        yield {
            "ats": "breezy", "company": slug, "title": j.get("name", ""),
            "location": f"{loc.get('name', '')} {country} | remote={loc.get('is_remote')}",
            "url": j.get("url", ""), "updated": j.get("published_date", ""),
        }


def recruitee(slug):
    for j in get(f"https://{slug}.recruitee.com/api/offers/").get("offers", []):
        yield {
            "ats": "recruitee", "company": slug, "title": j.get("title", ""),
            "location": f"{j.get('location', '')} {j.get('country', '')} | remote={j.get('remote')}",
            "url": j.get("careers_url", ""), "updated": j.get("published_at", ""),
            "desc": html_text(j.get("description", "")),
        }


def teamtailor(slug):
    import xml.etree.ElementTree as ET
    root = ET.fromstring(get(f"https://{slug}.teamtailor.com/jobs.rss", raw=True))
    for it in root.iter("item"):
        yield {
            "ats": "teamtailor", "company": slug, "title": it.findtext("title", ""),
            "location": (it.findtext("{*}locations") or "") + " " + (it.findtext("remoteStatus") or it.findtext("{*}remoteStatus") or ""),
            "url": it.findtext("link", ""), "updated": it.findtext("pubDate", ""),
            "desc": html_text(it.findtext("description", "")),
        }


def personio(slug):
    import xml.etree.ElementTree as ET
    root = ET.fromstring(get(f"https://{slug}.jobs.personio.de/xml?language=en", raw=True))
    for p in root.iter("position"):
        yield {
            "ats": "personio", "company": slug, "title": p.findtext("name", ""),
            "location": p.findtext("office", ""), "url": f"https://{slug}.jobs.personio.de/job/{p.findtext('id', '')}",
            "updated": p.findtext("createdAt", ""),
        }


FETCHERS = [greenhouse, lever, ashby, workable, smartrecruiters, breezy, recruitee, teamtailor, personio]


def scan_slug(slug):
    jobs, found = [], []
    for f in FETCHERS:
        try:
            got = list(f(slug))
        except Exception:
            continue
        if got:
            found.append(f.__name__)
            jobs.extend(got)
    return slug, found, jobs


NOISE = re.compile(r"remote|home|based|friendly|travel|required|hybrid|onsite|on-site|none|true|false|[|,;()\-=]|\s", re.I)


def classify(job):
    loc = job["location"]
    if LOC_STRONG.search(loc):
        return "strong"
    if LOC_REMOTE.search(loc) and "remote=False" not in loc and len(NOISE.sub("", loc)) < 3:
        return "generic-remote"
    return None


def parse_date(v):
    """Return an aware datetime from ISO strings or epoch millis, else None."""
    if not v:
        return None
    v = str(v).strip()
    try:
        if v.isdigit():
            return datetime.fromtimestamp(int(v) / (1000 if len(v) > 10 else 1), timezone.utc)
        d = datetime.fromisoformat(v.replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def age_days(j):
    d = parse_date(j.get("posted")) or parse_date(j.get("updated"))
    return (datetime.now(timezone.utc) - d).days if d else None


def html_text(h):
    import html
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(h or "")))


def add_detail(j):
    desc = j.get("desc", "")
    if j["ats"] == "greenhouse" and not desc:
        try:
            d = get(f"https://boards-api.greenhouse.io/v1/boards/{j['company']}/jobs/{j['id']}")
            desc = html_text(d.get("content", ""))
            j["posted"] = d.get("first_published", "")
        except Exception:
            pass
    j["desc"] = desc[:20000]
    m = RESTRICT.search(desc)
    j["restriction"] = m.group(0) if m else None
    onsite = re.search(r"(hybrid|on-?site|in[- ]office|presencial|h[ií]brido|days? (a|per) week in)", desc, re.I)
    j["onsite_hint"] = onsite.group(0) if onsite else None
    yrs = re.findall(r"(\d{1,2})\s*\+?\s*(?:-\s*\d{1,2}\s*)?(?:years|anos)", desc, re.I)
    j["years_mentions"] = sorted(set(yrs), key=int)[:4]
    sal = re.search(r"(?:\$|USD|EUR|€|£|R\$)\s?\d[\d.,]*\s?[kK]?\s*(?:-|–|to|and)\s*(?:\$|USD|EUR|€|£|R\$)?\s?\d[\d.,]*\s?[kK]?", desc)
    j["pay"] = sal.group(0) if sal else None
    return j


def main():
    max_age = int(sys.argv[sys.argv.index("--max-age") + 1]) if "--max-age" in sys.argv else 14
    show_all = "--all" in sys.argv
    slugs = [s.strip() for s in WATCHLIST.read_text().split() if s.strip() and not s.startswith("#")]
    slugs = sorted(set(slugs))
    t0 = time.time()
    with ThreadPoolExecutor(16) as ex:
        results = list(ex.map(scan_slug, slugs))
    boards = {s: f for s, f, _ in results if f}
    all_jobs = [j for _, _, js in results for j in js]
    hits = []
    for j in all_jobs:
        if TITLE_DROP.search(j["title"]) or not TITLE_KEEP.search(j["title"] + " "):
            continue
        c = classify(j)
        if not c:
            continue
        j["match"] = c
        a = age_days(j)
        if a is not None and a > max_age:
            continue
        hits.append(j)
    with ThreadPoolExecutor(16) as ex:
        hits = list(ex.map(add_detail, hits))
    for j in hits:
        j["age_days"] = age_days(j)
    # Greenhouse only gives updated_at in the list, so re-check the real first_published date.
    hits = [j for j in hits if j["age_days"] is None or j["age_days"] <= max_age]
    seen_path = OUT_DIR / "seen.json"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    seen = json.loads(seen_path.read_text()) if seen_path.exists() else {}
    for j in hits:
        j["new"] = j["url"] not in seen
        seen.setdefault(j["url"], datetime.now().strftime("%Y-%m-%d"))
    seen_path.write_text(json.dumps(seen, indent=1))
    hits.sort(key=lambda j: (not j["new"], j["match"] != "strong", j["age_days"] if j["age_days"] is not None else 999))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    (OUT_DIR / f"{stamp}.json").write_text(json.dumps(
        {"boards": boards, "total_jobs": len(all_jobs), "hits": hits}, indent=1))
    print(f"{len(slugs)} slugs tried, {len(boards)} live boards, {len(all_jobs)} jobs, "
          f"{len(hits)} title+location hits, {time.time() - t0:.0f}s")
    for j in hits:
        if not j["new"] and not show_all:
            continue
        flags = []
        if j["restriction"]:
            flags.append("RESTRICT:" + j["restriction"])
        if j["onsite_hint"]:
            flags.append("ONSITE?:" + j["onsite_hint"])
        print(f"[{j['match']}] age={j['age_days']}d {j['company']} | {j['title']} | {j['location'][:70]} | yrs={j['years_mentions']} "
              f"| pay={j['pay']} | {' '.join(flags)} | {j['url']}")


if __name__ == "__main__":
    main()
