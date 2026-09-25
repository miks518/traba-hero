"""Tests for DuckDuckGo search module (ddg_search.py)."""
import pytest
from unittest.mock import patch, MagicMock
from app.services.ddg_search import (
    ddg_search,
    extract_company_name,
    format_search_context,
    is_valid_company_name,
    search_company,
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

        results = ddg_search("test query")
        assert results == []

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
