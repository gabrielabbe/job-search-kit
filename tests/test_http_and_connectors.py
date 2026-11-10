import pytest

from conftest import fake_http, fixture_json
from jobintel.connectors import (AshbyConnector, GreenhouseConnector, LeverConnector, SmartRecruitersConnector)
from jobintel.http import AccessDenied, FetchError, NotFound, Response
from jobintel.models import Company


# ---------------------------------------------------------------- HTTP hygiene
def test_429_honours_retry_after():
    http, t = fake_http({"x.test": [Response(429, {"retry-after": "3"}, b""), Response(200, {}, b"{}")]})
    assert http.get("https://x.test/a").status == 200
    assert http.sleeps == [3.0]


def test_429_retry_after_is_capped():
    http, _ = fake_http({"x.test": [Response(429, {"retry-after": "99999"}, b""), Response(200, {}, b"{}")]})
    http.get("https://x.test/a")
    assert http.sleeps == [http.retry_after_cap]


def test_5xx_backoff_is_exponential_with_jitter_and_capped():
    http, t = fake_http({"x.test": Response(503, {}, b"")}, max_retries=3, backoff_cap=4.0)
    with pytest.raises(FetchError):
        http.get("https://x.test/a")
    assert len(t.calls) == 4  # 1 try + 3 retries, no more
    assert len(http.sleeps) == 3  # never sleeps after the last attempt
    assert all(0 < s <= 4.0 for s in http.sleeps)


def test_403_stops_immediately_and_is_never_retried():
    http, t = fake_http({"x.test": Response(403, {}, b"")})
    with pytest.raises(AccessDenied):
        http.get("https://x.test/a")
    assert len(t.calls) == 1 and http.sleeps == []


def test_401_also_stops():
    http, t = fake_http({"x.test": Response(401, {}, b"")})
    with pytest.raises(AccessDenied):
        http.get("https://x.test/a")
    assert len(t.calls) == 1


def test_404_is_not_found_without_retry():
    http, t = fake_http({})
    with pytest.raises(NotFound):
        http.get("https://x.test/a")
    assert len(t.calls) == 1


def test_timeout_is_retried_then_reported():
    http, t = fake_http({"x.test": TimeoutError("timed out")}, max_retries=2)
    with pytest.raises(FetchError):
        http.get("https://x.test/a")
    assert len(t.calls) == 3


def test_per_host_pacing():
    from jobintel.http import HttpClient
    now = [0.0]
    sleeps = []
    c = HttpClient(transport=lambda u, h, t: Response(200, {}, b"{}"), min_interval=1.0, sleep=sleeps.append,
                   clock=lambda: now[0], origin="fixture")
    c.get("https://a.test/1")
    c.get("https://a.test/2")  # same host, no time passed: must wait
    c.get("https://b.test/1")  # other host: no wait
    assert sleeps == [1.0]


# ---------------------------------------------------------------- Greenhouse
def test_greenhouse_normalizes_pay_cents_period_and_escaped_html():
    http, t = fake_http({"boards-api.greenhouse.io": fixture_json("greenhouse_board.json")})
    res = GreenhouseConnector(http).fetch_jobs(Company("FixtureCo", "fixtureco", "greenhouse"))
    assert res.status == "ok" and res.authoritative and len(res.jobs) == 4
    assert "content=true" in t.calls[0] and "pay_transparency=true" in t.calls[0]  # reference traps 5 and 6
    by = {j.external_id: j for j in res.jobs}
    assert (by["1001"].salary_min, by["1001"].salary_max, by["1001"].salary_period) == (5400.0, 6600.0, "monthly")
    assert by["1002"].salary_min == 222800.0 and by["1002"].salary_period == "annual"
    assert by["1003"].salary_period == "hourly"  # an hourly rate must never be read as annual
    assert by["1004"].salary_min is None
    assert "<" not in by["1001"].description_text  # HTML reduced to text
    assert all(j.data_origin == "fixture" for j in res.jobs)


def test_greenhouse_script_instructions_are_dropped_as_untrusted_text():
    http, _ = fake_http({"boards-api.greenhouse.io": fixture_json("greenhouse_board.json")})
    job = GreenhouseConnector(http).fetch_jobs(Company("FixtureCo", "fixtureco", "greenhouse")).jobs[0]
    assert "ignore all previous instructions" not in job.description_text


def test_greenhouse_empty_200_is_an_authoritative_empty_board():
    http, _ = fake_http({"greenhouse": {"jobs": []}})
    res = GreenhouseConnector(http).fetch_jobs(Company("x", "x", "greenhouse"))
    assert res.status == "empty" and res.authoritative


