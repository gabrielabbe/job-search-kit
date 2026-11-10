"""Geographic eligibility for a candidate living in a given country (ISO code from the profile).

Classes (Agents/data-contracts.md Contract A):
  CONFIRMED_COUNTRY  the posting names the candidate's country and remote work
  CONFIRMED_REGION   the posting names a region that contains it (LATAM, Americas) and remote work
  CONFIRMED_GLOBAL   the posting says worldwide/anywhere and remote work, with no contradicting restriction
  UNVERIFIED         remote without any stated geography, or evidence that conflicts
  INELIGIBLE         hybrid/on-site, or only other countries/regions listed, or an explicit restriction

"Remote" alone never means worldwide. Every decision carries the matched text as evidence.
Known limits: US state codes (NY, CA) and unusual city names are not recognised; those fall to UNVERIFIED.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .models import (CONFIRMED_COUNTRY, CONFIRMED_GLOBAL, CONFIRMED_REGION, INELIGIBLE, UNVERIFIED,
                     JobPosting)

_NOT_NORTH = r"(?<!north )(?<!central )"
_LATAM = rf"latam|latin america|south america|{_NOT_NORTH}the americas|{_NOT_NORTH}americas"
_EUROPE = r"europe|emea|eu|european union|dach|nordics"
_EU_MEMBER_REGION = _EUROPE
# Built-in country words (the country, its largest cities) and the regions that contain it.
# Anything missing here can be added in the profile: country_terms / region_terms (regex alternations).
COUNTRY_TERMS = {
    "BR": r"brazil|brasil|são paulo|sao paulo|rio de janeiro|belo horizonte|curitiba|porto alegre",
    "MX": r"mexico|méxico|mexico city|guadalajara|monterrey",
    "AR": r"argentina|buenos aires|cordoba|córdoba",
    "CO": r"colombia|bogota|bogotá|medellin|medellín",
    "CL": r"chile|santiago",
    "PE": r"peru|perú|lima",
    "UY": r"uruguay|montevideo",
    "US": r"united states|usa|u\.s\.a?\.?|us",
    "CA": r"canada|toronto|vancouver|montreal",
    "GB": r"united kingdom|uk|england|scotland|wales|london",
    "IE": r"ireland|dublin",
    "DE": r"germany|deutschland|berlin|munich",
    "FR": r"france|paris",
    "ES": r"spain|españa|madrid|barcelona",
    "PT": r"portugal|lisbon|lisboa|porto",
    "IT": r"italy|italia|milan|rome",
    "NL": r"netherlands|amsterdam",
    "PL": r"poland|warsaw|krakow",
    "RO": r"romania|bucharest",
    "UA": r"ukraine|kyiv",
    "TR": r"turkey|türkiye|istanbul",
    "IN": r"india|bangalore|bengaluru|mumbai|delhi|hyderabad",
    "PH": r"philippines|manila",
    "PK": r"pakistan|karachi|lahore",
    "ID": r"indonesia|jakarta",
    "VN": r"vietnam",
    "NG": r"nigeria|lagos",
    "KE": r"kenya|nairobi",
    "ZA": r"south africa|cape town|johannesburg",
    "EG": r"egypt|cairo",
    "AU": r"australia|sydney|melbourne",
    "NZ": r"new zealand",
}
REGION_TERMS = {
    **{c: _LATAM for c in ("BR", "MX", "AR", "CO", "CL", "PE", "UY")},
    "US": rf"north america|{_NOT_NORTH}americas",
    "CA": rf"north america|{_NOT_NORTH}americas",
    **{c: _EUROPE for c in ("DE", "FR", "ES", "PT", "IT", "NL", "PL", "RO", "IE")},
    "GB": r"europe|emea",
    "UA": r"europe|emea",
    "TR": r"europe|emea",
    "IN": r"apac|asia",
    "PH": r"apac|asia",
    "PK": r"apac|asia",
    "ID": r"apac|asia",
    "VN": r"apac|asia",
    "AU": r"apac|anz",
    "NZ": r"apac|anz",
    "NG": r"africa|emea",
    "KE": r"africa|emea",
    "ZA": r"africa|emea",
    "EG": r"africa|emea|mena|middle east",
}


def register(code: str, country_terms: str | None = None, region_terms: str | None = None) -> None:
    """Add or override the location words for a country (called when a profile supplies its own)."""
    if country_terms:
        COUNTRY_TERMS[code] = country_terms
    if region_terms:
        REGION_TERMS[code] = region_terms


GLOBAL_TERMS = r"worldwide|world-wide|anywhere|global|globally"

_US_STATES = (
    "alabama|alaska|arizona|arkansas|california|colorado|connecticut|delaware|florida|georgia|hawaii|idaho|"
    "illinois|indiana|iowa|kansas|kentucky|louisiana|maine|maryland|massachusetts|michigan|minnesota|mississippi|"
    "missouri|montana|nebraska|nevada|new hampshire|new jersey|new mexico|new york|north carolina|north dakota|"
    "ohio|oklahoma|oregon|pennsylvania|rhode island|south carolina|south dakota|tennessee|texas|utah|vermont|"
    "virginia|washington|west virginia|wisconsin|wyoming"
)
_OTHER_PLACES = (
    r"united states|usa|u\.s\.a?\.?|us|canada|united kingdom|uk|england|scotland|wales|ireland|germany|france|"
    r"spain|portugal|italy|netherlands|belgium|switzerland|austria|sweden|norway|denmark|finland|poland|romania|"
    r"ukraine|czech republic|czechia|hungary|greece|turkey|israel|uae|united arab emirates|saudi arabia|india|"
    r"pakistan|bangladesh|vietnam|philippines|indonesia|singapore|japan|china|korea|australia|new zealand|"
    r"south africa|nigeria|kenya|egypt|mexico|argentina|colombia|chile|peru|uruguay|ecuador|costa rica|panama|"
    r"bulgaria|serbia|croatia|lithuania|latvia|estonia|emea|europe|eu|apac|asia|north america|anz|dach|nordics|"
    r"mena|africa|middle east|brazil|brasil|venezuela|bolivia|paraguay|cuba|dominican republic|guatemala|honduras|"
    r"el salvador|nicaragua|jamaica|thailand|malaysia|taiwan|sri lanka|nepal|morocco|tunisia|ghana|ethiopia|tanzania|"
    r"uganda|jordan|lebanon|qatar|kuwait|iceland|luxembourg|slovakia|slovenia|bosnia|albania|north macedonia|georgia|"
    r"armenia|azerbaijan|kazakhstan|belarus|russia|moldova|malta|cyprus|" + _US_STATES
)

_OTHER_CITIES = (
    r"london|new york|san francisco|los angeles|seattle|boston|austin|chicago|denver|atlanta|miami|toronto|vancouver|montreal|"
    r"berlin|munich|paris|madrid|barcelona|lisbon|porto|amsterdam|dublin|stockholm|copenhagen|oslo|helsinki|warsaw|krakow|"
    r"prague|vienna|zurich|milan|rome|sydney|melbourne|tokyo|bangalore|bengaluru|mumbai|delhi|hyderabad|mexico city|"
    r"buenos aires|bogota|bogotá|santiago|lima|tel aviv|dubai|cape town|johannesburg|nairobi|lagos|manila|jakarta|seoul|"
    r"hong kong|shanghai|beijing|kyiv|bucharest|budapest|athens|istanbul|são paulo|sao paulo|rio de janeiro|belo horizonte|"
    r"curitiba|porto alegre|brasilia|brasília"
)
# ISO country codes are matched case-sensitively as whole tokens ("London | GB"). 'IT' is omitted on purpose (IT = technology).
_OTHER_CODES = (r"GB|US|CA|DE|FR|ES|PT|IN|NL|SE|NO|DK|FI|PL|AU|NZ|JP|SG|MX|AR|CO|CL|PE|IE|CH|AT|BE|ZA|AE|IL|TR|RO|CZ|HU|GR|UA|"
                r"PH|ID|KR|CN|HK|EG|NG|KE|UY|EC|CR|PA")

# Explicit restrictions found in the description (they name the US, UK, EU, Canada or Europe).
_PLACE = r"(?:the )?(?:us|u\.s\.a?\.?|usa|united states|uk|united kingdom|eu|european union|canada|europe)"
RESTRICTIONS = [
    re.compile(rf"must\s+(?:be\s+)?(?:located|based|reside|resident|living|live)\s+(?:in|within)\s+{_PLACE}\b", re.I),
    re.compile(rf"(?:must|need to|required to)\s+(?:be\s+)?(?:legally\s+)?(?:authori[sz]ed|eligible|permitted)\s+to\s+work\s+in\s+{_PLACE}\b", re.I),
    re.compile(rf"(?:right|authori[sz]ation)\s+to\s+work\s+in\s+{_PLACE}\b", re.I),
    re.compile(rf"(?:remote|work)\s+(?:in|from)\s+{_PLACE}\s+(?:only|exclusively)", re.I),
    re.compile(rf"\b{_PLACE}[- ]only\b", re.I),
    re.compile(rf"(?:open|available)\s+(?:only\s+)?to\s+(?:residents|candidates|applicants)\s+(?:of|in|located in)\s+{_PLACE}\b", re.I),
]
REMOTE_IN_DESC = re.compile(r"\b(?:fully remote|100% remote|remote[- ]first|work(?:ing)? remotely|remote position|distributed team)\b", re.I)
TZ_PATTERNS = [
    re.compile(r"[^.\n]{0,80}\b(?:overlap|working hours|time ?zone)\b[^.\n]{0,80}\b(?:est|edt|pst|pdt|cet|cest|utc[+-]?\d*|gmt[+-]?\d*|central|eastern|pacific)\b[^.\n]{0,40}", re.I),
    re.compile(r"[^.\n]{0,60}\b\d+\s*(?:hours?|h)\s+(?:of\s+)?overlap[^.\n]{0,60}", re.I),
]


@dataclass
class Eligibility:
    remote_class: str
    eligible: str  # yes | no | unknown
    evidence: str
    time_zone_limits: str = ""

    @property
    def work_from_anywhere_verified(self) -> bool:
        return self.remote_class == CONFIRMED_GLOBAL


def _alt(pattern: str, text: str):
    return re.search(rf"(?<![\w-])(?:{pattern})(?![\w-])", text, re.I)


def _all_alt(pattern: str, text: str) -> list[str]:
    return sorted({m.group(0).lower() for m in re.finditer(rf"(?<![\w-])(?:{pattern})(?![\w-])", text, re.I)})


def _tz(desc: str) -> str:
    for p in TZ_PATTERNS:
        m = p.search(desc)
        if m:
            return re.sub(r"\s+", " ", m.group(0)).strip()[:160]
    return ""


def classify(job: JobPosting, candidate_country: str = "BR") -> Eligibility:
    loc_text = " | ".join([job.location_raw or ""] + list(job.extra_locations or []))
    desc = (job.description_text or "")[:8000]
    tz = _tz(desc)

    if job.remote_type in ("hybrid", "onsite"):
        return Eligibility(INELIGIBLE, "no", f"work model is {job.remote_type} (source field); fully remote is required", tz)

    restriction = None
    for rx in RESTRICTIONS:
        m = rx.search(desc)
        if m:
            restriction = re.sub(r"\s+", " ", m.group(0)).strip()
            break

    has_country = _alt(COUNTRY_TERMS.get(candidate_country, r"$^"), loc_text) or \
        (candidate_country == "BR" and re.search(r"(?<![\w])br(?![\w])", loc_text, re.I) and
         not re.search(r"\bbr\w", loc_text, re.I)) or \
        (candidate_country not in ("BR", "IT") and re.search(rf"(?<![A-Za-z]){candidate_country}(?![A-Za-z])", loc_text))
    has_region = _alt(REGION_TERMS.get(candidate_country, r"$^"), loc_text)
    has_global = _alt(GLOBAL_TERMS, loc_text)
    others = sorted(set(_all_alt(_OTHER_PLACES + "|" + _OTHER_CITIES, loc_text)) |
                    set(re.findall(rf"(?<![A-Za-z])(?:{_OTHER_CODES})(?![A-Za-z])", loc_text)))
    remote_evidence = (job.remote_type == "remote" or re.search(r"remote|work from anywhere|distributed", loc_text, re.I)
                       or REMOTE_IN_DESC.search(desc))

    def positive(cls: str, why: str) -> Eligibility:
        if not remote_evidence:
            return Eligibility(UNVERIFIED, "unknown", f"{why}, but remote work is not stated anywhere", tz)
        if restriction:
            return Eligibility(UNVERIFIED, "unknown",
                               f"conflict: {why}; description says \"{restriction}\"", tz)
        return Eligibility(cls, "yes", why, tz)

    if has_country:
        return positive(CONFIRMED_COUNTRY, f"location lists the candidate's country: \"{loc_text}\"")
    if has_region:
        return positive(CONFIRMED_REGION, f"location lists a region that includes the candidate's country: \"{loc_text}\"")
    if has_global:
        return positive(CONFIRMED_GLOBAL, f"location says worldwide/anywhere: \"{loc_text}\"")
    if others:
        return Eligibility(INELIGIBLE, "no", f"location lists only other places ({', '.join(others)}): \"{loc_text}\"", tz)
    if restriction:
        return Eligibility(INELIGIBLE, "no", f"description restricts eligibility: \"{restriction}\"", tz)
    if loc_text.strip(" |"):
        return Eligibility(UNVERIFIED, "unknown", f"location \"{loc_text}\" states no geography; remote is not worldwide", tz)
    return Eligibility(UNVERIFIED, "unknown", "no location text in the posting", tz)


def apply(job: JobPosting, candidate_country: str = "BR") -> JobPosting:
    e = classify(job, candidate_country)
    job.remote_class = e.remote_class
    job.eligible_for_candidate = e.eligible
    job.eligibility_evidence = e.evidence
    job.time_zone_limits = e.time_zone_limits
    job.work_from_anywhere_verified = e.work_from_anywhere_verified
    return job
