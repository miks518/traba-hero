"""The backend must refuse what the frontend would never send.

The extension stops at four screenshots (`MAX_SCREENSHOTS` in
`ScamScanView.tsx`) and compresses each to a JPEG capped at 1280px. The API had
neither limit: `ScanRequest.images_base64` was an unbounded `list[str]` with no
per-item length cap.

That gap is a cost amplifier rather than a bug with a visible symptom. Vision
tokens scale with pixel area, so one request carrying several hundred images is
a single enormous call against a *reasoning* model — the configured kind — and
the person paying for it learns about it from a bill.

These tests are written the way a hostile caller would write them, because that
is the caller this endpoint was being tested against before: a careful developer
sending one small image. Well-formed input cannot find a missing limit.

**Why 422 and not truncation.** Dropping images 5-40 and scanning the first four
would return a result describing four images while claiming to describe forty.
That is a lie in the direction this product is specifically built to avoid, and
it is worse than a refusal because the reader cannot tell it happened.
"""

import re
from pathlib import Path

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.models.schemas import (
    MAX_IMAGES_PER_SCAN,
    MAX_IMAGE_BASE64,
    ScanRequest,
)

transport = ASGITransport(app=app)


@pytest.mark.asyncio
async def test_forty_images_in_one_request_is_refused():
    """The amplification case, stated as the attacker would try it."""
    payload = {"images_base64": ["dGVzdA=="] * 40, "language": "english"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/scan", json=payload)

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_one_image_past_the_cap_is_refused():
    """One over, not a lot over. The boundary is what a cap actually is."""
    payload = {"images_base64": ["dGVzdA=="] * (MAX_IMAGES_PER_SCAN + 1)}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/scan", json=payload)

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_exactly_the_cap_is_accepted():
    """The other side of the same boundary. Without this a cap of zero passes
    the test above, and so does a cap that rejects everything."""
    payload = {"images_base64": ["dGVzdA=="] * MAX_IMAGES_PER_SCAN}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/scan", json=payload)

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_one_oversized_image_is_refused():
    """Bounded count, unbounded item. Forty 200KB images are fine; one image
    the size of a phone video is the same token cost as hundreds."""
    payload = {"images_base64": ["A" * (MAX_IMAGE_BASE64 + 1)]}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/scan", json=payload)

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_the_singular_image_field_is_capped_too():
    """`image_base64` is the legacy spelling and still accepted. Capping only
    the list would leave the cheapest door open: one call, one enormous image."""
    payload = {"image_base64": "A" * (MAX_IMAGE_BASE64 + 1)}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/scan", json=payload)

    assert resp.status_code == 422


def test_the_limit_matches_what_the_extension_sends():
    """The backend must not be stricter than the client it serves, or ordinary
    use breaks to fix a problem nobody has.

    Read out of the extension source rather than restated as a literal, because
    a literal asserting `MAX_IMAGES_PER_SCAN == 4` passes even if both numbers
    are wrong together. This is the guard against the two drifting apart in
    either direction — a backend that rejects a normal four-image scan, or one
    that raises its own cap without the client being able to reach it.
    """
    frontend = Path(__file__).resolve().parents[2] / (
        "entrypoints/sidepanel/views/ScamScanView.tsx"
    )
    match = re.search(r"const MAX_SCREENSHOTS\s*=\s*(\d+)", frontend.read_text(encoding="utf-8"))

    assert match, "MAX_SCREENSHOTS not found in ScamScanView.tsx"
    assert int(match.group(1)) == MAX_IMAGES_PER_SCAN


def test_the_schema_rejects_the_attempt_without_a_server():
    """The cap lives on the schema, so it also holds for anything that validates
    the body before a request is ever made. Asserting it here rather than only
    over HTTP pins the limit to the field rather than to a route."""
    with pytest.raises(ValueError):
        ScanRequest(images_base64=["x"] * (MAX_IMAGES_PER_SCAN + 1))

    assert len(ScanRequest(images_base64=["x"] * MAX_IMAGES_PER_SCAN).images_base64) == (
        MAX_IMAGES_PER_SCAN
    )