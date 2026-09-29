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
    _parse_domains,
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
        assert captured["search_depth"] == "advanced"


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

    def test_strips_a_corporate_suffix(self):
        """A literal 'Corporation' dilutes a rare name.

        Searching the suffix verbatim drags in unrelated companies whose names
        end the same way, so the distinctive part of the name gets less weight.
        """
        assert build_query("MIX Market Integrated Xploration Corporation") == (
            "MIX Market Integrated Xploration Philippines"
        )

    def test_strips_each_supported_suffix(self):
        cases = [
            ("Jollibee Foods Corporation", "Jollibee Foods"),
            ("Jollibee Foods Corp", "Jollibee Foods"),
            ("Jollibee Foods Corp.", "Jollibee Foods"),
            ("Jollibee Foods Inc", "Jollibee Foods"),
            ("Jollibee Foods Incorporated", "Jollibee Foods"),
            ("Jollibee Foods Co", "Jollibee Foods"),
            ("Jollibee Foods LLC", "Jollibee Foods"),
        ]
        for name, expected_stem in cases:
            assert build_query(name) == f"{expected_stem} Philippines", name

    def test_suffix_stripping_respects_word_boundaries(self):
        """'Co' is only a suffix as a whole word.

        A substring match would turn 'Coca-Cola' into 'Coca-' and 'Incorporated
        Data' into 'Data', silently searching a different company.
        """
        for name in ("Coca-Cola Bottlers", "Concordia Trading", "Incorporated Systems PH"):
            assert build_query(name) == f"{name} Philippines", name

    def test_a_name_that_is_only_a_suffix_is_left_intact(self):
        """Stripping must not empty the query.

        'Corporation' alone strips to nothing, which would search for the
        geographic term on its own and return results about any company.
        """
        for name in ("Corporation", "Inc", "Co"):
            assert build_query(name) == f"{name} Philippines", name

    def test_does_not_double_the_anchor(self):
        """A name that already names the country is not anchored twice."""
        assert build_query("Jollibee Philippines") == "Jollibee Philippines"


class TestSettingsDefaultTestsIgnoreTheLocalEnvFile:
    """    A default assertion must read the code's default, not the developer's.

    `Settings()` loads `backend/.env`, so asserting on it tests the local
    environment rather than the shipped default: it passes only while the two
    happen to agree, and fails the moment a developer edits their own .env.
    Worse, a failing assertion prints the whole settings repr — including the
    live `AI_API_KEY` — into the test output. `_env_file=None` reads the class
    defaults instead, which is what each of these needs to assert.

    Note what that does and does not bypass: the env *file* is skipped, but a
    real OS environment variable still wins, because pydantic-settings applies
    those after the class defaults. The production module is unaffected — it
    wants the deployed value — and only these tests pass `_env_file=None`.
    """

    def test_the_default_is_asserted_without_reading_the_env_file(self, tmp_path):
        from app.config import Settings

        disagreeing = tmp_path / ".env"
        disagreeing.write_text("TAVILY_MAX_RESULTS=9\n", encoding="utf-8")

        assert Settings(_env_file=disagreeing).tavily_max_results == 9
        assert Settings(_env_file=None).tavily_max_results == 4

    def test_a_real_environment_variable_still_overrides_the_default(self, monkeypatch):
        """`_env_file=None` skips the file, not the environment.

        Worth pinning because the fix above looks like it isolates settings
        from the environment, and it does not. A deployment exporting
        TAVILY_MAX_RESULTS must still win over the shipped default.
        """
        from app.config import Settings

        monkeypatch.setenv("TAVILY_MAX_RESULTS", "9")

        assert Settings(_env_file=None).tavily_max_results == 9


