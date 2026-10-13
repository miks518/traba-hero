"""Rate limits sized for the wrong era.

They were set when inference ran against LM Studio locally, where a single scan
took minutes because of slow local inference. Every limit was therefore loose
relative to what a person could actually do. The backend now calls a hosted
provider, a verification completes in seconds, and those numbers are generous
by an order of magnitude.

These tests do not assert a number against a literal — that passes when the
number and the literal are both wrong together. They assert the *relationships*
the numbers have to keep:

- a limit must stay above what the extension genuinely needs (`/health`)
- a more expensive endpoint must not be allowed more of it than a cheaper one

The `/health` one is the sharpest. The extension polls it every four seconds
while the panel is open, so 15 probes a minute is a floor, not a preference.
"Tightening" it looks like a security improvement and silently breaks the
offline banner for every user, which is why it is read out of the frontend
rather than restated here.
"""

import re
from pathlib import Path

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.routers import scan as scan_router
from app.routers import health as health_router

transport = ASGITransport(app=app)
HEADERS = {"X-Trabahero-Client-Key": "test-secret-key"}


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
            (await client.post("/api/verify", json=payload, headers=HEADERS)).status_code
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


def test_the_health_limit_clears_the_extension_polling_rate():
    """15 probes a minute is a floor set by the client, not a preference.

    The panel polls `/health` every `POLL_INTERVAL_MS` while visible, and
    `useBackendHealth` flips the offline banner after two consecutive failures.
    A limit below the poll rate does not stop an attacker and does break every
    legitimate user, so it is pinned to the frontend's own number.
    """
    hook = Path(__file__).resolve().parents[2] / (
        "entrypoints/sidepanel/hooks/useBackendHealth.ts"
    )
    match = re.search(
        r"const POLL_INTERVAL_MS\s*=\s*(\d+)", hook.read_text(encoding="utf-8")
    )
    assert match, "POLL_INTERVAL_MS not found in useBackendHealth.ts"

    per_minute = 60_000 / int(match.group(1))

    assert _health_limit() >= per_minute, (
        f"/health allows {_health_limit()}/minute but the panel polls every "
        f"{match.group(1)}ms ({per_minute}/minute)"
    )