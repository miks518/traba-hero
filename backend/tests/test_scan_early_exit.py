"""Tests for early termination of the scan stream when VALID: false."""
import json
import pytest
from unittest.mock import patch, MagicMock
from app.routers.scan import _scan_event_stream, _VALID_LINE_RE


def _sse_events(events: list[str]) -> list[dict]:
    out = []
    for e in events:
        if e.startswith("data: "):
            out.append(json.loads(e[len("data: "):]))
    return out


def _result(events: list[str]) -> dict | None:
    for ev in _sse_events(events):
        if ev.get("type") == "result":
            return ev["data"]
    return None


# ── _VALID_LINE_RE ───────────────────────────────────────────────────

class TestValidLineRegex:
    def test_matches_false_line(self):
        assert _VALID_LINE_RE.search("VALID: false\n")

    def test_matches_true_line(self):
        m = _VALID_LINE_RE.search("VALID: true\n")
        assert m and m.group(1).lower() == "true"

    def test_partial_false_does_not_match(self):
        assert _VALID_LINE_RE.search("VALID: fal") is None

    def test_partial_token_does_not_match(self):
        assert _VALID_LINE_RE.search("VALID: f") is None

    def test_case_insensitive(self):
        m = _VALID_LINE_RE.search("valid: FALSE\n")
        assert m and m.group(1).lower() == "false"

    def test_requires_line_start(self):
        # Mid-line mention should not match (requires ^ with MULTILINE)
        assert _VALID_LINE_RE.search("see VALID: false here\n") is None

    def test_false_at_end_of_buffer_without_newline(self):
        # $ with MULTILINE matches end of string
        m = _VALID_LINE_RE.search("VALID: false")
        assert m and m.group(1).lower() == "false"


# ── _scan_event_stream early exit ────────────────────────────────────

@pytest.mark.asyncio
async def test_early_exit_stops_stream_on_valid_false():
    """Stream with VALID: false stops before consuming later pieces."""
    consumed: list[str] = []

    async def fake_stream(messages, max_tokens=None, temperature=None, top_p=None):
        for piece in [
            "VALID: false\n",
            "VERDICT_PERCENTAGE: 0\n",
            "ANALYSIS:\nnot a job\nEND ANALYSIS\n",
            "JOB SUMMARY:\nfoo\nEND JOB SUMMARY\n",
        ]:
            consumed.append(piece)
            yield piece

    with patch("app.routers.scan.chat_stream_pieces", fake_stream):
        events = []
        async for ev in _scan_event_stream(
            [{"role": "user", "content": "x"}], endpoint="test-early"
        ):
            events.append(ev)

    # Only the first piece should have been pulled from the generator
    assert consumed == ["VALID: false\n"]

    data = _result(events)
    assert data is not None
    assert data["valid"] is False
    assert data["email_verifications"] == []
    assert "verification_context" not in data


@pytest.mark.asyncio
async def test_no_early_exit_on_valid_true():
    """VALID: true continues streaming all pieces."""
    consumed: list[str] = []

    async def fake_stream(messages, max_tokens=None, temperature=None, top_p=None):
        for piece in [
            "VALID: true\n",
            "VERDICT_PERCENTAGE: 10\n",
            "END FLAGS\n",
            "ANALYSIS:\nlooks fine\nEND ANALYSIS\n",
            "JOB SUMMARY:\nEngineer at ACME developing web applications.\nApplicants need TypeScript and two years of experience.\nEND JOB SUMMARY\n",
        ]:
            consumed.append(piece)
            yield piece

    mock_verify = MagicMock(return_value=[])

    with patch("app.routers.scan.chat_stream_pieces", fake_stream), \
         patch("app.routers.scan.verify_emails_in_text", mock_verify), \
         patch("app.routers.scan.extract_company_name", return_value="ACME"):
        events = []
        async for ev in _scan_event_stream(
            [{"role": "user", "content": "x"}], endpoint="test-valid"
        ):
            events.append(ev)

    assert len(consumed) == 5

    data = _result(events)
    assert data is not None
    assert data["valid"] is True
    assert data["job_summary"] == (
        "Engineer at ACME developing web applications.\n"
        "Applicants need TypeScript and two years of experience."
    )


@pytest.mark.asyncio
async def test_partial_valid_false_does_not_trigger_early_exit():
    """Incomplete VALID: fal must not cancel the stream."""
    consumed: list[str] = []

    async def fake_stream(messages, max_tokens=None, temperature=None, top_p=None):
        for piece in [
            "VALID: fal",
            "se\n",
            "VERDICT_PERCENTAGE: 0\n",
            "END FLAGS\n",
            "ANALYSIS:\nnot a job\nEND ANALYSIS\n",
            "JOB SUMMARY:\nn/a\nEND JOB SUMMARY\n",
        ]:
            consumed.append(piece)
            yield piece

    with patch("app.routers.scan.chat_stream_pieces", fake_stream):
        events = []
        async for ev in _scan_event_stream(
            [{"role": "user", "content": "x"}], endpoint="test-partial"
        ):
            events.append(ev)

    # "VALID: fal" alone should not early-exit; "se\n" completes the line
    # and then early-exit fires — so we should get at least 2 pieces.
    assert len(consumed) >= 2
    # Should not have consumed everything if early exit fired after completion
    # After "VALID: false\n" is complete (piece 2), early exit → stop.
    assert consumed == ["VALID: fal", "se\n"]

    data = _result(events)
    assert data is not None
    assert data["valid"] is False


@pytest.mark.asyncio
async def test_invalid_skips_email_and_company_search():
    """When valid=false (even without early_exit), skip email + company extraction."""
    async def fake_stream(messages, max_tokens=None, temperature=None, top_p=None):
        # Model ignores stop instruction and emits full output with VALID: false
        yield "VALID: false\n"
        yield "VERDICT_PERCENTAGE: 0\n"
        yield "END FLAGS\n"
        yield "ANALYSIS:\nnot a job post\nEND ANALYSIS\n"
        yield "JOB SUMMARY:\nn/a\nEND JOB SUMMARY\n"

    mock_email = MagicMock(return_value=[])
    mock_company = MagicMock(return_value="ACME")

    with patch("app.routers.scan.chat_stream_pieces", fake_stream), \
         patch("app.routers.scan.verify_emails_in_text", mock_email), \
         patch("app.routers.scan.extract_company_name", mock_company):
        events = []
        async for ev in _scan_event_stream(
            [{"role": "user", "content": "x"}], endpoint="test-skip"
        ):
            events.append(ev)

    mock_email.assert_not_called()
    mock_company.assert_not_called()

    data = _result(events)
    assert data is not None
    assert data["valid"] is False
    assert data["email_verifications"] == []
