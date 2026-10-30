"""Rate limits sized for the wrong era.

They were set when inference ran against LM Studio locally, where a single scan
took minutes because of slow local inference. Every limit was therefore loose
relative to what a person could actually do. The backend now calls a hosted
provider, a verification completes in seconds, and those numbers are generous
by an order of magnitude.

These tests do not assert a number against a literal — that passes when the
number and the literal are both wrong together. They assert the *relationships*
the numbers have to keep:

- a more expensive endpoint must not be allowed more of it than a cheaper one
- `/health` carries no per-identity limit at all, because its load scales with
  the number of installed panels while the identity is the shared public IP

The old `/health` rule — "a limit must stay above what the extension genuinely
needs" — modeled one panel. In the field the identity is a carrier-grade NAT
address shared by every user behind it, and three concurrent users tripped the
30/minute bucket. See `test_health_carries_no_per_identity_rate_limit`.
"""

import re
from pathlib import Path

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.routers import scan as scan_router
from app.routers import health as health_router

transport = ASGITransport(app=app)


def _limit_of(path: str) -> int:
    """The per-minute number on a route, read from the decorator source.

    Parsed from `scan.py` rather than pulled off the `Limiter` object: slowapi
    keeps its limit table in a private attribute, so a test reaching into it
    would break on a library upgrade for no benefit. The decorator is the
    declaration; the attribute is an implementation detail of reading it.
    """
    source = Path(scan_router.__file__).read_text(encoding="utf-8")
    route = re.search(rf'@router\.\w+\("{re.escape(path)}"\)', source)
    assert route, f"{path} is not routed at all"

    after = source[route.end():]
    limit = re.search(r'@limiter\.limit\("(\d+)/', after)
    assert limit, f"{path} carries no rate limit decorator"
    return int(limit.group(1))


def _health_limit() -> int:
    source = Path(health_router.__file__).read_text(encoding="utf-8")
    route = re.search(r'@router\.get\("/health"\)', source)
    assert route, "/health is not routed at all"
    limit = re.search(r'@limiter\.limit\("(\d+)/', source[route.end():])
    assert limit, "/health carries no rate limit decorator"
    return int(limit.group(1))


@pytest.mark.asyncio
async def test_verify_refuses_once_the_limit_is_passed():
    """The limit is real, not decoration: the call after the window allows is a
    429. Asserted within one test on purpose — the conftest fixture gives every
    test its own budget, so this is the only place the number can be exercised.
    """
    limit = _limit_of("/api/verify")
    payload = {"company_name": "Acme Trading", "job_summary": "Sales associate wanted"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        statuses = [
            (await client.post("/api/verify", json=payload)).status_code
            for _ in range(limit + 1)
        ]

    assert statuses[limit - 1] == 200, "the limit refused a call the window allows"
    assert statuses[limit] == 429, "the limit did not refuse the call after it"


def test_verify_is_not_allowed_more_than_a_plain_scan():
    """A verification costs one AI call *and* one to three Tavily credits; a
    scan costs one AI call and no search. If the more expensive door is the more
    generous one, the limits are ordered by accident.

    Tavily's free tier is 1,000 credits a month and a verification spends up to
    three, so this ratio is the difference between a month's allowance lasting
    an afternoon and lasting a morning.
    """
    verify = _limit_of("/api/verify")
    scan = _limit_of("/api/scan")

    assert verify <= scan


def test_matching_is_not_allowed_more_than_a_plain_scan():
    """Matching is one call carrying up to `MAX_JOBS_PER_MATCH` jobs. It is the
    most expensive single request the backend serves, so a rate limit higher
    than a plain scan's is the wrong way round."""
    match = _limit_of("/api/match-resume")
    scan = _limit_of("/api/scan")

    assert match <= scan


def test_health_carries_no_per_identity_rate_limit():
    """/health must not sit behind a per-identity limit, at any number.

    The 2026-10-30 deployment incident: every panel polls /health every
    POLL_INTERVAL_MS, and the limit is keyed by public IP. Users behind one
    carrier-grade NAT share that IP, so three concurrent users sent the same
    30/minute bucket over its edge and every one of them saw `slowapi:
    ratelimit 30 per 1 minute exceeded` — while railway.json names this exact
    route as the platform healthcheck, so a 429 here is also a deploy-failure
    signal for a healthy service. No per-identity number survives this: the
    endpoint's load scales with user count and the identity does not. The
    endpoint is an O(1) static response with no I/O — none of the resources
    the limiter exists to protect (AI spend, Tavily credits, event loop under
    model work) are touched by it. A flood of it is an edge/infra concern,
    not an application one.
    """
    source = Path(health_router.__file__).read_text(encoding="utf-8")
    route = re.search(r'@router\.get\("/health"\)', source)
    assert route, "/health is not routed at all"

    assert not re.search(r"@limiter\.limit\(", source[route.end():]), (
        "/health carries a per-identity rate limit. Its load scales with the "
        "number of installed panels while the identity is the shared public "
        "IP, so any number trips for enough concurrent users behind one NAT "
        "- and railway.json uses this route as the platform healthcheck."
    )