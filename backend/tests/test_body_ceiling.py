"""A body the framework has already buffered cannot be called a cap.

Every endpoint caps its fields in pydantic, and the caps are rejections rather
than truncations, which is the right call. But pydantic runs *after* FastAPI has
read the request body into memory and JSON-decoded it. So a caller can send a
body far larger than any cap allows, have the single uvicorn worker allocate and
parse all of it, and only then receive its 422.

That is narrower than it sounds. `MAX_IMAGES_PER_SCAN` is 4 and
`MAX_IMAGE_BASE64` is 5,000,000, so a *schema-valid* `POST /api/scan` body is
about 20 MB of base64. The gap between what is refused and what is accepted is
small, which is what makes the missing pre-buffer ceiling worth closing.

The rate limit does not help. `@limiter.limit` decorates the endpoint function,
and FastAPI resolves the body parameter while solving dependencies — strictly
before the decorated function is invoked. The body is fully resident before the
limiter charges the request.

Two paths are covered, because a Content-Length check alone is a check the caller
can decline to make: a declared length is refused before a single byte is read,
and an undeclared one is caught as the bytes arrive.

Both mechanisms are driven against the middleware with a small ceiling, so they
are tested without allocating twenty-five megabytes to prove a comparison
happens. That was a deliberate trade and it was the wrong one: a stub downstream
app catches the middleware's exception in the middleware, while the real app
raises it inside FastAPI's body reader, whose `except Exception` clause rewrites
anything that is not an `HTTPException` into `400 There was an error parsing the
body`. Every test below the mechanism section passed against code that answered
400 in production. A live probe found it; the two end-to-end tests at the bottom
of this file are what keep it fixed, and they pay the megabytes on purpose.
"""

import json

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import MAX_REQUEST_BYTES, LimitRequestBody, app
from app.models.schemas import MAX_IMAGE_BASE64, MAX_IMAGES_PER_SCAN

transport = ASGITransport(app=app)

# The largest body the field caps permit, which the ceiling has to clear.
LARGEST_LEGITIMATE = MAX_IMAGES_PER_SCAN * MAX_IMAGE_BASE64


def _oversized() -> dict:
    """A body far past the ceiling, built cheaply so the test does not allocate a
    hundred megabytes to prove a comparison happens."""
    return {"images_base64": ["A" * (MAX_REQUEST_BYTES + 1024)], "image_base64": ""}


def _within_caps() -> dict:
    return {"images_base64": ["A" * 1000], "image_base64": ""}


# ── the ceiling has to clear what the field caps permit ───────────────────────


def test_the_ceiling_is_above_the_largest_body_the_caps_allow():
    """If someone raises `MAX_IMAGE_BASE64`, this fails until the ceiling moves
    with it. Asserted as a relationship so the two cannot drift apart silently."""
    assert MAX_REQUEST_BYTES > LARGEST_LEGITIMATE, (
        f"the ceiling ({MAX_REQUEST_BYTES}) is at or below the largest body the "
        f"field caps permit ({LARGEST_LEGITIMATE}), so legitimate traffic is refused"
    )


def test_the_ceiling_is_not_generous_beyond_that():
    """A ceiling set to gigabytes passes the test above while closing nothing."""
    assert MAX_REQUEST_BYTES < LARGEST_LEGITIMATE * 2, (
        "the ceiling is more than double the largest legitimate body, which "
        "leaves the amplification the caps were written to prevent"
    )


# ── the declared-length path, through the real app ────────────────────────────


@pytest.mark.asyncio
async def test_an_oversized_body_is_refused_before_it_is_buffered():
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/scan", json=_oversized())

    assert resp.status_code == 413, resp.text
    assert "too large" in resp.text.lower()


@pytest.mark.asyncio
async def test_a_body_within_the_caps_still_reaches_the_endpoint():
    """The overcorrection: refuse everything and the extension cannot scan at
    all. This is the assertion that makes the refusal one mean something."""
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/scan", json=_within_caps())

    assert resp.status_code != 413, "the ceiling is refusing a legitimate request"
    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_get_routes_are_untouched():
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")

    assert resp.status_code == 200


# ── the undeclared-length path, against the middleware directly ──────────────


async def _drive(headers, chunks, max_bytes=1000):
    """Run the middleware over a synthetic request and report what came back."""
    seen: list[dict] = []
    body_left = list(chunks)

    async def receive():
        if body_left:
            return {"type": "http.request", "body": body_left.pop(0), "more_body": True}
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        seen.append(message)

    async def downstream(scope, _receive, send_):
        while True:
            message = await _receive()
            if not message.get("more_body"):
                break
        await send_({"type": "http.response.start", "status": 200, "headers": []})
        await send_({"type": "http.response.body", "body": b"ok"})

    await LimitRequestBody(downstream, max_bytes=max_bytes)(
        {"type": "http", "method": "POST", "headers": headers}, receive, send
    )
    return seen


@pytest.mark.asyncio
async def test_a_body_with_no_content_length_is_caught_while_it_arrives():
    """A Content-Length check on its own is one the caller can decline to make.
    This is that case, and skipping it would leave the fix bypassable by anyone
    who sends a chunked body."""
    seen = await _drive(headers=[], chunks=[b"x" * 600, b"x" * 600])

    start = next(m for m in seen if m["type"] == "http.response.start")
    assert start["status"] == 413


