"""Tests for the Tavily search module (app/services/search.py).

The load-bearing property: a failed search and a search that found nothing must
be distinguishable by the caller. `ok` and `results` are independent.
"""
import asyncio
import json
import time

import httpx

from app.main import app
from app.services.search import (
    SearchOutcome,
    SearchResult,
    build_query,
    clean_company_name,
    extract_company_name,
    is_valid_company_name,
    search,
)


class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx
            raise httpx.HTTPStatusError(
                f"status {self.status_code}", request=None, response=None
            )

    def json(self):
        return self._payload


TAVILY_OK = {
    "results": [
        {
            "title": "Jollibee Foods Corporation",
            "url": "https://jollibee.com.ph",
            "content": "A Philippine multinational fast food chain.",
            "score": 0.91,
        },
        {
            "title": "SEC Registration CS201500123",
            "url": "https://companieshouse.ph/jfc",
            "content": "Registered with SEC number CS201500123.",
            "score": 0.77,
        },
    ],
    "credits_used": 1,
}


class TestSearchResultShape:
    def test_maps_tavily_fields_onto_search_result(self, monkeypatch):
        import app.services.search as mod

        captured = {}

        def fake_post(url, json=None, timeout=None, headers=None):
            captured["url"] = url
            captured["json"] = json
            return FakeResponse(TAVILY_OK)

        monkeypatch.setattr(mod.httpx, "post", fake_post)
        outcome = mod.search("Jollibee", 5)

        assert outcome.ok is True
        assert outcome.error == ""
        assert len(outcome.results) == 2
        first = outcome.results[0]
        assert isinstance(first, SearchResult)
        assert first.title == "Jollibee Foods Corporation"
        assert first.url == "https://jollibee.com.ph"
        # Tavily calls the snippet 'content'; ours is 'snippet'.
        assert first.snippet == "A Philippine multinational fast food chain."
        assert first.score == 0.91

    def test_sends_the_api_key_in_the_body(self, monkeypatch):
        import app.services.search as mod

        captured = {}

        def fake_post(url, json=None, timeout=None, headers=None):
            captured.update(json or {})
            return FakeResponse(TAVILY_OK)

        monkeypatch.setattr(mod.settings, "tavily_api_key", "tvly-test")
        monkeypatch.setattr(mod.httpx, "post", fake_post)
        mod.search("Jollibee", 5)

        assert captured["api_key"] == "tvly-test"
        assert captured["query"] == "Jollibee"
        assert captured["max_results"] == 5
        assert captured["search_depth"] == "basic"


