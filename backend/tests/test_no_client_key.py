"""There is no client key, and this is why.

The extension used to send `X-Trabahero-Client-Key` and the backend compared it
against `CLIENT_SECRET_KEY`. That looked like authentication and protected
nothing.

**The key shipped inside the extension.** `WXT_CLIENT_KEY` was compiled into the
bundle at build time, so anyone could open `chrome://extensions`, click *service
worker -> inspect*, and read it as a string literal in the JavaScript. A shared
secret in a browser extension is not a secret — it is a speed bump for someone
who does not know where to look, and it was presented as a security boundary in
the docs ("In production, always set CLIENT_SECRET_KEY").

**A token would not have fixed it.** Any credential the extension holds is
equally extractable. A per-install signed token would have added a database and
a revocation list to defend against an attacker who can simply request their own
token.

So the boundary is gone, and the loss is bounded instead: per-endpoint rate
limits weighted by what each call costs, hard input caps on every request body,
and a spending ceiling at the provider. Those hold against someone patient. An
extractable string never did.

What this costs is stated plainly rather than forgotten: `/api/verify` and the
scan endpoints are reachable by anyone who can reach the URL. See
`test_cors_is_not_wildcard.py` for the control that remains in front of it.
"""

import re
from pathlib import Path

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

transport = ASGITransport(app=app)

# Each endpoint's own required body, so a 422 here means the auth change
# regressed rather than that this test sent the wrong shape.
BODIES = {
    "/api/verify": {"company_name": "Acme Trading", "job_summary": "Sales associate"},
    "/api/scan": {"images_base64": ["dGVzdA=="]},
    "/api/analyze-offer": {"text": "Offer to pay for referrals."},
}


@pytest.mark.asyncio
@pytest.mark.parametrize("path", sorted(BODIES))
async def test_a_request_with_no_key_is_served(path):
    """The direct consequence. Before this was a 401."""
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(path, json=BODIES[path])

    assert resp.status_code == 200, f"{path} still refuses a request with no key"


@pytest.mark.asyncio
async def test_a_bogus_key_is_ignored_rather_than_rejected():
    """Proves nothing is reading the header, which is stronger than proving a
    valid one is accepted. A 401 here would mean a check still exists and is
    only passing because the value happens to match."""
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"X-Trabahero-Client-Key": "deliberately-wrong"},
    ) as client:
        resp = await client.post("/api/verify", json={
            "company_name": "Acme Trading",
            "job_summary": "Sales associate wanted",
        }, headers={"X-Trabahero-Client-Key": "deliberately-wrong"})

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_health_needs_nothing():
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")

    assert resp.status_code == 200


def test_no_route_carries_the_auth_dependency_again():
    """The regression guard. Re-adding one is a two-line change and looks like
    hardening, so it is asserted rather than left to review."""
    from app.routers import scan as scan_router

    source = Path(scan_router.__file__).read_text(encoding="utf-8")

    assert "require_client_key" not in source, "a route still validates a client key"


def test_the_auth_module_is_gone():
    """Not merely unused — removed. A module left in place is read by the next
    person as something that might be in use, and `EXPECTED_KEY` at import time
    is the kind of line that keeps a removed idea alive."""
    import app.core

    core = Path(app.core.__file__).resolve().parent / "auth.py"

    assert not core.exists(), "backend/app/core/auth.py still exists"


def test_the_settings_field_is_gone():
    """Same reason. A `client_secret_key` that nothing reads is worse than no
    field: it invites someone to set it and believe it is doing something."""
    from app.config import Settings

    assert "client_secret_key" not in Settings.model_fields


def test_the_extension_stops_sending_the_header():
    """The other end of the same wire. Leaving it would leave the header in the
    bundle, which is the thing that made the scheme false comfort in the first
    place — a secret-looking string people would treat as load-bearing."""
    from app.routers import scan as scan_router

    # backend/app/routers/scan.py -> routers -> app -> backend -> repo root
    repo_root = Path(scan_router.__file__).resolve().parents[3]
    api = (repo_root / "entrypoints/sidepanel/lib/api.ts").read_text(encoding="utf-8")

    assert "authHeaders" not in api
    assert "X-Trabahero-Client-Key" not in api
    assert "WXT_CLIENT_KEY" not in api