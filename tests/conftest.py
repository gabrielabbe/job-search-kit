"""Shared helpers. All network access in tests goes through FakeTransport: no test touches the network."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from jobintel.config import load_profile  # noqa: E402
from jobintel.evidence import EvidenceBase  # noqa: E402
from jobintel.http import HttpClient, Response  # noqa: E402
from jobintel.models import JobPosting  # noqa: E402
from jobintel.store import Store  # noqa: E402

FIX = Path(__file__).parent / "fixtures"


def fixture_json(name: str):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


class FakeTransport:
    """Routes URL substrings to canned responses; records calls. A value may be a list to script successive replies."""

    def __init__(self, routes: dict):
        self.routes, self.calls = routes, []

    def __call__(self, url, headers, timeout):
        self.calls.append(url)
        for key, val in self.routes.items():
            if key in url:
                scripted = isinstance(val, list) and val and all(isinstance(v, (Response, Exception)) for v in val)
                if scripted:
                    val = val.pop(0) if len(val) > 1 else val[0]
                if isinstance(val, Exception):
                    raise val
                if isinstance(val, Response):
                    return val
                return Response(200, {}, json.dumps(val).encode())
        return Response(404, {}, b"")


def fake_http(routes: dict, **kw) -> tuple[HttpClient, FakeTransport]:
    t = FakeTransport(routes)
    sleeps = []
    http = HttpClient(transport=t, min_interval=0, sleep=sleeps.append, origin="fixture", **kw)
    http.sleeps = sleeps  # type: ignore[attr-defined]
    return http, t


def make_job(**kw) -> JobPosting:
    base = dict(provider="greenhouse", company_slug="acme", external_id="1", company_name="Acme", title="IT Manager",
                source_url="https://example.test/api", fetched_at="2026-11-06T00:00:00Z", canonical_url="https://acme.test/jobs/1",
                location_raw="Remote - Brazil", remote_type="remote", description_text="Own IT.", raw_hash="h1")
    base.update(kw)
    j = JobPosting(**base)
    j.data_origin = "fixture"
    return j


@pytest.fixture
def store():
    s = Store(":memory:")
    yield s
    s.close()


@pytest.fixture
def evidence():
    return EvidenceBase.load(FIX / "evidence_sample.json", FIX / "skills_sample.json")


@pytest.fixture
def profile():
    return load_profile("test", FIX / "search-profiles.test.yaml")
