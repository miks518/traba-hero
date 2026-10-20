"""The schema-less path must parse, or fail loudly.

A provider that drops `response_format` answers in prose and the request still
succeeds. If the text parser returns nothing quietly, the panel renders empty
cards with no error anywhere — the failure mode this whole file exists to stop.

The distinction that matters: "parsed the response and it contained no checks"
is a legitimate empty result; "could not read this response at all" is a
failure worth reporting. Only the second raises.
"""

import json
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.scanner.verification_flow import _read_verify_output
from app.services.scanner.verification_parser import (
    VerificationParseError,
    _parse_verification_result,
    _parse_verify_section,
)

transport = ASGITransport(app=app)


BLOCK = (
    "VERIFY: Company Existence\n"
    "STATUS: green\n"
    "DETAIL: Acme lists this address on its own site.\n"
    "SOURCE: Acme Contact | https://acme.example/contact\n"
    "END VERIFY\n"
    "VERIFY: Channel Match\n"
    "STATUS: red\n"
    "DETAIL: Acme's own domain is acme.example; the post directs applicants to a Gmail address.\n"
    "SOURCE: Acme Contact | https://acme.example/contact\n"
    "END VERIFY\n"
)


def test_the_documented_block_shape_parses():
    items = _parse_verification_result(BLOCK)
    assert [i.label for i in items] == ["Company Existence", "Channel Match"]
    assert items[0].status == "green"
    assert items[1].status == "red"


def test_finding_is_accepted_as_well_as_detail():
    """The new shape names the field FINDING; the old one named it DETAIL.

    A parser that only knows DETAIL returns an item with an empty explanation,
    which renders as a card with a status and no explanation — looking like a
    finding that says nothing.
    """
    text = "VERIFY: Reputation\nSTATUS: yellow\nFINDING: No adverse record in the results.\nEND VERIFY\n"
    items = _parse_verification_result(text)
    assert items[0].explanation == "No adverse record in the results."


def test_the_legacy_detail_field_is_still_read_as_the_explanation():
    """Both spellings must yield a populated explanation, not just an item.

    Accepting FINDING alone is the overcorrection: results recorded before the
    rename arrive with DETAIL, and a parser that stops reading them returns a
    card with a status and no explanation for every stored response.
    """
    text = "VERIFY: Reputation\nSTATUS: yellow\nDETAIL: No adverse record in the results.\nEND VERIFY\n"
    items = _parse_verification_result(text)
    assert items[0].explanation == "No adverse record in the results."


def test_source_is_captured():
    text = (
        "VERIFY: Reputation\nSTATUS: red\nDETAIL: A DMW advisory names this scheme.\n"
        "SOURCE: DMW Advisory | https://dmw.gov.ph/advisory\nEND VERIFY\n"
    )
    items = _parse_verification_result(text)
    assert items[0].source_title == "DMW Advisory"
    assert items[0].source_url == "https://dmw.gov.ph/advisory"


def test_a_missing_end_marker_does_not_swallow_the_next_block():
    """The bug this parser was rewritten for.

    One combined regex loses a whole category whenever the model deviates
    slightly. A missing END VERIFY made the next match span two blocks.
    """
    text = (
        "VERIFY: Company Existence\nSTATUS: green\nDETAIL: Has a site.\n"
        "VERIFY: Reputation\nSTATUS: red\nDETAIL: A complaint was published.\n"
    )
    labels = [i.label for i in _parse_verification_result(text)]
    assert "Company Existence" in labels
    assert "Reputation" in labels


def test_unparseable_prose_raises_rather_than_returning_empty():
    # The silent failure. Without this raise the panel shows nothing and
    # nothing in the log says why.
    with pytest.raises(VerificationParseError):
        _parse_verification_result("The company appears to be legitimate based on my analysis.")


def test_empty_text_raises_too():
    with pytest.raises(VerificationParseError):
        _parse_verification_result("")


def test_a_response_with_no_usable_checks_is_not_an_error():
    """A well-formed response that simply reported nothing parses to empty.

    That is a legitimate result — the verification flow renders its own notice
    — and must not be confused with an unreadable one. The block is present and
    carries no status, so the parser read the response and it yielded nothing;
    the flow then renders its own notice rather than an error.

    The plan's original fixture for this was `REPORT: Nothing found.`, which has
    no VERIFY block at all — the very thing "could not read this response"
    means, and what the raise exists for. It asserted `[]` against text the
    plan's own implementation rejects, so it could never have passed.
    """
    assert _parse_verification_result("VERIFY: Reputation\nEND VERIFY\n") == []


def test_report_and_recommendation_still_parse():
    text = BLOCK + "REPORT: Two checks found something.\nEND REPORT\n"
    assert _parse_verify_section(text, "REPORT") == "Two checks found something."


class TestTheReadBoundaryRaises:
    """`_read_verify_output` must not swallow the parse error.

    It is the boundary the flow calls, so an exception caught here reappears as
    an empty item list, which is the state this file exists to delete.
    """

    def test_prose_reaches_the_caller_as_an_error(self):
        with pytest.raises(VerificationParseError):
            _read_verify_output("The company appears to be legitimate.")

    def test_a_readable_response_still_returns_items(self):
        items, _, _, used_json, _, _, _, _reason, _assessments = _read_verify_output(BLOCK)
        assert used_json is False
        assert [i.label for i in items] == ["Company Existence", "Channel Match"]


class TestTheFlowTellsTheTwoEmptyResultsApart:
    """Both render something; only one of them is a failure.

    Reaching the reader as "verification unavailable" (an error event) and as a
    yellow card saying nothing could be read are different claims, and the panel
    has to be able to make one without the other.
    """

    PROSE = "The company appears to be legitimate based on the search results."

    EMPTY_JSON = json.dumps({
        "checks": [],
        "evidence": [],
        "report": "",
        "recommendation": "",
    })

    async def _verify(self, ai_text):
        with patch("app.routers.scan.chat", return_value=ai_text):
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                return await client.post("/api/verify", json={
                    "company_name": "Acme Corp",
                    "job_summary": "Developer at Acme Corp",
                })

    @pytest.mark.asyncio
    async def test_an_unreadable_response_is_reported_as_a_failure(self):
        resp = await self._verify(self.PROSE)

        assert resp.status_code == 200
        assert '"type": "error"' in resp.text
        assert '"type": "result"' not in resp.text
        # Not the card either: an unreadable response must not be dressed up as
        # a finding about the employer.
        assert "No structured findings could be read" not in resp.text

    @pytest.mark.asyncio
    async def test_a_readable_response_with_no_checks_is_not_a_failure(self):
        resp = await self._verify(self.EMPTY_JSON)

        assert resp.status_code == 200
        assert '"type": "result"' in resp.text
        assert "No structured findings could be read" in resp.text
        # A verdict still exists: the unreadable verification contributes
        # nothing, and the posting's own score stands.
        assert '"verification_score": null' in resp.text