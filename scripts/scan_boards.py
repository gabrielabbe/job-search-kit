"""Scan public remote-job aggregator APIs/feeds (RemoteOK, Remotive, Jobicy, Himalayas, We Work Remotely and
regional boards) for the target titles in config/search-profiles.yaml that are open to the candidate's country or worldwide.

Usage: python scripts/scan_boards.py [--max-age DAYS] [--all]
Complements scan_jobs.py (company career pages). Writes jobs/_scans/boards_<timestamp>.json.
Only reads public feeds. Nothing is submitted. Already-seen URLs (jobs/_scans/seen.json) are hidden unless --all.
"""
import html
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "jobs" / "_scans"

sys.path.insert(0, str(Path(__file__).resolve().parent))
import profile_loader  # noqa: E402

PROFILE = profile_loader.require_onboarded()
TITLE_KEEP = profile_loader.title_keep(PROFILE)
TITLE_DROP = profile_loader.title_drop(PROFILE)
ELIGIBLE = profile_loader.location_regex(PROFILE)
RESTRICT = re.compile(
    r"(must (be )?(located|reside|live|based) in|authorized to work in the (us|united states)|us[- ]only|u\.s\.[- ]only|"
    r"eligible to work in the (us|united states|uk|eu)|right to work in the (uk|eu)|within (the )?(us|united states) time)", re.I)


def get(url, as_json=True, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 job-scan"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read().decode("utf-8", "replace")
    return json.loads(raw) if as_json else raw


def text(h):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(h or ""))).strip()


def to_dt(v):
    if not v:
        return None
    try:
        if isinstance(v, (int, float)) or str(v).isdigit():
            v = int(v)
            return datetime.fromtimestamp(v / (1000 if v > 10**11 else 1), timezone.utc)
        s = str(v)
        try:
            return parsedate_to_datetime(s)
        except (TypeError, ValueError):
            d = datetime.fromisoformat(s.replace("Z", "+00:00"))
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def remoteok():
    for j in get("https://remoteok.com/api")[1:]:
        yield dict(src="remoteok", title=j.get("position", ""), company=j.get("company", ""), location=j.get("location", "") or "Worldwide",
                   url=j.get("url", ""), posted=j.get("date") or j.get("epoch"), desc=text(j.get("description")),
                   pay=f"{j.get('salary_min')}-{j.get('salary_max')}" if j.get("salary_min") else None)


def remotive():
    seen = set()
    for q in ["it manager", "head of it", "it operations", "martech", "marketing operations", "ai operations",
              "systems administrator", "it director", "revenue operations", "automation"]:
        try:
            d = get("https://remotive.com/api/remote-jobs?limit=100&search=" + urllib.request.quote(q))
        except Exception:
            continue
        for j in d.get("jobs", []):
            if j["url"] in seen:
                continue
            seen.add(j["url"])
            yield dict(src="remotive", title=j["title"], company=j["company_name"], location=j.get("candidate_required_location", ""),
                       url=j["url"], posted=j.get("publication_date"), desc=text(j.get("description")), pay=j.get("salary") or None)


def jobicy():
    for geo in profile_loader.jobicy_geos(PROFILE):
        try:
            d = get("https://jobicy.com/api/v2/remote-jobs?count=100" + (f"&geo={geo}" if geo else ""))
        except Exception:
            continue
        for j in d.get("jobs", []):
            yield dict(src="jobicy", title=j.get("jobTitle", ""), company=j.get("companyName", ""), location=str(j.get("jobGeo", "")),
                       url=j.get("url", ""), posted=j.get("pubDate"), desc=text(j.get("jobDescription")),
                       pay=(f"{j.get('salaryMin')}-{j.get('salaryMax')} {j.get('salaryCurrency', '')}" if j.get("salaryMin") else None))


HIMALAYAS_QUERIES = profile_loader.board_queries(PROFILE)