class TestFailureIsNotAbsence:
    """The defect that made the old module untrustworthy."""

    def test_http_error_is_a_failure_not_an_empty_success(self, monkeypatch):
        import app.services.search as mod

        def fake_post(url, json=None, timeout=None, headers=None):
            return FakeResponse({"detail": "Unauthorized"}, status=401)

        monkeypatch.setattr(mod.settings, "tavily_api_key", "tvly-test")
        monkeypatch.setattr(mod.httpx, "post", fake_post)
        outcome = mod.search("Jollibee", 5)

        assert outcome.ok is False
        assert outcome.results == []
        assert "401" in outcome.error

    def test_empty_result_set_is_a_success_with_no_results(self, monkeypatch):
        """A 200 with zero results means the company has no footprint.

        This is a finding, not a malfunction, and must not read as one.
        """
        import app.services.search as mod

        def fake_post(url, json=None, timeout=None, headers=None):
            return FakeResponse({"results": [], "credits_used": 1})

        monkeypatch.setattr(mod.settings, "tavily_api_key", "tvly-test")
        monkeypatch.setattr(mod.httpx, "post", fake_post)
        outcome = mod.search("Nowhere Trading PH", 5)

        assert outcome.ok is True
        assert outcome.error == ""
        assert outcome.results == []

    def test_missing_api_key_is_a_failure(self, monkeypatch):
        import app.services.search as mod

        def explode(*a, **kw):
            raise AssertionError("must not call the provider without a key")

        monkeypatch.setattr(mod.settings, "tavily_api_key", "")
        monkeypatch.setattr(mod.httpx, "post", explode)
        outcome = mod.search("Jollibee", 5)

        assert outcome.ok is False
        assert outcome.results == []
        assert "TAVILY_API_KEY" in outcome.error

    def test_transport_exception_is_caught(self, monkeypatch):
        import app.services.search as mod

        def boom(*a, **kw):
            raise RuntimeError("connection reset")

        monkeypatch.setattr(mod.settings, "tavily_api_key", "tvly-test")
        monkeypatch.setattr(mod.httpx, "post", boom)
        outcome = mod.search("Jollibee", 5)

        assert outcome.ok is False
        assert "connection reset" in outcome.error

    def test_malformed_body_is_a_failure(self, monkeypatch):
        """A body without a usable results list means the provider changed shape.

        Reporting that as "the company has no footprint" is the exact defect
        this module exists to prevent: a parse fault indistinguishable from a
        finding about a real employer.
        """
        import app.services.search as mod

        for body in (
            {"unexpected": "shape"},
            {"results": None},
            {"error": {"code": "invalid_api_key"}},
            {"results": {"not": "a list"}},
        ):
            def fake_post(url, json=None, timeout=None, headers=None, _b=body):
                return FakeResponse(_b)

            monkeypatch.setattr(mod.settings, "tavily_api_key", "tvly-test")
            monkeypatch.setattr(mod.httpx, "post", fake_post)
            outcome = mod.search("Jollibee", 5)

            assert outcome.ok is False, f"{body} must not read as a clean company"
            assert outcome.results == []
            assert outcome.error

    def test_an_explicitly_empty_list_is_a_success(self, monkeypatch):
        """{"results": []} is a finding; {"results": None} is a parse fault."""
        import app.services.search as mod

        def fake_post(url, json=None, timeout=None, headers=None):
            return FakeResponse({"results": [], "credits_used": 1})

        monkeypatch.setattr(mod.settings, "tavily_api_key", "tvly-test")
        monkeypatch.setattr(mod.httpx, "post", fake_post)
        outcome = mod.search("Nowhere PH", 5)

        assert outcome.ok is True
        assert outcome.results == []

    def test_a_non_dict_body_does_not_raise(self, monkeypatch):
        """search() must never raise; the debug endpoint has no exception handler."""
        import app.services.search as mod

        def fake_post(url, json=None, timeout=None, headers=None):
            return FakeResponse(["a", "list", "not", "an", "object"])

        monkeypatch.setattr(mod.settings, "tavily_api_key", "tvly-test")
        monkeypatch.setattr(mod.httpx, "post", fake_post)
        outcome = mod.search("Jollibee", 5)

        assert outcome.ok is False
        assert outcome.error

    def test_latency_is_measured(self, monkeypatch):
        import app.services.search as mod

        def fake_post(url, json=None, timeout=None, headers=None):
            time.sleep(0.05)
            return FakeResponse(TAVILY_OK)

        monkeypatch.setattr(mod.settings, "tavily_api_key", "tvly-test")
        monkeypatch.setattr(mod.httpx, "post", fake_post)
        outcome = mod.search("Jollibee", 5)

        # Latency is rounded to milliseconds, so assert against a threshold the
        # fake's sleep comfortably clears rather than against zero.
        assert outcome.latency >= 0.01, f"latency was {outcome.latency}"


class TestBuildQuery:
    def test_appends_philippines(self):
        assert build_query("Jollibee") == "Jollibee Philippines"

    def test_is_the_only_query_shape(self):
        """One query. No category suffixes — that is the point of the rebuild."""
        q = build_query("Jollibee Foods Corporation")
        assert q.count("Philippines") == 1
        for banned in ("SEC", "scam", "reviews", "fraud"):
            assert banned not in q


class TestRawProviderBody:
    """The debug tab must show the provider's body, not our re-serialisation.

    The tab exists to make a mis-ranked or mis-parsed response visible. If it
    echoed our own normalised output, a parse fault would render as a clean
    empty result — the failure it was built to catch.
    """

    def test_outcome_carries_the_provider_body(self, monkeypatch):
        import app.services.search as mod

        def fake_post(url, json=None, timeout=None, headers=None):
            return FakeResponse({
                "results": [{"title": "T", "url": "u", "content": "S", "score": 0.5}],
                "credits_used": 1,
                "request_id": "abc123",
            })

        monkeypatch.setattr(mod.settings, "tavily_api_key", "tvly-test")
        monkeypatch.setattr(mod.httpx, "post", fake_post)
        outcome = mod.search("Jollibee", 5)

        assert outcome.ok is True
        assert outcome.raw_response.get("request_id") == "abc123"
        assert outcome.raw_response.get("credits_used") == 1

    def test_raw_body_survives_a_parse_fault(self, monkeypatch):
        """A shape change must still show the body that caused it."""
        import app.services.search as mod

        def fake_post(url, json=None, timeout=None, headers=None):
            return FakeResponse({"results": None, "detail": "quota exceeded"})

        monkeypatch.setattr(mod.settings, "tavily_api_key", "tvly-test")
        monkeypatch.setattr(mod.httpx, "post", fake_post)
        outcome = mod.search("Jollibee", 5)

        assert outcome.ok is False
        assert outcome.raw_response.get("detail") == "quota exceeded"
    def test_valid_names(self):
        assert is_valid_company_name("Acme Corp") is True
        assert is_valid_company_name("Jollibee Foods Corporation") is True
        assert is_valid_company_name("San Miguel Brewery Inc.") is True

    def test_placeholders_rejected(self):
        for bad in ("Not stated", "N/A", "unknown", "None", "", None, "company"):
            assert is_valid_company_name(bad) is False

    def test_clean_keeps_a_plain_name(self):
        assert clean_company_name("Jollibee Foods Corporation") == "Jollibee Foods Corporation"

    def test_clean_keeps_the_client_from_a_recruiter_pair(self):
        got = clean_company_name("Vikings / Silvergreen Manpower Services Corporation")
        assert got == "Silvergreen Manpower Services Corporation"

    def test_clean_drops_a_leading_article(self):
        assert clean_company_name("The Acme Company") == "Acme Company"

    def test_clean_rejects_placeholders(self):
        assert clean_company_name("Not stated") == ""

    def test_extract_finds_a_name(self):
        assert extract_company_name("Apply now at Google Philippines") == "Google Philippines"

    def test_extract_returns_none_when_absent(self):
        assert extract_company_name("Apply now, good salary, call this number") is None