class TestSearchSettingsAreConfigurable:
    """The credit trade is a deployment decision, not a code constant.

    Advanced depth costs 2 credits against basic's 1, which halves the
    1,000/month free budget. That is the right default for a niche lookup and
    the wrong default for a deployment being run down its quota, so the knob
    belongs in the environment where it can be changed without a redeploy of
    the code.
    """

    def _capture(self, monkeypatch, **overrides):
        import app.services.search as mod

        captured = {}

        def fake_post(url, json=None, timeout=None, headers=None):
            captured.update(json or {})
            return FakeResponse(TAVILY_OK)

        monkeypatch.setattr(mod.settings, "tavily_api_key", "tvly-test")
        monkeypatch.setattr(mod.httpx, "post", fake_post)
        for key, value in overrides.items():
            monkeypatch.setattr(mod.settings, key, value)
        mod.search("Jollibee", 5)
        return captured

    def test_depth_is_read_from_settings(self, monkeypatch):
        captured = self._capture(monkeypatch, tavily_search_depth="basic")
        assert captured["search_depth"] == "basic"

    def test_depth_defaults_to_advanced(self):
        """A deployment that sets nothing keeps the better recall."""
        from app.config import Settings

        assert Settings(_env_file=None).tavily_search_depth == "advanced"

    def test_country_is_read_from_settings(self, monkeypatch):
        captured = self._capture(monkeypatch, tavily_country="united kingdom")
        assert captured["country"] == "united kingdom"

    def test_country_defaults_to_philippines(self):
        from app.config import Settings

        assert Settings(_env_file=None).tavily_country == "philippines"

    def test_an_invalid_depth_falls_back_rather_than_being_sent(self, monkeypatch):
        """A typo must not become a provider error for every verification.

        Tavily would reject an unrecognised depth, turning a configuration
        mistake into a search failure reported to the user as a company that
        cannot be looked up.
        """
        import app.services.search as mod

        captured = self._capture(monkeypatch, tavily_search_depth="advnaced")

        assert captured["search_depth"] in {"basic", "advanced"}
        assert captured["search_depth"] == mod.settings.tavily_search_depth_fallback

    def test_a_blank_country_is_omitted_rather_than_sent_empty(self, monkeypatch):
        """An empty boost value is a misconfiguration, not a country.

        Sending country="" would either be rejected or silently behave as no
        boost, so it is dropped and the plain query is issued.
        """
        captured = self._capture(monkeypatch, tavily_country="   ")

        assert "country" not in captured

    def test_exclude_domains_is_read_from_settings(self, monkeypatch):
        captured = self._capture(monkeypatch, tavily_exclude_domains="pinterest.com")
        assert captured["exclude_domains"] == ["pinterest.com"]

    def test_a_comma_separated_list_is_split(self, monkeypatch):
        captured = self._capture(
            monkeypatch, tavily_exclude_domains="pinterest.com, quora.com"
        )
        assert captured["exclude_domains"] == ["pinterest.com", "quora.com"]

    def test_exclude_domains_defaults_to_wikipedia_only(self):
        """One entry ships by default; the rest is a deployment decision.

        The knob exists so noise can be dropped without touching the sources
        the country boost targets, which is why its default is a single
        unreliable-by-construction domain rather than a broad list.
        """
        from app.config import Settings

        assert _parse_domains(Settings(_env_file=None).tavily_exclude_domains) == [
            "wikipedia.org"
        ]

    def test_the_default_list_excludes_wikipedia(self):
        """An encyclopedia page is not a source, whatever it says.

        Wikipedia is crowd-editable and unattributed, so a company entry is not
        evidence of anything about the company — and a panel that cites it puts
        a defensible check behind a claim nobody can trace. It is excluded
        without ceremony: the entry is wrong often enough to be noise, and
        citing it invites the question it cannot answer.
        """
        from app.config import Settings

        settings = Settings(_env_file=None)
        assert "wikipedia.org" in _parse_domains(settings.tavily_exclude_domains)

    def test_the_default_list_keeps_the_sources_the_boost_targets(self):
        """Excluding noise must not touch what the country boost exists for.

        JobStreet, Indeed PH, and city PESO listings are the pages a small
        Philippine employer is actually found on. If one of those were dropped,
        the recall the boost buys would be spent getting rid of it.
        """
        from app.config import Settings

        excluded = _parse_domains(Settings(_env_file=None).tavily_exclude_domains)

        for essential in ("jobstreet.com", "indeed.com", "peso.gov.ph", "sec.gov.ph"):
            assert essential not in excluded, essential

    def test_a_blank_list_is_omitted_rather_than_sent_empty(self, monkeypatch):
        """An empty list and an absent key are different requests.

        `exclude_domains: []` tells the provider to filter nothing while still
        declaring an intent; a blank value is a misconfiguration, so it is
        dropped and the unfiltered query is issued.
        """
        captured = self._capture(monkeypatch, tavily_exclude_domains="   ")

        assert "exclude_domains" not in captured

    def test_a_list_of_separators_alone_is_omitted(self, monkeypatch):
        captured = self._capture(monkeypatch, tavily_exclude_domains=" , ,")

        assert "exclude_domains" not in captured

    def test_a_full_url_is_reduced_to_a_bare_domain(self, monkeypatch):
        """People paste URLs. Tavily wants the host.

        A scheme, a `www.` prefix, or a trailing path would not match the
        results it filters on, so the exclusion would silently do nothing —
        which reads as "the setting works" and is worse than an error.
        """
        captured = self._capture(
            monkeypatch,
            tavily_exclude_domains="https://www.Example.com/some/path",
        )
        assert captured["exclude_domains"] == ["example.com"]

    def test_empty_entries_are_dropped(self, monkeypatch):
        """A trailing comma or a double space is a typo, not a domain."""
        captured = self._capture(
            monkeypatch, tavily_exclude_domains="quora.com,,  ,reddit.com"
        )
        assert captured["exclude_domains"] == ["quora.com", "reddit.com"]

    def test_duplicates_collapse(self, monkeypatch):
        """Case and `www.` make two entries that filter identically."""
        captured = self._capture(
            monkeypatch, tavily_exclude_domains="quora.com, www.quora.com, QUORA.com"
        )
        assert captured["exclude_domains"] == ["quora.com"]

    def test_a_wildcard_is_passed_through_intact(self, monkeypatch):
        """Tavily supports `*.example.com`; parsing must not flatten it."""
        captured = self._capture(monkeypatch, tavily_exclude_domains="*.example.com")
        assert captured["exclude_domains"] == ["*.example.com"]

    def test_an_entry_without_a_dot_is_dropped(self, monkeypatch):
        """A stray word in the .env must not become a provider error.

        Tavily would reject a malformed domain, and a rejected search is
        reported to the user as a company that cannot be looked up. A typo in
        a recall setting must not become a verdict.
        """
        captured = self._capture(
            monkeypatch, tavily_exclude_domains="quora.com, scammy, reddit.com"
        )
        assert captured["exclude_domains"] == ["quora.com", "reddit.com"]

    def test_default_max_results_is_four(self):
        """The result count is a token-budget decision, not a recall one.

        Credits are charged per request, so `max_results` is free — asking for
        more results costs nothing. What it costs is context: every snippet
        becomes prompt text for a model that draws its reasoning from the same
        `AI_MAX_TOKENS` budget that has to hold the answer, and a truncated
        reasoning phase can come back with nothing at all. Four is the ceiling
        that keeps the verification answer room to exist.
        """
        from app.config import Settings

        assert Settings(_env_file=None).tavily_max_results == 4

    def test_max_results_is_still_configurable(self, monkeypatch):
        import app.services.search as mod

        captured = {}

        def fake_post(url, json=None, timeout=None, headers=None):
            captured.update(json or {})
            return FakeResponse(TAVILY_OK)

        monkeypatch.setattr(mod.settings, "tavily_api_key", "tvly-test")
        monkeypatch.setattr(mod.settings, "tavily_max_results", 3)
        monkeypatch.setattr(mod.httpx, "post", fake_post)
        # No explicit limit, so the value has to come from settings.
        mod.search("Jollibee")

        assert captured["max_results"] == 3


