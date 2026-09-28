"""Tests for DuckDuckGo search module (ddg_search.py)."""
import pytest
from unittest.mock import patch, MagicMock
from app.services.ddg_search import (
    ddg_search,
    extract_company_name,
    format_search_context,
    format_verification_context,
    is_valid_company_name,
    search_company,
    search_company_for_verification,
    search_job_posting,
    search_job_posting_data,
)


class TestIsValidCompanyName:
    def test_valid_company_names(self):
        assert is_valid_company_name("Acme Corp") is True
        assert is_valid_company_name("Google Philippines") is True
        assert is_valid_company_name("San Miguel Brewery Inc.") is True

    def test_invalid_placeholder_names(self):
        assert is_valid_company_name("None") is False
        assert is_valid_company_name("none") is False
        assert is_valid_company_name("N/A") is False
        assert is_valid_company_name("Unknown") is False
        assert is_valid_company_name("Not specified") is False
        assert is_valid_company_name("unclear") is False
        assert is_valid_company_name("not provided") is False
        assert is_valid_company_name("no company") is False
        assert is_valid_company_name("") is False
        assert is_valid_company_name(None) is False



# ── extract_company_name ─────────────────────────────────────────────

class TestCleanCompanyName:
    """The employer is the company the reader would work for.

    A staffing agency is a recruiter, not the employer, so a posting naming both
    ("Vikings / Silvergreen Manpower Services Corporation") must not reach the
    search as one joined string — a search engine tokenises the slash into
    neither entity.
    """

    def test_plain_name_passes_through(self):
        from app.services.ddg_search import clean_company_name

        assert clean_company_name("Jollibee Foods Corporation") == "Jollibee Foods Corporation"

    def test_joined_recruiter_and_client_keeps_the_client(self):
        from app.services.ddg_search import clean_company_name

        got = clean_company_name("Vikings / Silvergreen Manpower Services Corporation")
        assert got == "Silvergreen Manpower Services Corporation"

    def test_pipe_separator_also_handled(self):
        from app.services.ddg_search import clean_company_name

        assert clean_company_name("Vikings | Silvergreen Manpower") == "Silvergreen Manpower"

    def test_agency_only_posting_keeps_the_agency(self):
        from app.services.ddg_search import clean_company_name

        assert clean_company_name("Silvergreen Manpower Services Corporation") == "Silvergreen Manpower Services Corporation"

    def test_placeholders_still_rejected(self):
        from app.services.ddg_search import clean_company_name

        for bad in ("Not stated", "N/A", "unknown", "", None):
            assert clean_company_name(bad) == ""

    def test_leading_article_dropped(self):
        from app.services.ddg_search import clean_company_name

        assert clean_company_name("The Acme Company") == "Acme Company"


class TestExtractCompanyName:
    def test_extracts_company_from_hiring_pattern(self):
        text = "Acme Corp is hiring a Software Engineer"
        result = extract_company_name(text)
        assert result is not None
        assert "Acme Corp" in result

    def test_extracts_company_from_at_pattern(self):
        text = "Apply now at Google Philippines"
        assert extract_company_name(text) == "Google Philippines"

    def test_extracts_company_from_about_pattern(self):
        text = "About Accenture Philippines we are a global company"
        result = extract_company_name(text)
        assert result is not None
        assert "Accenture Philippines" in result

    def test_extracts_company_from_label(self):
        text = "Company: Globe Telecom\nSalary: 30k"
        result = extract_company_name(text)
        assert result is not None
        assert "Globe Telecom" in result

    def test_returns_none_for_no_company(self):
        text = "Apply now, good salary, call this number"
        assert extract_company_name(text) is None

    def test_returns_result_for_text_with_at(self):
        text = "Work at We are hiring"
        result = extract_company_name(text)
        assert result is not None

    def test_skips_skip_words(self):
        text = "The Company is hiring"
        assert extract_company_name(text) is None


