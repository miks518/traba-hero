"""The search-debug surface is removed.

Built to diagnose one bug: a wrong-but-successful Tavily response that was
indistinguishable from a parse fault, because the tab reported only parsed
results. The ranking fix that resolved it is in search.py and is covered by
test_search.py, so the diagnostic has served its purpose.

These tests assert absence. That is the correct shape for a removal — a test
failing when the debug code comes *back* is the one worth keeping, since
resurrecting a diagnostics endpoint on a shipped extension is a small leak of
the provider's raw response body.
"""
import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (REPO / rel).read_text(encoding="utf-8")


def test_the_debug_endpoint_is_gone():
    """No route may answer /api/debug/search."""
    from app.main import app

    paths = {getattr(r, "path", "") for r in app.routes}
    assert "/api/debug/search" not in paths


def test_the_endpoint_reports_not_found_over_http():
    from app.main import app
    from httpx import AsyncClient, ASGITransport
    import asyncio

    async def call():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post(
                "/api/debug/search",
                json={"query": "Acme"},
                headers={"X-Trabahero-Client-Key": "test-secret-key"},
            )
            return r.status_code

    assert asyncio.run(call()) == 404


def test_no_search_debug_request_model():
    from app.models import schemas

    assert not hasattr(schemas, "SearchDebugRequest")


@pytest.mark.parametrize(
    "rel,pattern",
    [
        ("entrypoints/sidepanel/data/content.ts", r"id:\s*'search'"),
        ("entrypoints/sidepanel/types/index.ts", r"debugPrompt"),
        ("entrypoints/sidepanel/lib/api.ts", r"debugSearchStream"),
        ("entrypoints/sidepanel/App.tsx", r"SearchDebugView"),
        ("entrypoints/sidepanel/components/scan/VerificationSection.tsx", r"SearchRawPanel"),
        ("entrypoints/sidepanel/views/ScamScanView.tsx", r"debugPrompt"),
    ],
)
def test_frontend_debug_symbols_are_gone(rel, pattern):
    source = _read(rel)
    assert not re.search(pattern, source), f"{rel} still references {pattern}"


@pytest.mark.parametrize(
    "rel",
    [
        "entrypoints/sidepanel/views/SearchDebugView.tsx",
        "entrypoints/sidepanel/components/scan/SearchRawPanel.tsx",
    ],
)
def test_debug_view_files_are_deleted(rel):
    assert not (REPO / rel).exists(), f"{rel} should have been removed"


def test_backend_stops_shipping_the_prompt_to_the_client():
    """`debug_prompt` sent the exact model prompt over the wire to the browser.

    It also carried whatever the search returned, so it was a second copy of
    untrusted web text in a response the extension renders.
    """
    source = _read("backend/app/services/scanner/verification_flow.py")
    assert "debug_prompt" not in source


def test_the_search_outcome_no_longer_carries_the_raw_provider_body():
    """`raw_response` existed only so the debug tab could show the provider's body.

    Nothing in the production path reads it. The outcome already reports the
    classified error string, which is what a log needs.
    """
    from app.services.search import SearchOutcome

    assert not hasattr(SearchOutcome(), "raw_response")


def test_navigation_is_back_to_two_tabs():
    # Scoped to NAV_TABS: content.ts also declares FOOTER_LINKS, whose entries
    # are unrelated to the side navigation.
    source = _read("entrypoints/sidepanel/data/content.ts")
    nav = re.search(r"NAV_TABS[^=]*=\s*\[(.*?)\];", source, re.S)
    assert nav, "NAV_TABS must be declared"
    ids = re.findall(r"id:\s*'(\w+)'", nav.group(1))
    assert ids == ["scan", "match"], f"expected the two real tabs, found {ids}"
