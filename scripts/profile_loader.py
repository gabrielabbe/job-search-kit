"""Read the candidate's search profile (config/search-profiles.yaml) for the scanner scripts.

Everything a scanner used to hard-code (target titles, excluded titles, which locations count as eligible, which
country to ask a job board for) now comes from the profile that the onboarding interview fills in.
A scanner refuses to run until the profile is onboarded, so a fresh clone never scans with someone else's targets.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "search-profiles.yaml"

# Words that mean "open to people anywhere". Added to every profile's own location terms.
WORLDWIDE_WORDS = ["worldwide", "world-wide", "anywhere", "global", "work from anywhere", "international"]

# Country-code -> feeds that only make sense for that region.
LOCAL_FEEDS = {
    "BR": ["gupy", "getonbrd"],
    "MX": ["getonbrd"], "AR": ["getonbrd"], "CL": ["getonbrd"], "CO": ["getonbrd"], "PE": ["getonbrd"], "UY": ["getonbrd"],
}
EUROPE = {"DE", "FR", "ES", "PT", "IT", "NL", "BE", "AT", "CH", "SE", "NO", "DK", "FI", "PL", "IE", "CZ", "RO", "BG", "GR", "HU"}

# Titles nobody in a professional search wants, whatever the targets are. Profile terms add to this.
ALWAYS_DROP = ["intern", "internship", "junior", "recruiter", "sales development", "account executive"]


def _active_name(data: dict) -> str:
    return data.get("active_profile") or next(iter(data.get("profiles", {})), "default")


def load(name: str | None = None) -> dict:
    if not CONFIG.exists():  # first run: start from the blank template
        import shutil
        shutil.copyfile(ROOT / "templates" / "search-profiles.yaml", CONFIG)
    data = yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}
    prof = (data.get("profiles") or {}).get(name or _active_name(data)) or {}
    return prof


def is_onboarded(prof: dict | None = None) -> bool:
    prof = prof if prof is not None else load()
    return bool(prof.get("onboarded")) and bool(prof.get("candidate_country"))


def require_onboarded() -> dict:
    """Return the profile, or stop the script with a clear message when onboarding has not happened yet."""
    prof = load()
    if not is_onboarded(prof):
        sys.exit("The search profile is not set up yet. Open this folder in Claude Code and say hello: "
                 "it starts the onboarding interview that fills in config/search-profiles.yaml.")
    return prof


def _alt(words: list[str]) -> str:
    return "|".join(re.escape(w.strip()) for w in words if w and w.strip())


def target_terms(prof: dict) -> list[str]:
    terms = []
    for fam in (prof.get("role_families") or {}).values():
        terms += fam.get("terms", [])
    return terms + list(prof.get("extra_title_terms") or [])


def title_keep(prof: dict) -> re.Pattern:
    terms = target_terms(prof)
    return re.compile(r"(" + _alt(terms) + r")" if terms else r"$^", re.I)


def title_drop(prof: dict) -> re.Pattern:
    terms = ALWAYS_DROP + list(prof.get("exclude_title_terms") or [])
    return re.compile(r"\b(" + _alt(terms) + r")\b", re.I)


def location_terms(prof: dict) -> list[str]:
    return list(prof.get("location_terms") or []) + WORLDWIDE_WORDS


def location_regex(prof: dict) -> re.Pattern:
    return re.compile(r"(" + _alt(location_terms(prof)) + r")", re.I)


def country_name(prof: dict) -> str:
    return prof.get("country_name") or prof.get("candidate_country") or ""


def board_queries(prof: dict) -> list[str]:
    """Search phrases for boards that need them (Himalayas). Own list, else the first terms of each role family."""
    own = prof.get("board_queries")
    if own:
        return list(own)
    out = []
    for fam in (prof.get("role_families") or {}).values():
        out += fam.get("terms", [])[:4]
    return list(dict.fromkeys(out))[:45]


def jobicy_geos(prof: dict) -> list[str]:
    own = prof.get("jobicy_geos")
    if own:
        return list(own)
    geos = ["anywhere", "worldwide", ""]
    cn = country_name(prof).lower().replace(" ", "-")
    if cn:
        geos.insert(0, cn)
    return geos


def local_feeds(prof: dict) -> list[str]:
    own = prof.get("local_feeds")
    if own is not None:
        return list(own)
    cc = prof.get("candidate_country", "")
    feeds = list(LOCAL_FEEDS.get(cc, []))
    if cc in EUROPE:
        feeds.append("european_rss")
    return feeds