# ── ddg_search ───────────────────────────────────────────────────────

class TestDdgSearch:
    @pytest.fixture(autouse=True)
    def _no_throttle_waits(self):
        """The throttle interval is a real sleep; these tests are not about timing."""
        from app.config import settings

        interval = settings.ddg_min_interval
        settings.ddg_min_interval = 0.0
        yield
        settings.ddg_min_interval = interval

    @patch("app.services.ddg_search.DDGS")
    def test_returns_formatted_results(self, mock_ddgs):
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.text.return_value = [
            {"title": "ACME Corp", "body": "A company in PH", "href": "https://acme.ph"},
        ]
        mock_ddgs.return_value = mock_ctx

        results = ddg_search("ACME Philippines")
        assert len(results) == 1
        assert results[0]["title"] == "ACME Corp"
        assert results[0]["snippet"] == "A company in PH"
        assert results[0]["url"] == "https://acme.ph"

    @patch("app.services.ddg_search.DDGS")
    def test_returns_empty_on_exception(self, mock_ddgs):
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.text.side_effect = Exception("rate limited")
        mock_ddgs.return_value = mock_ctx

        # The offline conftest configures a Tavily key, and ddg_search() falls
        # back to it when the primary fails. Clear it so this asserts what it
        # means to: a failed primary with no fallback configured returns [].
        with (
            patch("app.services.ddg_search.settings.tavily_api_key", ""),
            patch("app.services.ddg_search.time.sleep"),
        ):
            results = ddg_search("test query")
        assert results == []

    def test_retries_before_giving_up_on_a_throttled_query(self):
        from app.services import ddg_search as mod

        attempts = []

        def throttled_once(q, n=5):
            attempts.append(q)
            if len(attempts) == 1:
                raise RuntimeError("No results found.")
            return [{"title": "Recovered", "snippet": "s", "url": "u"}]

        with (
            patch.object(mod, "_ddg_once", throttled_once),
            patch.object(mod.time, "sleep"),
            patch.object(mod.settings, "ddg_min_interval", 0.0),
        ):
            results = mod.ddg_search("q", 5)

        assert len(attempts) >= 2, "a throttled query must be retried"
        assert results[0]["title"] == "Recovered"

    @patch("app.services.ddg_search.DDGS")
    def test_truncates_long_snippets(self, mock_ddgs):
        long_body = "x" * 500
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.text.return_value = [
            {"title": "Test", "body": long_body, "href": "https://test.com"},
        ]
        mock_ddgs.return_value = mock_ctx

        results = ddg_search("test")
        assert len(results[0]["snippet"]) <= 300


# ── format_search_context ────────────────────────────────────────────

class TestFormatSearchContext:
    def test_returns_empty_for_no_results(self):
        assert format_search_context({"company": "X"}) == ""

    def test_formats_results_with_sections(self):
        data = {
            "company": "ACME",
            "legitimacy_results": [{"title": "ACME Corp", "snippet": "A company"}],
            "sec_results": [],
            "scam_results": [],
            "linkedin_results": [],
            "dole_results": [],
        }
        result = format_search_context(data)
        assert "WEB SEARCH: ACME" in result
        assert "Company Info" in result
        assert "ACME Corp" in result
        assert "END SEARCH" in result

    def test_includes_multiple_sections(self):
        data = {
            "company": "ACME",
            "legitimacy_results": [{"title": "Info", "snippet": "..."}],
            "sec_results": [{"title": "SEC", "snippet": "..."}],
            "scam_results": [{"title": "Scam", "snippet": "..."}],
            "linkedin_results": [],
            "dole_results": [],
        }
        result = format_search_context(data)
        assert "Company Info" in result
        assert "SEC Registration" in result
        assert "Scam/Fraud Reports" in result


# ── format_verification_context ──────────────────────────────────────

