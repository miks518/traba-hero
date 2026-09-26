"""Tests for extension-to-backend request authentication (Task 1.1)."""
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

from .conftest import FAKE_JOB_SUMMARY

transport = ASGITransport(app=app)
HEADERS = {"X-Trabahero-Client-Key": "test-secret-key"}
WRONG_HEADERS = {"X-Trabahero-Client-Key": "wrong-key"}


# ── Health endpoint: no auth required ──────────────────────────────────

@pytest.mark.asyncio
async def test_health_no_auth_needed():
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ── POST /api/scan: auth checks ────────────────────────────────────────

@pytest.mark.asyncio
async def test_scan_missing_key_returns_401(scan_payload):
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/scan", json=scan_payload)
    assert resp.status_code == 401
    assert "missing client key" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_scan_wrong_key_returns_401(scan_payload):
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/scan", json=scan_payload, headers=WRONG_HEADERS)
    assert resp.status_code == 401
    assert "invalid client key" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_scan_correct_key_passes_auth(scan_payload):
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/scan", json=scan_payload, headers=HEADERS)
    # Auth passes and the offline AI fixture produces a stream — NOT 401
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]


# ── POST /api/scan-text: auth checks ───────────────────────────────────

@pytest.mark.asyncio
async def test_scan_text_missing_key_returns_401(text_payload):
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/scan-text", json=text_payload)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_scan_text_wrong_key_returns_401(text_payload):
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/scan-text", json=text_payload, headers=WRONG_HEADERS)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_scan_text_correct_key_passes_auth(text_payload):
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/scan-text", json=text_payload, headers=HEADERS)
    assert resp.status_code != 401
    # AI is faked by the offline fixture, so the body must be the fake payload.
    # This also proves a valid-key request never reaches the real provider.
    assert FAKE_JOB_SUMMARY in resp.text


# ── POST /api/analyze-resume: auth checks ──────────────────────────────

@pytest.mark.asyncio
async def test_analyze_resume_missing_key_returns_401(resume_payload):
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/analyze-resume", json=resume_payload)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_analyze_resume_wrong_key_returns_401(resume_payload):
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/analyze-resume", json=resume_payload, headers=WRONG_HEADERS)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_analyze_resume_correct_key_passes_auth(resume_payload):
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/analyze-resume", json=resume_payload, headers=HEADERS)
    assert resp.status_code != 401


# ── POST /api/match-resume: auth checks ────────────────────────────────

@pytest.mark.asyncio
async def test_match_missing_key_returns_401(match_payload):
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/match-resume", json=match_payload)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_match_wrong_key_returns_401(match_payload):
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/match-resume", json=match_payload, headers=WRONG_HEADERS)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_match_correct_key_passes_auth(match_payload):
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/match-resume", json=match_payload, headers=HEADERS)
    assert resp.status_code != 401
