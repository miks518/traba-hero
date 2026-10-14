"""The rate-limit bound must hold through the real app, not just the key function.

This is the test `docs/security-audit-2026-10-14.md` asked for. The key function
had a unit test asserting that X-Forwarded-For won, and the suite stayed green
while the bound was bypassable, because no test ever drove the app with a
rotating header.

Each request below carries a fresh X-Forwarded-For, so a limiter keyed on the
header sees a new principal every time and never engages. `/api/match-resume` is
the route used because it carries the tightest limit in the service, so six
requests is twice what the window allows.

Both halves matter. The bypass test only means something next to a control that
shows the same budget applies when the header is absent; without it, a test that
found no 429 at all would pass for the wrong reason.
"""

import logging

import pytest
from httpx import AsyncClient, ASGITransport

from app.config import settings
from app.main import _warn_if_no_trusted_proxies, app

transport = ASGITransport(app=app)

PATH = "/api/match-resume"
REQUESTS = 6  # the route allows 3/minute, so this is twice the window

PAYLOAD = {
    "resume": {
        "skills": ["Python"],
        "experience_years": 2,
        "job_titles": ["Developer"],
        "industries": ["IT"],
        "summary": "A summary.",
    },
    "jobs": [{"id": "job-0", "title": "Sales associate", "summary": "A role."}],
}

LIMIT = 3  # the per-minute number on /api/match-resume


async def _statuses(headers_for: "callable" = None) -> list[int]:
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return [
            (
                await client.post(
                    PATH, json=PAYLOAD, headers=headers_for(i) if headers_for else None
                )
            ).status_code
            for i in range(REQUESTS)
        ]


def _rotating_header(i: int) -> dict:
    return {"X-Forwarded-For": f"203.0.113.{i}"}


@pytest.mark.asyncio
async def test_rotating_the_forwarded_header_does_not_reset_the_budget():
    """The bypass itself. Every request claims a different client, and the
    service is supposed to notice that they are all arriving on one socket."""
    statuses = await _statuses(_rotating_header)

    assert statuses[:LIMIT] == [200] * LIMIT, (
        "the limit refused a call the window allows"
    )
    assert 429 in statuses[LIMIT:], (
        f"rotating X-Forwarded-For reset the rate-limit budget: {statuses}"
    )


@pytest.mark.asyncio
async def test_without_the_header_the_same_budget_still_applies():
    """The control. If this found no 429 either, the test above would be
    passing because nothing was rate limiting at all."""
    statuses = await _statuses(None)

    assert statuses[:LIMIT] == [200] * LIMIT
    assert 429 in statuses[LIMIT:], f"the route is not rate limited: {statuses}"


# ── The operator-facing half ─────────────────────────────────────────────────


def test_startup_warns_when_no_proxy_is_trusted(caplog, monkeypatch):
    """Blank TRUSTED_PROXIES puts every caller in one shared bucket.

    That is the fail-closed direction and it is correct, but it is also the
    failure most likely to surprise whoever deployed this: the symptom is an
    unexplained 429 for users who did nothing wrong, and the cause is a setting
    they were never told existed. So it is said out loud at startup.

    Asserted on two substrings rather than the whole sentence, so rewording is
    not a failure but gutting the message into something unhelpful is.
    """
    monkeypatch.setattr(settings, "trusted_proxies", "")

    with caplog.at_level(logging.WARNING, logger="trabahero"):
        _warn_if_no_trusted_proxies()

    message = caplog.text
    assert "TRUSTED_PROXIES" in message
    assert "proxy" in message.lower()


def test_no_warning_when_a_proxy_is_trusted(caplog, monkeypatch):
    """A warning that always fires trains the operator to ignore the one time it
    matters."""
    monkeypatch.setattr(settings, "trusted_proxies", "10.0.0.0/8")

    with caplog.at_level(logging.WARNING, logger="trabahero"):
        _warn_if_no_trusted_proxies()

    assert "TRUSTED_PROXIES" not in caplog.text


def test_the_warning_fires_once_not_per_request(caplog, monkeypatch):
    """Per-request it would bury the log it is trying to be read in.

    Counts records rather than substring occurrences: the message names
    TRUSTED_PROXIES twice, so counting the string would read 2 for one record.
    """
    monkeypatch.setattr(settings, "trusted_proxies", "")
    caplog.clear()

    with caplog.at_level(logging.WARNING, logger="trabahero"):
        _warn_if_no_trusted_proxies()

    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert len(warnings) == 1
