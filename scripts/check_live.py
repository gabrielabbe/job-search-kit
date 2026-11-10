"""Check whether job postings are still open before spending drafting time on them.

Usage: python scripts/check_live.py <url> [<url> ...]
Prints OPEN / CLOSED / UNKNOWN per URL. Uses the ATS APIs where possible (Greenhouse, Lever, Ashby, Workable)
and falls back to reading the page for 404s and "no longer accepting" wording. Read-only.
Idea borrowed from career-ops' liveness check: never evaluate a dead posting.
"""
import json
import re
import sys
import urllib.error
import urllib.request

DEAD = re.compile(r"(no longer (accepting|available)|position (has been|is) (filled|closed)|job (not found|has expired|is closed)|"
                  r"this (job|position|posting) (is|has been) (closed|removed|filled)|vaga (encerrada|expirada)|(job|posting|listing) (has )?expired)", re.I)


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 job-scan"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception:
        return 0, ""


def check(url):
    m = re.search(r"greenhouse\.io/([\w.-]+)/jobs/(\d+)", url) or re.search(r"gh_jid=(\d+)", url)
    if m and "greenhouse.io" in url:
        code, _ = fetch(f"https://boards-api.greenhouse.io/v1/boards/{m.group(1)}/jobs/{m.group(2)}")
        return "OPEN" if code == 200 else "CLOSED" if code == 404 else "UNKNOWN"
    m = re.search(r"lever\.co/([\w.-]+)/([0-9a-f-]{36})", url)
    if m:
        code, _ = fetch(f"https://api.lever.co/v0/postings/{m.group(1)}/{m.group(2)}")
        return "OPEN" if code == 200 else "CLOSED" if code == 404 else "UNKNOWN"
    m = re.search(r"ashbyhq\.com/([\w.-]+)/([0-9a-f-]{36})", url)
    if m:
        code, body = fetch(f"https://api.ashbyhq.com/posting-api/job-board/{m.group(1)}")
        if code != 200:
            return "UNKNOWN"
        ids = {j.get("id") for j in json.loads(body).get("jobs", [])}
        return "OPEN" if m.group(2) in ids else "CLOSED"
    code, body = fetch(url)
    if code in (404, 410):
        return "CLOSED"
    if code == 200:
        # script payloads (Next.js) can embed a "closed" template that is not rendered for open roles
        visible = re.sub(r"(?is)<script.*?</script>", " ", body)
        return "CLOSED" if DEAD.search(visible[:200000]) else "OPEN"
    return "UNKNOWN"


if __name__ == "__main__":
    for u in sys.argv[1:]:
        print(check(u), u)