class TestFormatVerificationContext:
    """The /api/verify prompt is built from this function.

    A regression: it read r['body'] while ddg_search() returns the snippet
    under 'snippet', so every snippet was dropped and the model saw titles
    only. It then truthfully reported that no result mentioned SEC
    registration even when the top hit plainly did.
    """

    def test_returns_empty_for_no_results(self):
        assert format_verification_context({"company": "X"}) == ""

    def test_emits_the_snippet_not_just_the_title(self):
        data = {
            "company": "Acme",
            "sec": [{
                "title": "SEC Registration No. CS201900123 - Acme",
                "snippet": "Certificate of Incorporation issued by the SEC.",
                "url": "https://example.com",
            }],
        }
        out = format_verification_context(data)
        assert "CS201900123" in out
        assert "Certificate of Incorporation" in out

    def test_emits_snippets_for_every_section(self):
        data = {
            "company": "Acme",
            "legitimacy": [{"title": "T1", "snippet": "S1"}],
            "sec": [{"title": "T2", "snippet": "S2"}],
            "scam": [{"title": "T3", "snippet": "S3"}],
            "reviews": [{"title": "T4", "snippet": "S4"}],
        }
        out = format_verification_context(data)
        for s in ("S1", "S2", "S3", "S4"):
            assert s in out, f"snippet {s} missing from verification prompt"

    def test_social_results_carry_snippets(self):
        """search_company builds social_results from ddg_search()'s return.

        It used to read the raw library keys 'body' and 'href', which ddg_search
        does not emit, so all 13 results had empty snippets and the scan prompt
        received Social Media Reviews as titles with no text.
        """
        from app.services import ddg_search as mod

        raw = [{
            "title": "Jollibee review",
            "snippet": "Good place to work according to 4 reviews.",
            "url": "https://example.com/r",
        }]

        calls = []

        def fake_ddg_search(query, max_results=5):
            calls.append(query)
            if query.startswith("site:facebook.com"):
                return raw
            if query.startswith("site:reddit.com"):
                return []
            return list(raw)

        with patch.object(mod, "ddg_search", fake_ddg_search):
            data = mod.search_company("Jollibee")

        social = data["social_results"]
        assert social, "no social results collected"
        assert all(r["snippet"] for r in social), "a social result has an empty snippet"
        assert all(r["url"] for r in social), "a social result has an empty url"
        assert "Good place to work" in social[0]["snippet"]

    def test_shows_each_query_with_its_results(self):
        data = {
            "company": "Acme",
            "legitimacy": [{"title": "Site", "snippet": "Runs a shop."}],
            "sec": [{"title": "Registry", "snippet": "SEC 123"}],
        }
        out = format_verification_context(data)
        assert "QUERY: Acme Philippines company" in out
        assert "QUERY: Acme SEC registration Philippines" in out
        assert "Runs a shop." in out
        assert "SEC 123" in out

    def test_shows_every_result_not_just_the_first_three(self):
        """This is a raw dump: capping at three hid half the evidence."""
        data = {
            "company": "Acme",
            "sec": [{"title": f"T{i}", "snippet": f"S{i}"} for i in range(10)],
        }
        out = format_verification_context(data)
        for i in range(10):
            assert f"S{i}" in out, f"result {i} missing from the dump"

    def test_includes_urls(self):
        data = {
            "company": "Acme",
            "sec": [{"title": "T", "snippet": "S", "url": "https://example.com/x"}],
        }
        assert "https://example.com/x" in format_verification_context(data)

    def test_marks_an_empty_query_rather_than_skipping_it(self):
        """An empty query must be visible, or it looks like it never ran."""
        data = {
            "company": "Acme",
            "legitimacy": [{"title": "T", "snippet": "S"}],
            "sec": [],
        }
        out = format_verification_context(data)
        assert "QUERY: Acme SEC registration Philippines" in out
        assert "(no results returned for this query)" in out

    def test_no_category_headings(self):
        """The old headings implied a result had been classified for a category."""
        data = {
            "company": "Acme",
            "legitimacy": [{"title": "T", "snippet": "S"}],
            "sec": [{"title": "T", "snippet": "S"}],
        }
        out = format_verification_context(data)
        for heading in ("COMPANY EXISTENCE", "SEC REGISTRATION", "SCAM REPORTS", "REVIEWS AND REPUTATION"):
            assert heading not in out, f"{heading} should no longer be imposed on the results"

    def test_repeated_results_across_queries_are_both_shown(self):
        """No dedupe: the model judges whether a repeat is meaningful."""
        same = [{"title": "Facebook page", "snippet": "23,828 followers"}]
        data = {"company": "Acme", "legitimacy": same, "sec": same, "scam": same}
        out = format_verification_context(data)
        assert out.count("23,828 followers") == 3


