from conftest import make_job
from jobintel import eligibility
from jobintel.models import FetchResult
from jobintel.search import fts_query, monthly_usd, search


def result(jobs, status="ok", authoritative=True, provider="greenhouse", slug="acme"):
    return FetchResult(provider=provider, slug=slug, source_url="https://example.test", status=status, jobs=jobs,
                       authoritative=authoritative)


def test_ingest_new_unchanged_updated_and_versions(store):
    j = eligibility.apply(make_job())
    assert store.ingest(result([j]))["new"] == 1
    assert store.ingest(result([j]))["unchanged"] == 1
    j2 = eligibility.apply(make_job(raw_hash="h2", description_text="Own IT and security."))
    assert store.ingest(result([j2]))["updated"] == 1
    assert store.count("job_versions") == 2 and store.count("job_postings") == 1


def test_closure_only_after_a_successful_authoritative_fetch(store):
    a, b = eligibility.apply(make_job(external_id="1")), eligibility.apply(make_job(external_id="2", canonical_url="https://acme.test/jobs/2", title="IT Lead"))
    store.ingest(result([a, b]))
    # a timeout, 429 or error must never close anything
    store.ingest(result([], status="error", authoritative=False))
    assert store.db.execute("SELECT COUNT(*) c FROM job_postings WHERE status='OPEN'").fetchone()["c"] == 2
    # ambiguous empty (SmartRecruiters style) must not close anything
    store.ingest(result([], status="empty_or_unknown", authoritative=False))
    assert store.db.execute("SELECT COUNT(*) c FROM job_postings WHERE status='OPEN'").fetchone()["c"] == 2
    # a successful full fetch without job 2 closes it
    counts = store.ingest(result([a]))
    assert counts["closed"] == 1 and store.job("greenhouse:acme:2")["status"] == "CLOSED"
    # it comes back: reopened
    assert store.ingest(result([a, b]))["reopened"] == 1


def test_canonical_url_duplicate_is_flagged_across_providers(store):
    a = eligibility.apply(make_job(provider="greenhouse", external_id="1", canonical_url="https://acme.test/jobs/1?utm_source=x"))
    b = eligibility.apply(make_job(provider="lever", external_id="zz", canonical_url="https://acme.test/jobs/1/"))
    store.ingest(result([a]))
    c = store.ingest(result([b], provider="lever"))
    assert c["duplicates"] == 1
    methods = {d["method"] for d in store.duplicates()}
    assert "canonical_url" in methods  # same company/title/location is also flagged fuzzy, for review


def test_fuzzy_duplicate_needs_human_review_and_is_not_merged(store):
    a = eligibility.apply(make_job(provider="greenhouse", external_id="1", canonical_url="https://a.test/1"))
    b = eligibility.apply(make_job(provider="lever", external_id="2", canonical_url="https://b.test/2"))
    store.ingest(result([a]))
    store.ingest(result([b], provider="lever"))
    d = store.duplicates(only_review=True)
    assert len(d) == 1 and d[0]["method"] == "fuzzy"
    assert store.count("job_postings") == 2  # never auto-merged


def test_search_applies_hard_filters_before_text(store, profile):
    jobs = [
        eligibility.apply(make_job(external_id="1", title="IT Manager", location_raw="Remote - Brazil", canonical_url="https://t/1")),
        eligibility.apply(make_job(external_id="2", title="IT Manager", location_raw="Remote - US", canonical_url="https://t/2")),
        eligibility.apply(make_job(external_id="3", title="IT Manager", location_raw="Remote", canonical_url="https://t/3")),
        eligibility.apply(make_job(external_id="4", title="IT Manager", location_raw="Remote - Brazil", remote_type="remote",
                                   salary_min=1500, salary_max=2000, currency="USD", salary_period="monthly", canonical_url="https://t/4")),
        eligibility.apply(make_job(external_id="5", title="Software Engineer - IT Operations", location_raw="Remote - Brazil", canonical_url="https://t/5")),
    ]
    store.ingest(result(jobs))
    r = search(store, profile, origin="fixture")
    assert [x["external_id"] for x in r.rows] == ["1"]
    reasons = dict(r.excluded)
    assert "below the $3,500 floor" in reasons["greenhouse:acme:4"]
    assert "excluded title term" in reasons["greenhouse:acme:5"]
    r2 = search(store, profile, include_unverified=True, origin="fixture")
    assert {"1", "3"} <= {x["external_id"] for x in r2.rows} and "2" not in {x["external_id"] for x in r2.rows}


def test_fixture_data_is_never_returned_as_live(store, profile):
    store.ingest(result([eligibility.apply(make_job())]))
    assert search(store, profile).rows == []  # default origin is live
    assert len(search(store, profile, origin="fixture").rows) == 1


def test_closed_postings_are_not_searchable(store, profile):
    a = eligibility.apply(make_job(external_id="1"))
    store.ingest(result([a]))
    store.ingest(result([]))  # authoritative empty closes it
    assert search(store, profile, origin="fixture").rows == []


def test_fts_query_cannot_inject_syntax(store, profile):
    q = fts_query(['it manager" OR ("', "NEAR(a b)"])
    assert q.count('"') % 2 == 0
    store.ingest(result([eligibility.apply(make_job())]))
    search(store, profile, query='weird " OR * ( ) NEAR', origin="fixture")  # must not raise


def test_monthly_usd_never_defaults_the_period():
    fx = {"USD": 1.0}
    assert monthly_usd({"salary_min": 60000, "salary_max": None, "salary_period": "annual", "currency": "USD"}, fx) == 5000
    assert monthly_usd({"salary_min": 60000, "salary_max": None, "salary_period": "unknown", "currency": "USD"}, fx) is None
    assert monthly_usd({"salary_min": 60, "salary_max": None, "salary_period": "hourly", "currency": "USD"}, fx) > 10000


def test_canonical_key_keeps_job_identifying_params_and_drops_tracking():
    from jobintel.store import canonical_key
    a = canonical_key("https://www.acme.com/careers/job?gh_jid=111&utm_source=x&gh_src=y")
    b = canonical_key("https://www.acme.com/careers/job?gh_jid=222")
    c = canonical_key("https://www.acme.com/careers/job/?gh_jid=111")
    assert a != b and a == c  # regression: stripping gh_jid collapsed 13,000 distinct postings into duplicates


def test_distinct_jobs_on_one_careers_page_are_not_duplicates(store):
    jobs = [eligibility.apply(make_job(external_id=str(i), title=f"Role {i}", canonical_url=f"https://acme.com/careers/job?gh_jid={i}")) for i in range(5)]
    store.ingest(result(jobs))
    assert store.duplicates() == []
    assert store.rebuild_dedupe() == {"duplicate_flags": 0}
