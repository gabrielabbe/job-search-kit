"""Config loading and the watchlist import (company registry with provenance)."""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from .models import Company

ROOT = Path(__file__).resolve().parents[2]
PROVIDERS = ("greenhouse", "lever", "ashby", "smartrecruiters")


def load_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_profile(name: str | None = None, path: Path | None = None) -> dict:
    """The candidate's search profile. With no name, the file's `active_profile` (else its first profile) is used."""
    cfg = path or ROOT / "config" / "search-profiles.yaml"
    if not cfg.exists() and path is None:  # first run: start from the blank template
        cfg = ROOT / "templates" / "search-profiles.yaml"
    data = load_yaml(cfg)
    profiles = data.get("profiles") or {}
    name = name or data.get("active_profile") or next(iter(profiles), "default")
    try:
        prof = profiles[name]
    except KeyError:
        raise KeyError(f"profile '{name}' not found in search-profiles.yaml") from None
    if prof.get("candidate_country") and (prof.get("country_terms") or prof.get("region_terms")):
        from . import eligibility
        eligibility.register(prof["candidate_country"], prof.get("country_terms"), prof.get("region_terms"))
    return prof


def load_sources(path: Path | None = None) -> dict:
    return load_yaml(path or ROOT / "config" / "sources.yaml")


def read_watchlist(path: Path | None = None) -> list[str]:
    """Slugs from scripts/watchlist.txt: one per line, '#' comments. Order and duplicates are normalised."""
    p = path or ROOT / "scripts" / "watchlist.txt"
    seen, out = set(), []
    for line in p.read_text(encoding="utf-8").splitlines():
        # some lines hold several slugs separated by spaces or commas
        for s in re.split(r"[\s,]+", line.split("#", 1)[0].strip().lower()):
            if s and s not in seen:
                seen.add(s)
                out.append(s)
    return out


def companies_from_watchlist(path: Path | None = None, providers: tuple[str, ...] = PROVIDERS) -> list[Company]:
    """Each slug is registered once per provider with ats_confidence=unverified. A fetch that returns rows upgrades it.

    Slugs are not guessed: they are exactly the user's list. 404 on a provider just means 'not on that provider'.
    """
    out = []
    for slug in read_watchlist(path):
        for prov in providers:
            out.append(Company(name=slug, slug=slug, provider=prov, discovery_source="watchlist",
                               ats_confidence="unverified"))
    return out