class TestSearchCompanyForVerification:
    @patch("app.services.ddg_search.search_with_diagnostics")
    def test_runs_four_queries(self, mock_search):
        from app.services.ddg_search import SearchOutcome

        mock_search.return_value = SearchOutcome(results=[], provider="ddg", attempts=3)
        result = search_company_for_verification("Acme")
        assert mock_search.call_count == 4
        assert set(result) == {"company", "legitimacy", "sec", "scam", "reviews", "throttled"}

    @patch("app.services.ddg_search.search_with_diagnostics")
    def test_results_survive_into_the_prompt(self, mock_search):
        """End-to-end shape: a snippet from the library reaches the prompt."""
        from app.services.ddg_search import SearchOutcome

        mock_search.return_value = SearchOutcome(
            results=[{
                "title": "SEC Registration No. CS201900123",
                "snippet": "Registered with the Philippine SEC.",
                "url": "https://example.com",
            }],
            provider="ddg",
        )
        out = format_verification_context(search_company_for_verification("Acme"))
        assert "Registered with the Philippine SEC." in out

    @patch("app.services.ddg_search.search_with_diagnostics")
    def test_failed_sections_are_flagged_not_silently_dropped(self, mock_search):
        """A throttled section must be marked, not look like a clean company."""
        from app.services.ddg_search import SearchOutcome

        good = SearchOutcome(results=[{"title": "Site", "snippet": "Runs a shop.", "url": "u"}])
        bad = SearchOutcome(results=[], attempts=3, throttled=True, error="empty result set")
        # legitimacy good, sec bad, scam good, reviews bad
        mock_search.side_effect = [good, bad, good, bad]

        data = search_company_for_verification("Acme")
        assert sorted(data["throttled"]) == ["reviews", "sec"]
        out = format_verification_context(data)
        assert "NOTE ON RETRIEVAL" in out
        # The notice names the queries that failed, so the model can see which
        # categories are unknown.
        assert "Acme SEC registration Philippines" in out
        assert "Acme scam fraud complaint" in out
        assert "NOT that the company has no such" in out

    @patch("app.services.ddg_search.search_with_diagnostics")
    def test_no_throttle_notice_when_all_sections_succeed(self, mock_search):
        from app.services.ddg_search import SearchOutcome

        mock_search.return_value = SearchOutcome(
            results=[{"title": "T", "snippet": "S", "url": "u"}]
        )
        out = format_verification_context(search_company_for_verification("Acme"))
        assert "NOTE ON RETRIEVAL" not in out