def himalayas():
    """Himalayas has 100k+ jobs and sorts by newest, so scanning the first pages misses almost everything.
    Its search endpoint filters server-side by country, so ask for the candidate's country and for worldwide per query."""
    seen = set()
    for q in HIMALAYAS_QUERIES:
        for geo in (f"country={urllib.request.quote(profile_loader.country_name(PROFILE))}", "worldwide=true"):
            for off in (0, 100):
                try:
                    d = get(f"https://himalayas.app/jobs/api/search?q={urllib.request.quote(q)}&{geo}&limit=100&offset={off}")
                except Exception:
                    break
                jobs = d.get("jobs", [])
                for j in jobs:
                    key = j.get("guid") or j.get("applicationLink")
                    if key in seen:
                        continue
                    seen.add(key)
                    locs = ", ".join(j.get("locationRestrictions") or []) or "Worldwide"
                    yield dict(src="himalayas", title=j.get("title", ""), company=j.get("companyName", ""), location=locs,
                               url=j.get("applicationLink") or j.get("guid", ""), posted=j.get("pubDate"), desc=text(j.get("description")),
                               type=j.get("employmentType", ""),
                               pay=(f"{j.get('minSalary')}-{j.get('maxSalary')} {j.get('currency', '')}" if j.get("minSalary") else None))
                if len(jobs) < 100:
                    break


def wwr():
    for cat in ["remote-devops-sysadmin-jobs", "remote-management-and-finance-jobs", "remote-all-other-remote-jobs",
                "remote-sales-and-marketing-jobs", "remote-business-exec-management-jobs"]:
        try:
            root = ET.fromstring(get(f"https://weworkremotely.com/categories/{cat}.rss", as_json=False))
        except Exception:
            continue
        for it in root.iter("item"):
            title = it.findtext("title", "")
            co, _, t = title.partition(": ")
            yield dict(src="weworkremotely", title=t or title, company=co if t else "",
                       location=it.findtext("region", "") or it.findtext("{*}region", "") or "Remote",
                       url=it.findtext("link", ""), posted=it.findtext("pubDate"), desc=text(it.findtext("description")), pay=None)


GUPY_QUERIES = ["gerente de TI", "head de TI", "coordenador de TI", "lider de TI", "gerente de tecnologia", "IT manager",
                "IT operations", "gerente de operacoes de TI", "gerente de infraestrutura", "coordenador de infraestrutura",
                "seguranca da informacao gerente", "martech", "marketing operations", "operacoes de marketing", "automacao",
                "inteligencia artificial", "gerente de projetos de TI", "analista de BI", "gerente de dados", "salesforce",
                "service desk coordenador", "gerente de sistemas", "customer success operations", "chief of staff"]


def gupy():
    """Gupy hosts the career pages of thousands of Brazilian employers (used only when the profile's country is Brazil); its public search is keyed by keyword."""
    seen = set()
    for q in GUPY_QUERIES:
        for off in (0, 100):
            try:
                d = get(f"https://portal.gupy.io/api/job-search/jobs?jobName={urllib.request.quote(q)}&workplaceType=remote&limit=100&offset={off}")
            except Exception:
                break
            rows = d.get("data", [])
            for j in rows:
                if j.get("jobUrl") in seen or "confidencial" in (j.get("careerPageName") or "").lower():
                    continue
                seen.add(j.get("jobUrl"))
                yield dict(src="gupy", title=j.get("name", ""), company=j.get("careerPageName", ""),
                           location=f"Brazil ({j.get('state', '')}) {j.get('workplaceType', '')}", url=j.get("jobUrl", ""),
                           posted=j.get("publishedDate"), desc=text(j.get("description")), type=j.get("type", ""), pay=None)
            if len(rows) < 100:
                break


def getonbrd():
    """Get on Board is a LatAm-focused remote tech board."""
    for cat in ["operations-management", "sysadmin-devops-qa", "data-science-analytics", "machine-learning-ai",
                "cybersecurity", "technical-support", "digital-marketing", "innovation-agile", "education-coaching"]:
        for page in (1, 2):
            try:
                d = get(f"https://www.getonbrd.com/api/v0/categories/{cat}/jobs?per_page=100&page={page}&expand[]=company")
            except Exception:
                break
            for j in d.get("data", []):
                a = j.get("attributes", {})
                remote = a.get("remote_modality") in ("fully_remote", "remote_local", "remote") or a.get("remote")
                if not remote:
                    continue
                countries = ", ".join(a.get("countries") or []) or "LATAM"
                co = ((a.get("company") or {}).get("data") or {}).get("attributes", {}).get("name", "")
                yield dict(src="getonbrd", title=a.get("title", ""), company=co, location=f"LATAM {countries}",
                           url=(j.get("links") or {}).get("public_url", ""), posted=a.get("published_at"),
                           desc=text(a.get("description")), pay=(f"{a.get('min_salary')}-{a.get('max_salary')} USD" if a.get("min_salary") else None))


