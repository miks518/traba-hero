"""The scan must tell the model what day it is.

A scan reported "future-dated hiring event - the poster advertises a hiring event
scheduled for October 14, 2026, which is a date far in the future and
inconsistent with standard immediate hiring practices." It was 12 October. The
date was two days away.

The model was working without a reference. Nothing in either prompt said what
today is, so "far in the future" had nothing to be far from, and the model
applied a genuinely useful scam heuristic - fake postings do claim distant start
dates - to a date that did not deserve it. The heuristic was right; the input was
unanchored.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.scanner import _today_instruction

transport = ASGITransport(app=app)


def _ph_now() -> datetime:
    return datetime.now(timezone(timedelta(hours=8)))


class TestTheInstructionIsWellFormed:
    def test_it_states_todays_date_in_an_unambiguous_form(self):
        text = _today_instruction()
        now = _ph_now()

        # Both forms, because "12 October 2026" and "2026-10-12" are read
        # differently by different models and a month/day/year slip here becomes
        # a wrong anomaly rather than a failed parse.
        assert now.strftime("%Y-%m-%d") in text
        assert str(now.day) in text

    def test_it_says_what_the_date_is_for(self):
        """A bare date reads as noise, and a model told nothing may ignore it.

        The line has to say *when it applies*, or the model has no reason to
        consult it for the posting in front of it.
        """
        low = _today_instruction().lower()

        for trigger in ("date", "schedule", "deadline"):
            assert trigger in low, trigger
        # It has to resolve the case that caused this, not merely supply a number.
        assert "must not be reported" in low or "no anomaly at all" in low

    def test_it_is_short_enough_to_ignore(self):
        """Cheaper than enabling reasoning, which is the whole reason for this.

        If this line grew to hundreds of characters it would pay, on every scan,
        for the same problem that turning reasoning on solves far more
        expensively.
        """
        assert len(_today_instruction()) < 600


class TestItReachesTheModelRequest:
    """The leg that failed once already, in this exact shape.

    A prompt instruction nothing sends is a rule that does not exist. The unit
    tests above pass against a function no endpoint calls.
    """

    @staticmethod
    def _capturing():
        from app.services.lm_client import _parse_custom

        captured = {}

        def _capture(messages, **kwargs):
            captured["text"] = "\n".join(str(m.get("content")) for m in messages)
            return _parse_custom("VALID: false\n")

        return captured, _capture

    @pytest.mark.asyncio
    async def test_the_image_scan_sends_it(self, scan_payload):
        captured, _capture = self._capturing()

        with patch("app.routers.scan.chat_stream_pieces", side_effect=_capture):
            async with AsyncClient(transport=transport, base_url="http://test") as c:
                resp = await c.post("/api/scan", json=scan_payload)

        assert resp.status_code == 200
        assert "Philippine time" in captured["text"]

    @pytest.mark.asyncio
    async def test_the_text_scan_sends_it(self, text_payload):
        captured, _capture = self._capturing()

        with patch("app.routers.scan.chat_stream_pieces", side_effect=_capture):
            async with AsyncClient(transport=transport, base_url="http://test") as c:
                resp = await c.post("/api/scan-text", json=text_payload)

        assert resp.status_code == 200
        assert "Philippine time" in captured["text"]


class TestTheFailureItPrevents:
    def test_the_reported_case_is_now_ordinary(self):
        """The exact input from the bug report, stated as a property.

        Not a test of the model - nothing offline can predict what a model will
        say - but a statement of what the instruction now tells it. If the
        wording changes until a two-day date reads as reportable again, the
        assertion that it still rules that out is what catches it.
        """
        low = _today_instruction().lower()

        assert "within the next few days is ordinary" in low
        assert "far from today" in low
