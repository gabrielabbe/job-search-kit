import pytest

from conftest import make_job
from jobintel.eligibility import classify
from jobintel.models import (CONFIRMED_COUNTRY, CONFIRMED_GLOBAL, CONFIRMED_REGION, INELIGIBLE, UNVERIFIED)

CASES = [
    # (location_raw, extra, remote_type, description, expected class, expected eligible)
    ("Remote - US", [], "remote", "", INELIGIBLE, "no"),                                     # 'Remote - US only' fixture
    ("Remote", [], "remote", "", UNVERIFIED, "unknown"),                                      # remote is not worldwide
    ("Remote - Brazil", [], "remote", "", CONFIRMED_COUNTRY, "yes"),
    ("Brasil", [], "remote", "Fully remote team.", CONFIRMED_COUNTRY, "yes"),
    ("Remote, LATAM", [], "remote", "", CONFIRMED_REGION, "yes"),
    ("Latin America", [], "remote", "", CONFIRMED_REGION, "yes"),
    ("Remote - Americas", [], "unknown", "", CONFIRMED_REGION, "yes"),
    ("Worldwide", [], "remote", "", CONFIRMED_GLOBAL, "yes"),
    ("Remote - Global", [], "unknown", "", CONFIRMED_GLOBAL, "yes"),
    ("Sao Paulo", [], "unknown", "We hire in the office.", UNVERIFIED, "unknown"),           # Brazil city, remote not stated
    ("Sao Paulo", [], "hybrid", "", INELIGIBLE, "no"),
    ("Remote - Mexico", [], "remote", "", INELIGIBLE, "no"),                                  # other LATAM country
    ("Remote, EMEA", [], "remote", "", INELIGIBLE, "no"),
    ("Remote - North America", [], "remote", "", INELIGIBLE, "no"),
    ("Remote - Canada", [], "remote", "", INELIGIBLE, "no"),
    ("Remote - California", [], "remote", "", INELIGIBLE, "no"),
    ("Remote - US or Brazil", [], "remote", "", CONFIRMED_COUNTRY, "yes"),
    ("South Africa, Argentina, Colombia, Mexico, Chile, Brazil", [], "remote", "", CONFIRMED_COUNTRY, "yes"),
    ("Remote", [], "remote", "Candidates must reside in the United States.", INELIGIBLE, "no"),
    ("Remote", [], "remote", "You must be authorized to work in the US without sponsorship.", INELIGIBLE, "no"),
    ("Remote (Worldwide)", [], "remote", "You must be legally authorized to work in the United States.", UNVERIFIED, "unknown"),  # conflict
    ("Remote", [], "remote", "We are a US-based company with a global team.", UNVERIFIED, "unknown"),  # not a restriction
    ("London | GB", [], "remote", "", INELIGIBLE, "no"),                                      # regression: found in a live Spotify check
    ("London | Stockholm | GB", [], "remote", "", INELIGIBLE, "no"),
    ("Remote | IT", [], "remote", "", UNVERIFIED, "unknown"),                                 # 'IT' is technology, not Italy
    ("Remote, Brazil | BR", [], "remote", "", CONFIRMED_COUNTRY, "yes"),
]


@pytest.mark.parametrize("loc,extra,rtype,desc,cls,elig", CASES)
def test_classification(loc, extra, rtype, desc, cls, elig):
    e = classify(make_job(location_raw=loc, extra_locations=extra, remote_type=rtype, description_text=desc))
    assert (e.remote_class, e.eligible) == (cls, elig), e.evidence
    assert e.evidence  # every decision carries evidence


def test_remote_is_never_inferred_as_worldwide():
    e = classify(make_job(location_raw="Remote", description_text=""))
    assert e.remote_class != CONFIRMED_GLOBAL and not e.work_from_anywhere_verified


def test_time_zone_limits_are_extracted_but_do_not_change_class():
    e = classify(make_job(location_raw="Remote - Brazil", description_text="We need 4 hours of overlap with US Eastern time zone."))
    assert e.remote_class == CONFIRMED_COUNTRY and "overlap" in e.time_zone_limits.lower()


def test_other_candidate_country_changes_result():
    j = make_job(location_raw="Remote - Mexico")
    assert classify(j, "BR").remote_class == INELIGIBLE


@pytest.mark.parametrize("country,location,expected", [
    ("PT", "Remote - Portugal", CONFIRMED_COUNTRY),
    ("PT", "Remote, EMEA", CONFIRMED_REGION),
    ("PT", "Remote - Brazil", INELIGIBLE),
    ("US", "Remote - United States", CONFIRMED_COUNTRY),
    ("US", "Remote - Canada", INELIGIBLE),
    ("IN", "Remote | Bengaluru", CONFIRMED_COUNTRY),
    ("DE", "Berlin | DE", CONFIRMED_COUNTRY),
])
def test_built_in_countries_beyond_the_default(country, location, expected):
    j = make_job(location_raw=location, remote_type="remote", description_text="Fully remote team.")
    assert classify(j, country).remote_class == expected
