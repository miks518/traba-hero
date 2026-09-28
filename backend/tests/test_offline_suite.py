"""Guards that keep the default suite offline (AGENTS.md Test Safety).

The suite used to hit the real OpenRouter and DuckDuckGo endpoints from
auth-only tests, which spent provider credits and tripped rate limits. These
tests fail if that ever regresses. The search boundary is now Tavily.
"""
import socket

import pytest
from app.routers import scan as scan_router

from .conftest import (
    FAKE_COMPANY_NAME,
    FAKE_JOB_SUMMARY,
    REAL_AI_CHAT,
    REAL_AI_STREAM,
    ExternalNetworkBlocked,
)


def test_external_dns_lookup_is_blocked():
    with pytest.raises(ExternalNetworkBlocked):
        socket.getaddrinfo("openrouter.ai", 443)


def test_loopback_dns_lookup_is_allowed():
    assert socket.getaddrinfo("127.0.0.1", 8000)


@pytest.mark.asyncio
async def test_real_http_client_cannot_reach_the_provider():
    """The guard intercepts the real client library, not just direct calls."""
    import httpx

    with pytest.raises(ExternalNetworkBlocked):
        async with httpx.AsyncClient(timeout=5) as client:
            await client.get("https://openrouter.ai/api/v1/models")


def test_ai_boundary_is_not_the_real_client():
    import app.services.lm_client as lm

    assert scan_router.chat_stream_pieces is not REAL_AI_STREAM
    assert scan_router.chat is not REAL_AI_CHAT
    # The lm_client globals are patched too, so chat_json/chat_resume/
    # chat_match cannot reach the provider through their own reference.
    assert lm.chat is not REAL_AI_CHAT
    assert lm.chat_stream_pieces is not REAL_AI_STREAM


def test_search_boundary_is_not_the_real_service():
    """The live search boundary is Tavily, reached over httpx.

    It used to be the ddgs DDGS class. The rebuild replaced it, and this test
    is what proves the suite cannot reach a provider.
    """
    from app.services import search as search_mod

    # conftest replaces httpx.post on the shared httpx module, so the real
    # transport is not what search() would call.
    assert search_mod.httpx.post.__module__.endswith("conftest")
    assert search_mod.settings.tavily_api_key == "tvly-offline-test"


@pytest.mark.asyncio
async def test_fake_stream_yields_the_deterministic_scan_response():
    import json

    from app.routers.scan import _scan_event_stream

    events = []
    async for event in _scan_event_stream(
        [{"role": "user", "content": "x"}], endpoint="test-offline"
    ):
        # The stream yields raw SSE frames, e.g. 'data: {"type": ...}'
        if event.startswith("data: "):
            events.append(json.loads(event[len("data: "):]))

    result = next(e["data"] for e in events if e.get("type") == "result")
    assert result["job_summary"] == FAKE_JOB_SUMMARY
    assert result["valid"] is True
    # The fake data carries one red flag and a company name, so the mocked
    # response exercises flag parsing and the verification guardrail.
    assert [f["flag"] for f in result["red_flags"]] == ["Application fee requested"]
    assert result["verification_context"]["company_name"] == FAKE_COMPANY_NAME