def workingnomads():
    for j in get("https://www.workingnomads.com/api/exposed_jobs/"):
        yield dict(src="workingnomads", title=j.get("title", ""), company=j.get("company_name", ""), location=j.get("location") or "Worldwide",
                   url=j.get("url", ""), posted=j.get("pub_date"), desc=text(j.get("description")), pay=None)


EU_FEEDS = {"germantechjobs": "https://germantechjobs.de/rss", "berlinstartupjobs": "https://berlinstartupjobs.com/feed/"}
EU_REMOTE_OK = re.compile(r"(fully remote|100% remote|remote[- ]first|work from anywhere|remote \(?(worldwide|global|europe|emea|eu)|anywhere in the world)", re.I)


def european_rss():
    """GermanTechJobs and Berlin Startup Jobs publish public RSS feeds (robots.txt allows them). Most roles are on-site
    in Germany and need EU work authorization, so only postings that say fully remote or worldwide are kept."""
    for name, url in EU_FEEDS.items():
        try:
            root = ET.fromstring(get(url, as_json=False))
        except Exception:
            continue
        for it in root.iter("item"):
            body = text(it.findtext("description", "") + " " + (it.findtext("{*}encoded") or ""))
            title = it.findtext("title", "")
            loc = "Worldwide" if EU_REMOTE_OK.search(body + " " + title) else "Germany (on-site or EU only)"
            co = title.rpartition("//")[2].strip() if "//" in title else ""
            yield dict(src=name, title=title.partition("//")[0].strip(), company=co, location=loc, url=it.findtext("link", ""),
                       posted=it.findtext("pubDate"), desc=body, pay=None)


def run(f):
    try:
        return list(f())
    except Exception as e:
        print(f"[warn] {f.__name__}: {e}", file=sys.stderr)
        return []


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    max_age = int(sys.argv[sys.argv.index("--max-age") + 1]) if "--max-age" in sys.argv else 21
    show_all = "--all" in sys.argv
    with ThreadPoolExecutor(8) as ex:
        feeds = [remoteok, remotive, jobicy, himalayas, wwr, workingnomads]
        local = {"gupy": gupy, "getonbrd": getonbrd, "european_rss": european_rss}
        feeds += [local[n] for n in profile_loader.local_feeds(PROFILE) if n in local]
        results = list(ex.map(run, feeds))
    jobs = [j for r in results for j in r]
    counts = {}
    for j in jobs:
        counts[j["src"]] = counts.get(j["src"], 0) + 1
    now = datetime.now(timezone.utc)
    hits, dedupe = [], set()
    for j in jobs:
        if not j["url"] or j["url"] in dedupe:
            continue
        dedupe.add(j["url"])
        if TITLE_DROP.search(j["title"]) or not TITLE_KEEP.search(j["title"]):
            continue
        loc = (j["location"] or "").strip()
        # Only keep postings whose location names the candidate's country or region, or worldwide, or says nothing.
        if loc and not ELIGIBLE.search(loc):
            continue
        d = to_dt(j["posted"])
        j["age_days"] = (now - d).days if d else None
        if j["age_days"] is not None and j["age_days"] > max_age:
            continue
        m = RESTRICT.search(j["desc"])
        j["restriction"] = m.group(0) if m else None
        j["desc"] = j["desc"][:15000]
        hits.append(j)
    seen_path = OUT_DIR / "seen.json"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    seen = json.loads(seen_path.read_text()) if seen_path.exists() else {}
    for j in hits:
        j["new"] = j["url"] not in seen
        seen.setdefault(j["url"], datetime.now().strftime("%Y-%m-%d"))
    seen_path.write_text(json.dumps(seen, indent=1))
    hits.sort(key=lambda j: (not j["new"], j["age_days"] if j["age_days"] is not None else 999))
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    (OUT_DIR / f"boards_{stamp}.json").write_text(json.dumps({"counts": counts, "hits": hits}, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"feeds: {counts} | {len(hits)} title+location hits")
    for j in hits:
        if not j["new"] and not show_all:
            continue
        flag = ("RESTRICT:" + j["restriction"]) if j["restriction"] else ""
        print(f"[{j['src']}] age={j['age_days']}d {j['company']} | {j['title']} | {j['location'][:60]} | {j.get('type', '')} | pay={j['pay']} | {flag} | {j['url']}")


if __name__ == "__main__":
    main()
