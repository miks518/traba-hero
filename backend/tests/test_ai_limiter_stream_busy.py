"""The AI limiter under concurrent scans.

Field incident 2026-10-30: four users scanned at once. Two got responses; two
got "Scan Interrupted" and the backend logged `AI limiter acquire timeout
after 10.0s: 2 active, 2 queued` followed by `Exception in ASGI application`.
Two defects, both pinned here:

1. The acquire timeout (10s) is shorter than one active AI call, so a queued
   scan can never win a slot — the queue is decorative and every user past
   `max_concurrent` fails whenever all slots are busy. Pinned as a
   configuration relationship: a waiter must be willing to wait at least as
   long as any active call is allowed to run.
2. The 503 from `acquire()` is raised inside the SSE response generator,
   after the 200 and headers are already sent. The exception escapes as an
   ASGI error and the client sees a truncated stream instead of a clean
   "server busy" message. The route must degrade to an in-stream error event
   (the verify and offer flows already do this through their own catch-alls).

Each test installs a fresh AILimiter instance into the route: the production
singleton binds its asyncio.Semaphore to the first event loop that awaits it,
which is correct for the single-loop server but poisonous across
pytest-asyncio's per-test loops.
"""

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from app.ai_limiter import AILimiter
from app.config import settings
from app.main import app

transport = ASGITransport(app=app)

PAYLOAD = {"text": "Sales associate wanted, PHP 25k"}


@pytest.fixture
def fresh_limiter(monkeypatch):
    """A per-test limiter wired into the scan routes, so slot state never
    leaks across pytest-asyncio's event loops."""
    limiter = AILimiter(
        max_concurrent=2,
        max_queue_depth=10,
        acquire_timeout=0.2,
        call_timeout=30.0,
    )
    monkeypatch.setattr("app.routers.scan.ai_limiter", limiter)
    return limiter


async def _read_stream(client: AsyncClient, payload: dict = PAYLOAD) -> str:
    chunks: list[str] = []
    async with client.stream("POST", "/api/scan-text", json=payload) as resp:
        assert resp.status_code == 200, f"expected SSE 200, got {resp.status_code}"
        async for chunk in resp.aiter_text():
            chunks.append(chunk)
    return "".join(chunks)


def test_acquire_timeout_covers_at_least_one_call():
    """The queue is only real if a waiter is willing to wait as long as any
    active call may run. With the shipped 10s default against a 120s call
    bound, every queued scan timed out before the slot it wanted could free —
    the 2/4 outcome in the field."""
    assert settings.ai_acquire_timeout >= settings.ai_call_timeout, (
        f"acquire timeout ({settings.ai_acquire_timeout}s) is shorter than one "
        f"AI call ({settings.ai_call_timeout}s): queued scans time out before "
        "the slot they wait for can free, so the queue never runs its waiters"
    )


@pytest.mark.asyncio
async def test_busy_server_degrades_to_a_clean_error_event(fresh_limiter):
    """Both slots busy: the scan must yield an in-stream error event, not an
    ASGI crash. Before the fix this raised inside the response generator and
    the client saw a truncated stream ('Scan Interrupted')."""
    await fresh_limiter.acquire()
    await fresh_limiter.acquire()

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        body = await _read_stream(client)

    assert '"type": "error"' in body, f"no in-stream error event: {body!r}"
    assert "busy" in body.lower(), f"error event lost the busy message: {body!r}"


@pytest.mark.asyncio
async def test_a_queued_scan_wins_a_slot_when_one_frees(fresh_limiter):
    """The queue must be real: a scan that waits while both slots are held
    still runs when a slot frees, provided the timeout covers the wait."""
    fresh_limiter.acquire_timeout = 5.0
    await fresh_limiter.acquire()
    await fresh_limiter.acquire()
    body = ""
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:

            async def scan_later():
                nonlocal body
                await asyncio.sleep(0.3)
                body = await _read_stream(client)

            task = asyncio.create_task(scan_later())
            await asyncio.sleep(0.15)  # the scan is now queued behind both slots
            fresh_limiter.release()  # a slot frees while the scan is waiting
            await asyncio.wait_for(task, timeout=30)
    finally:
        fresh_limiter.release()

    assert '"type": "result"' in body, f"queued scan never ran: {body!r}"
    assert '"type": "error"' not in body, f"queued scan errored: {body!r}"


@pytest.mark.asyncio
async def test_queue_overflow_also_degrades_to_a_clean_error_event(fresh_limiter):
    """Queue full must be a clean in-stream error too — same shape as the
    timeout path, for the same reason. With the queue depth at zero, the
    route's own acquire is refused before it can wait — the burst-overflow
    rejection, at any slot state."""
    fresh_limiter.max_queue_depth = 0

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        body = await _read_stream(client)

    assert '"type": "error"' in body, f"no in-stream error event: {body!r}"
    assert "capacity" in body.lower(), f"error event lost the capacity message: {body!r}"


@pytest.mark.asyncio
async def test_acquire_waits_for_a_released_slot():
    """Unit pin on the mechanism: an acquire that starts while both slots are
    held completes once a slot is released, provided the timeout covers the
    wait."""
    limiter = AILimiter(
        max_concurrent=2, max_queue_depth=10, acquire_timeout=5.0, call_timeout=30.0
    )
    await limiter.acquire()
    await limiter.acquire()
    waiter = asyncio.create_task(limiter.acquire())
    await asyncio.sleep(0.1)
    assert not waiter.done(), "waiter acquired while both slots were held"
    limiter.release()
    await asyncio.wait_for(waiter, timeout=2)
    limiter.release()
