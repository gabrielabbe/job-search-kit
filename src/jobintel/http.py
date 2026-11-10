"""HTTP client with the hygiene the source contract requires.

Per-host minimum interval, timeouts, honour 429/Retry-After, exponential backoff with jitter (capped),
stop on 401/403 (never retried), 404 reported as not_found. No proxies, no evasion.
The transport and the clock are injectable so every branch is tested without network.
"""
from __future__ import annotations

import json
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Callable

USER_AGENT = "jobintel/0.1 (personal job search; public job-board APIs only)"


class FetchError(Exception):
    """Transient failure after retries (timeout, 5xx, 429 exhausted)."""


class NotFound(Exception):
    """HTTP 404: wrong slug or retired board."""


class AccessDenied(Exception):
    """HTTP 401/403: stop. Never retry, never work around."""


@dataclass
class Response:
    status: int
    headers: dict[str, str]
    body: bytes

    def json(self):
        return json.loads(self.body.decode("utf-8", "replace"))


Transport = Callable[[str, dict, float], Response]


def urllib_transport(url: str, headers: dict, timeout: float) -> Response:
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return Response(r.status, {k.lower(): v for k, v in r.headers.items()}, r.read())
    except urllib.error.HTTPError as e:
        return Response(e.code, {k.lower(): v for k, v in (e.headers or {}).items()}, e.read() or b"")


@dataclass
class HttpClient:
    transport: Transport = urllib_transport
    min_interval: float = 1.0
    timeout: float = 25.0
    max_retries: int = 3
    backoff_base: float = 1.0
    backoff_cap: float = 30.0
    retry_after_cap: float = 60.0
    sleep: Callable[[float], None] = time.sleep
    clock: Callable[[], float] = time.monotonic
    rng: random.Random = field(default_factory=random.Random)
    origin: str = "live"  # tests pass origin="fixture" so fake data can never be mistaken for a real posting
    _last: dict = field(default_factory=dict)

    def _pace(self, host: str) -> None:
        last = self._last.get(host)
        if last is not None:
            wait = self.min_interval - (self.clock() - last)
            if wait > 0:
                self.sleep(wait)
        self._last[host] = self.clock()

    def get(self, url: str, params: dict | None = None) -> Response:
        if params:
            url = f"{url}{'&' if '?' in url else '?'}{urllib.parse.urlencode(params)}"
        host = urllib.parse.urlparse(url).netloc
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        last_error = ""
        for attempt in range(self.max_retries + 1):
            self._pace(host)
            try:
                resp = self.transport(url, headers, self.timeout)
            except Exception as e:  # network error, timeout
                last_error = f"{type(e).__name__}: {e}"
                self._backoff(attempt, None)
                continue
            if resp.status in (401, 403):
                raise AccessDenied(f"HTTP {resp.status} for {url}")
            if resp.status == 404:
                raise NotFound(url)
            if resp.status == 429 or resp.status >= 500:
                last_error = f"HTTP {resp.status}"
                self._backoff(attempt, resp.headers.get("retry-after"))
                continue
            if 200 <= resp.status < 300:
                return resp
            raise FetchError(f"HTTP {resp.status} for {url}")
        raise FetchError(f"gave up after {self.max_retries + 1} attempts: {last_error}")

    def _backoff(self, attempt: int, retry_after: str | None) -> None:
        if attempt >= self.max_retries:
            return  # no sleep after the final attempt
        delay = None
        if retry_after:
            try:
                delay = min(float(retry_after), self.retry_after_cap)
            except ValueError:
                delay = None
        if delay is None:
            delay = min(self.backoff_cap, self.backoff_base * (2 ** attempt)) * (0.5 + self.rng.random() / 2)
        self.sleep(delay)