class TestMaxResultsComesFromSettings:
    def test_default_max_results_is_read_from_settings(self, monkeypatch):
        import app.services.search as mod

        captured = {}

        def fake_post(url, json=None, timeout=None, headers=None):
            captured.update(json or {})
            return FakeResponse({"results": []})

        monkeypatch.setattr(mod.settings, "tavily_api_key", "tvly-test")
        monkeypatch.setattr(mod.settings, "tavily_max_results", 8)
        monkeypatch.setattr(mod.httpx, "post", fake_post)
        mod.search("Jollibee")

        assert captured["max_results"] == 8


class TestScanPathDoesNotSearch:
    """Online evidence belongs to /api/verify only.

    The scan reports on the posting. Feeding it web results put two prompts
    with different guardrail rules on the same data, and cost eight searches
    per text scan.
    """

    def test_scan_text_route_body_has_no_search_call(self):
        import app.routers.scan as router

        source = open(router.__file__, encoding="utf-8").read()
        body = source.split("async def scan_text")[1].split("\n@router")[0]
        for banned in ("search_job_posting", "verify_company", "search_job_posting_data"):
            assert banned not in body, f"the scan-text route still calls {banned}"

    def test_scan_response_has_no_web_search_field(self):
        from app.models.schemas import ScanResponse

        assert "web_search" not in ScanResponse.model_fields


class TestDebugEndpoint:
    def test_streams_the_raw_provider_response(self):
        """A mis-ranked SERP must be visible, not inferred.

        The previous tab reported only parsed results, so a wrong-but-successful
        response was indistinguishable from a parsing mistake — which is exactly
        how the wrong-results bug went undiagnosed.
        """
        import inspect
        import app.routers.scan as router

        source = inspect.getsource(router.debug_search)
        for event in ('"meta"', '"result"', '"raw"', '"outcome"', '"done"'):
            assert event in source, f"the debug endpoint must emit {event}"
        assert "search_with_diagnostics" not in source, "the debug tab must use the new provider"
        assert "_ddg_once" not in source, "the debug tab must not walk engines"

    def test_raw_body_is_the_verbatim_result_payload(self, monkeypatch):
        """The raw event must be the provider's body, not our re-serialisation.

        Echoing our own normalised output would hide the exact failure the tab
        was built for: a shape change would render as a clean empty result.
        """
        import app.routers.scan as router
        from app.services import search as mod
        from app.services.search import SearchOutcome, SearchResult

        captured = []

        async def drive():
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                async with client.stream(
                    "POST", "/api/debug/search",
                    json={"query": "Acme", "max_results": 3},
                    headers={"X-Trabahero-Client-Key": "test-secret-key"},
                ) as resp:
                    async for line in resp.aiter_lines():
                        if line.startswith("data: "):
                            captured.append(json.loads(line[6:]))

        provider_body = {
            "results": [{"title": "A", "url": "https://a", "content": "S", "score": 0.5}],
            "credits_used": 1,
            "request_id": "req-123",
        }
        monkeypatch.setattr(
            "app.routers.scan.search",
            lambda *a, **k: SearchOutcome(
                results=[SearchResult("A", "https://a", "S", 0.5)],
                ok=True, latency=0.1, raw_response=provider_body,
            ),
        )
        asyncio.run(drive())

        raw = [e for e in captured if e.get("type") == "raw"]
        assert raw, "the endpoint must emit a raw event"
        body = json.loads(raw[0]["body"])
        # The provider's own fields survive, not just the ones we parse.
        assert body["request_id"] == "req-123"
        assert body["credits_used"] == 1

        outcome = [e for e in captured if e.get("type") == "outcome"]
        assert outcome and outcome[0]["ok"] is True
        assert any(e.get("type") == "done" for e in captured), "the stream must terminate"

    def test_a_failed_search_still_streams_outcome_and_done(self):
        """The debug tab must show the failure, not die mid-stream."""
        import inspect
        import app.routers.scan as router

        source = inspect.getsource(router.debug_search)
        assert "search_with_diagnostics" not in source
        assert "try:" not in source.split("async def _stream")[1], (
            "the debug stream must not wrap the search in a bare try that "
            "swallows the outcome; search() reports failure in the outcome"
        )