class TestGeographicBoost:
    """`country` is the fix for a ranking problem, not a query-syntax problem.

    A browser search from the Philippines surfaces SEC filings, city PESO
    sites, and local job boards for a small employer. Tavily's own crawl index
    covers that long tail less well, so a niche name falls through to whatever
    it indexes strongly — London VC firms, or a product with a similar word.
    Re-ranking the query cannot fix missing index coverage; boosting Philippine
    sources can.
    """

    def test_request_boosts_philippine_results(self, monkeypatch):
        import app.services.search as mod

        captured = {}

        def fake_post(url, json=None, timeout=None, headers=None):
            captured.update(json or {})
            return FakeResponse(TAVILY_OK)

        monkeypatch.setattr(mod.settings, "tavily_api_key", "tvly-test")
        monkeypatch.setattr(mod.httpx, "post", fake_post)
        mod.search("MIX Market Integrated Xploration", 5)

        assert captured["country"] == "philippines"

    def test_boost_does_not_filter_the_result_set(self, monkeypatch):
        """The goal was to keep JobStreet, Indeed PH, and PESO sites.

        `include_domains` restricts to the listed domains, which would discard
        exactly the non-government pages this boost is meant to surface. It
        must stay absent.

        `exclude_domains` removes pages by name, so it does not restrict the
        result set. The default does send one entry — see
        test_exclude_domains_defaults_to_wikipedia_only — which is a source
        removed, not a whitelist applied.
        """
        import app.services.search as mod

        captured = {}

        def fake_post(url, json=None, timeout=None, headers=None):
            captured.update(json or {})
            return FakeResponse(TAVILY_OK)

        monkeypatch.setattr(mod.settings, "tavily_api_key", "tvly-test")
        monkeypatch.setattr(mod.httpx, "post", fake_post)
        mod.search("MIX Market Integrated Xploration", 5)

        assert "include_domains" not in captured
        assert "include_domains_mode" not in captured

    def test_no_synthesised_answer_is_requested(self, monkeypatch):
        """The model reads the raw snippets; it is not handed a summary.

        `include_answer` makes the provider synthesise an answer, which is
        retrieval's opinion rather than evidence, and the verification prompt
        requires source URLs copied from the results.
        """
        import app.services.search as mod

        captured = {}

        def fake_post(url, json=None, timeout=None, headers=None):
            captured.update(json or {})
            return FakeResponse(TAVILY_OK)

        monkeypatch.setattr(mod.settings, "tavily_api_key", "tvly-test")
        monkeypatch.setattr(mod.httpx, "post", fake_post)
        mod.search("MIX Market Integrated Xploration", 5)

        assert not captured.get("include_answer")

    def test_uses_advanced_depth_for_a_niche_lookup(self, monkeypatch):
        """Advanced costs 2 credits against 1, and buys broader recall.

        Worth it for a small local employer that basic depth misses; the
        1,000-credit monthly budget is the trade.
        """
        import app.services.search as mod

        captured = {}

        def fake_post(url, json=None, timeout=None, headers=None):
            captured.update(json or {})
            return FakeResponse(TAVILY_OK)

        monkeypatch.setattr(mod.settings, "tavily_api_key", "tvly-test")
        monkeypatch.setattr(mod.httpx, "post", fake_post)
        mod.search("MIX Market Integrated Xploration", 5)

        assert captured["search_depth"] == "advanced"


class TestCompanyNameHelpers:
    """These were nested inside TestRawProviderBody by accident, which meant a
    class documented as being about the debug tab was also the only home for the
    name-cleaning tests. Deleting the debug tests would have taken these with
    them, so they now have a class of their own."""

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