@pytest.mark.asyncio
async def test_an_undeclared_body_under_the_ceiling_still_works():
    """The overcorrection on the undeclared path: counting every chunk must not
    refuse a request that fits."""
    seen = await _drive(headers=[], chunks=[b"x" * 600])

    start = next(m for m in seen if m["type"] == "http.response.start")
    assert start["status"] == 200


@pytest.mark.asyncio
async def test_a_declared_length_alone_is_enough_to_refuse():
    """Nothing is read at all in this case, which is the whole point: the
    declared check is a fast path, not the only defence."""
    reads: list[bool] = []

    async def receive():
        reads.append(True)
        return {"type": "http.request", "body": b"x" * 100, "more_body": False}

    seen: list[dict] = []

    async def send(message):
        seen.append(message)

    async def downstream(scope, _receive, send_):
        await send_({"type": "http.response.start", "status": 200, "headers": []})
        await send_({"type": "http.response.body", "body": b"ok"})

    await LimitRequestBody(downstream, max_bytes=50)(
        {"type": "http", "method": "POST", "headers": [(b"content-length", b"9999")]},
        receive,
        send,
    )

    start = next(m for m in seen if m["type"] == "http.response.start")
    assert start["status"] == 413
    assert reads == [], "the declared-length check read the body anyway"


@pytest.mark.asyncio
async def test_a_non_http_scope_passes_straight_through():
    """A websocket or lifespan scope has no body and no Content-Length; refusing
    it would break the server at startup rather than under attack."""
    seen: list[dict] = []

    async def send(message):
        seen.append(message)

    async def downstream(scope, receive, send_):
        await send_({"type": "websocket.accept"})

    await LimitRequestBody(downstream, max_bytes=1)(
        {"type": "websocket", "headers": []},
        lambda: None,
        send,
    )

    assert seen and seen[0]["type"] == "websocket.accept"


# ── the undeclared path, end to end ───────────────────────────────────────────


async def _drive_real_app(chunks, *, path="/api/scan", content_length: str | None = None):
    """Run the *real* app over a synthetic request with no Content-Length.

    `_drive` above substitutes a stub for the downstream app, which is the right
    way to test the counting cheaply but it means the body handler never runs.
    This one does not, which is why it needs twenty-five megabytes.

    Driven as a raw ASGI callable rather than through httpx because httpx's
    ASGITransport takes a `content` body and cannot express a stream, and an
    undeclared length *is* the case under test.
    """
    body_left = list(chunks)
    seen: list[dict] = []

    async def receive():
        if body_left:
            return {"type": "http.request", "body": body_left.pop(0), "more_body": True}
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        seen.append(message)

    headers = [(b"content-type", b"application/json")]
    if content_length is not None:
        headers.append((b"content-length", content_length.encode()))

    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "POST",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "root_path": "",
        "headers": headers,
        "client": ("203.0.113.9", 54321),
        "server": ("test", 80),
        "scheme": "http",
    }
    await app(scope, receive, send)
    start = next(m for m in seen if m["type"] == "http.response.start")
    body = b"".join(m.get("body", b"") for m in seen if m["type"] == "http.response.body")
    return start["status"], body


@pytest.mark.asyncio
async def test_a_chunked_oversized_body_reports_the_ceiling_not_a_parse_error():
    """The undeclared path, end to end, and the reason this file's earlier
    coverage was not enough.

    Every other test here drives a stub downstream app, so the middleware's
    exception is caught by the middleware. In the real app the exception is
    raised inside FastAPI's body reader, whose `except Exception` clause rewrites
    anything that is not an `HTTPException` into `400 There was an error parsing
    the body`. Production answered a syntax error for a body that was too large —
    the ceiling held, so memory was still bounded, but the caller was told the
    wrong thing about why, and a client retrying on a parse error would resend
    it forever.

    Asserted on the status *and* the detail, because a 413 from some other layer
    would satisfy a status-only check while saying nothing about the message.
    """
    chunk = b"A" * (2 * 1024 * 1024)
    status, body = await _drive_real_app([chunk] * 14)  # 28 MB, no Content-Length

    assert status == 413, f"expected the ceiling, got {status}: {body[:200]!r}"
    assert b"too large" in body
    assert b"parsing the body" not in body


@pytest.mark.asyncio
async def test_a_chunked_body_under_the_ceiling_is_not_refused_by_it():
    """The overcorrection for the fix above, on the same path.

    `_BodyTooLarge` is now an `HTTPException`, which FastAPI's body reader
    re-raises untouched rather than converting. That only helps if the exception
    is raised *when the ceiling is actually passed* — so this is the check that
    the subclass did not turn the ceiling into a blanket refusal. The body is
    deliberately malformed, so a request that reaches the parser answers 400
    rather than 413: the two are distinguishable, which is the point.
    """
    status, _ = await _drive_real_app([b"{not json at all"])

    assert status != 413, "the ceiling refused a body four bytes under it"
    assert status in (400, 422), f"expected the parser to answer, got {status}"