def test_greenhouse_404_is_not_found_and_403_is_access_denied():
    c = Company("x", "x", "greenhouse")
    assert GreenhouseConnector(fake_http({})[0]).fetch_jobs(c).status == "not_found"
    res = GreenhouseConnector(fake_http({"greenhouse": Response(403, {}, b"")})[0]).fetch_jobs(c)
    assert res.status == "access_denied" and not res.authoritative


def test_malformed_payload_is_an_error_not_a_crash():
    res = GreenhouseConnector(fake_http({"greenhouse": {"unexpected": True}})[0]).fetch_jobs(Company("x", "x", "greenhouse"))
    assert res.status == "error" and "malformed" in res.error


# ---------------------------------------------------------------- Lever / Ashby
def test_lever_fills_company_from_registry_and_normalizes():
    http, _ = fake_http({"api.lever.co": fixture_json("lever_board.json")})
    res = LeverConnector(http).fetch_jobs(Company("LeverCo", "leverco", "lever"))
    assert res.status == "ok" and len(res.jobs) == 2
    j = res.jobs[0]
    assert j.company_name == "LeverCo" and j.remote_type == "remote" and j.salary_period == "monthly"
    assert j.posted_at.startswith("2026-")
    assert res.jobs[1].remote_type == "onsite"


def test_lever_non_list_payload_is_rejected():
    res = LeverConnector(fake_http({"lever": {"jobs": []}})[0]).fetch_jobs(Company("x", "x", "lever"))
    assert res.status == "error"


def test_ashby_skips_unlisted_and_reads_compensation():
    http, t = fake_http({"ashbyhq.com": fixture_json("ashby_board.json")})
    res = AshbyConnector(http).fetch_jobs(Company("AshbyCo", "ashbyco", "ashby"))
    assert [j.external_id for j in res.jobs] == ["ash-1", "ash-3"]
    j = res.jobs[0]
    assert (j.salary_min, j.salary_max, j.salary_period, j.currency) == (4500, 6000, "monthly", "USD")
    assert "Brazil" in j.extra_locations
    assert "includeCompensation=true" in t.calls[0]


# ---------------------------------------------------------------- SmartRecruiters
def _sr_item(i):
    return {"id": f"id{i}", "name": f"Role {i}", "company": {"name": "SRCo"}, "releasedDate": "2026-11-01T00:00:00Z",
            "location": {"city": "Lisbon", "country": "pt", "remote": True, "fullLocation": "Lisbon, Portugal"}}


def test_smartrecruiters_pages_past_100():
    def transport_routes():
        calls = []

        def route(url, headers, timeout):
            calls.append(url)
            off = int(url.split("offset=")[1].split("&")[0])
            items = [_sr_item(i) for i in range(off, min(off + 100, 140))]
            import json
            return Response(200, {}, json.dumps({"totalFound": 140, "content": items}).encode())
        return route, calls
    from jobintel.http import HttpClient
    route, calls = transport_routes()
    http = HttpClient(transport=route, min_interval=0, sleep=lambda s: None, origin="fixture")
    res = SmartRecruitersConnector(http).fetch_jobs(Company("SRCo", "srco", "smartrecruiters"))
    assert len(res.jobs) == 140 and len(calls) == 2  # silently losing postings past 100 is reference trap 4
    assert res.jobs[0].remote_type == "remote" and "(PT)" in res.jobs[0].location_raw


def test_smartrecruiters_zero_rows_never_proves_an_empty_board():
    res = SmartRecruitersConnector(fake_http({"smartrecruiters": {"totalFound": 0, "content": []}})[0]).fetch_jobs(
        Company("x", "x", "smartrecruiters"))
    assert res.status == "empty_or_unknown" and not res.authoritative  # reference trap 1


def test_invalid_slug_is_never_requested():
    http, t = fake_http({})
    res = GreenhouseConnector(http).fetch_jobs(Company("x", "airbyte dbtlabs/../x", "greenhouse"))
    assert res.status == "error" and "invalid slug" in res.error and t.calls == []


def test_watchlist_lines_with_several_slugs_are_split(tmp_path):
    from jobintel.config import read_watchlist
    p = tmp_path / "w.txt"
    p.write_text("# comment\nairbyte dbtlabs  fivetran # trailing\nhubspot,asana\n\nairbyte\n", encoding="utf-8")
    assert read_watchlist(p) == ["airbyte", "dbtlabs", "fivetran", "hubspot", "asana"]