class TestSearchDiagnostics:
    """DuckDuckGo answers the same query with results or with nothing.

    The throttling interval and retry backoff are zeroed per-test. They are real
    waits, and the offline suite must stay fast; nothing here tests their timing.
    """

    @pytest.fixture(autouse=True)
    def _no_waits(self):
        from app.config import settings

        interval, backoff = settings.ddg_min_interval, settings.ddg_search_backoff
        settings.ddg_min_interval = 0.0
        settings.ddg_search_backoff = 0.0
        yield
        settings.ddg_min_interval, settings.ddg_search_backoff = interval, backoff

    def test_empty_result_is_retried_then_reported(self):
        from app.services import ddg_search as mod
        from app.services.ddg_search import SearchOutcome

        calls = []

        def always_empty(q, n=5):
            calls.append(q)
            return []

        with patch.object(mod, "_ddg_once", always_empty):
            outcome = mod.search_with_diagnostics("q", 5, attempts=3)

        assert len(calls) == 3, "an empty result set must be retried"
        assert outcome.ok is False
        assert outcome.attempts == 3
        assert "empty result set" in outcome.error

    def test_an_empty_200_is_classified_as_throttled(self):
        """A 200 with no rows is the throttle signature, not a clean company.

        The provider accepts the request and withholds the SERP, so nothing
        raises and a generic error check never sees it. The first verification
        query succeeded and the next three returned nothing this way.
        """
        from app.services import ddg_search as mod

        with (
            patch.object(mod, "_ddg_once", lambda q, n=5: []),
            patch.object(mod.time, "sleep"),
            patch.object(mod.settings, "ddg_min_interval", 0.0),
        ):
            outcome = mod.search_with_diagnostics("q", 5, attempts=2)

        assert outcome.ok is False
        assert outcome.throttled is True, "an empty 200 must be flagged as throttled"
        assert "empty result set" in outcome.error

    def test_a_rate_limited_engine_falls_through_to_another(self):
        """One engine being throttled must cost a miss, not a whole section."""
        from app.services import ddg_search as mod

        tried = []

        class Flaky:
            def __enter__(self):
                return self

            def __exit__(self, *e):
                return False

            def text(self, query, max_results=5, backend=None, **kw):
                tried.append(backend)
                if backend == "yahoo":
                    raise RuntimeError("No results found.")
                return [{"title": "OK", "body": "snippet", "href": "https://x"}]

        with patch.object(mod, "DDGS", Flaky), patch.object(mod.settings, "ddg_backend", ""):
            results = mod._ddg_once("q", 5)

        assert results and results[0]["snippet"] == "snippet"
        assert len(tried) >= 2, "should have tried a second engine"
        assert tried[0] == "yahoo" and tried[1] == "mojeek"

    def test_pinned_invalid_backend_is_not_silently_accepted(self):
        """The library rejects unknown backends; our list must not contain one."""
        from app.services import ddg_search as mod

        # The installed ddgs advertises this set; ours must be a subset.
        assert set(mod._BACKEND_ORDER) <= {
            "brave", "duckduckgo", "google", "grokipedia", "mojeek",
            "startpage", "wikipedia", "yahoo",
        }, f"unknown backend in rotation order: {mod._BACKEND_ORDER}"

    def test_backoff_grows_between_attempts(self):
        from app.services import ddg_search as mod

        waits = []
        with (
            patch.object(mod, "_ddg_once", lambda q, n=5: []),
            patch.object(mod.time, "sleep", waits.append),
            patch.object(mod.settings, "ddg_min_interval", 0.0),
            patch.object(mod.settings, "ddg_search_backoff", 2.0),
            patch.object(mod.settings, "ddg_search_backoff_max", 10.0),
        ):
            mod.search_with_diagnostics("q", 5, attempts=4)

        assert waits == [2.0, 4.0, 8.0], f"backoff should grow, got {waits}"

    def test_a_retry_that_succeeds_returns_results(self):
        from app.services import ddg_search as mod

        seq = [[], [], [{"title": "T", "snippet": "S", "url": "u"}]]
        calls = []

        def flaky(q, n=5):
            calls.append(q)
            return seq[len(calls) - 1]

        with patch.object(mod, "_ddg_once", flaky):
            outcome = mod.search_with_diagnostics("q", 5, attempts=3)

        assert outcome.ok is True
        assert len(outcome.results) == 1
        assert outcome.attempts == 3

    def test_transient_errors_are_classified_as_throttled(self):
        from app.services import ddg_search as mod

        def rate_limited(q, n=5):
            raise RuntimeError("Too Many Requests: 429")

        with patch.object(mod, "_ddg_once", rate_limited):
            outcome = mod.search_with_diagnostics("q", 5, attempts=1)

        assert outcome.throttled is True
        assert outcome.ok is False

    def test_permanent_errors_are_not_called_throttled(self):
        from app.services import ddg_search as mod

        def broken(q, n=5):
            raise ValueError("bad query syntax")

        with patch.object(mod, "_ddg_once", broken):
            outcome = mod.search_with_diagnostics("q", 5, attempts=1)

        assert outcome.throttled is False
        assert "bad query syntax" in outcome.error

    def test_fallback_provider_is_tried_when_primary_is_empty(self):
        from app.services import ddg_search as mod

        def primary_empty(q, n=5):
            return []

        def fallback_hit(q, n=5):
            return [{"title": "From Tavily", "snippet": "real content", "url": "u"}]

        with (
            patch.object(mod, "_ddg_once", primary_empty),
            patch.object(mod, "tavily_search", fallback_hit),
            patch.object(mod.settings, "tavily_api_key", "test-key"),
        ):
            results = mod.ddg_search("q", 5)

        assert results and results[0]["title"] == "From Tavily"

    def test_fallback_not_used_without_a_key(self):
        from app.services import ddg_search as mod

        with (
            patch.object(mod, "_ddg_once", lambda q, n=5: []),
            patch.object(mod, "tavily_search", lambda q, n=5: [{"title": "x"}]),
            patch.object(mod.settings, "tavily_api_key", ""),
        ):
            results = mod.ddg_search("q", 5)

        assert results == []


# ── search_company ───────────────────────────────────────────────────

class TestSearchCompany:
    @patch("app.services.ddg_search.ddg_search")
    def test_calls_all_query_types(self, mock_search):
        mock_search.return_value = []
        result = search_company("ACME")
        assert mock_search.call_count == 8
        assert result["company"] == "ACME"
        assert "legitimacy_results" in result
        assert "sec_results" in result
        assert "scam_results" in result
        assert "linkedin_results" in result
        assert "dole_results" in result
        assert "social_results" in result


# ── search_job_posting ───────────────────────────────────────────────

class TestSearchJobPosting:
    @patch("app.services.ddg_search.search_company")
    def test_returns_empty_when_no_company(self, mock_search):
        result = search_job_posting("Apply now, good salary")
        assert result == ""
        mock_search.assert_not_called()

    @patch("app.services.ddg_search.search_company")
    def test_returns_formatted_context(self, mock_search):
        mock_search.return_value = {
            "company": "ACME",
            "legitimacy_results": [{"title": "ACME", "snippet": "A company"}],
            "sec_results": [],
            "scam_results": [],
            "linkedin_results": [],
            "dole_results": [],
        }
        result = search_job_posting("Work at ACME Corp is hiring")
        assert "ACME" in result
        mock_search.assert_called_once()


# ── search_job_posting_data ──────────────────────────────────────────

class TestSearchJobPostingData:
    @patch("app.services.ddg_search.search_company")
    def test_returns_empty_when_no_company(self, mock_search):
        result = search_job_posting_data("Random text")
        assert result == {"company_name": None, "results": {}}

    @patch("app.services.ddg_search.search_company")
    def test_returns_structured_data(self, mock_search):
        mock_search.return_value = {
            "company": "ACME Corp",
            "legitimacy_results": [{"title": "ACME", "body": "A company", "href": "https://acme.ph"}],
            "sec_results": [],
            "scam_results": [],
            "linkedin_results": [],
            "dole_results": [],
        }
        result = search_job_posting_data("Work at ACME Corp")
        assert result["company_name"] == "ACME Corp"
        assert "legitimacy" in result["results"]
        assert len(result["results"]["legitimacy"]) == 1
