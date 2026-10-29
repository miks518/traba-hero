"""Extracted resume content must not reach the server logs.

The consent notice promises in-memory processing with no kept copy. A log line
that dumps the model's answer — the reader's skills, titles, and the summary
written out of their resume — is a kept copy on disk, and the promise would be
false the moment a request succeeded. These tests hold the two flows that carry
personal data to that promise: the resume analysis and the match.

Counters (tokens, characters) stay loggable — a number is not a person. What
may never appear is the content itself, on the success path or on a parse
failure: malformed output is still made of the reader's data.
"""

import asyncio
import contextlib
import json
import logging
from unittest.mock import patch

import pytest

from app.services.scanner import match_flow, resume_flow

# Any string that could only have come from the user's side of the exchange.
MARKER = "jane.santos@example.com"


def fake_stream_provider(pieces):
    async def provider(messages, max_tokens=None, endpoint=""):
        for piece in pieces:
            yield piece
    return provider


def fake_sse(obj):
    return json.dumps(obj)


async def collect_events(stream):
    events = []
    async for chunk in stream:
        events.append(chunk)
    return events


def event_types(events):
    return [json.loads(event)["type"] for event in events]


@pytest.mark.asyncio
async def test_resume_success_log_carries_no_content(caplog):
    with caplog.at_level(logging.INFO, logger="trabahero"):
        with patch_runtime(
            resume_flow.runtime,
            chat_stream=fake_stream_provider([f"SKILLS: {MARKER}, Excel\n", "TITLES: Encoder\n"]),
            parse_resume=lambda text: {"skills": [MARKER], "experience_years": 2, "job_titles": [], "industries": [], "summary": ""},
        ):
            events = await collect_events(resume_flow._resume_event_stream([{"role": "user", "content": "resume"}]))

    assert event_types(events)[-1] == "result", "the stream must still complete"
    assert MARKER not in caplog.text


@pytest.mark.asyncio
async def test_resume_parse_failure_log_carries_no_content(caplog):
    with caplog.at_level(logging.INFO, logger="trabahero"):
        with patch_runtime(
            resume_flow.runtime,
            chat_stream=fake_stream_provider([f"SKILLS: {MARKER}, Excel\n"]),
            parse_resume=lambda text: "not a dict",
        ):
            events = await collect_events(resume_flow._resume_event_stream([{"role": "user", "content": "resume"}]))

    # An unreadable resume yields the default empty profile — the established
    # contract — and, below, none of it may reach the log.
    assert event_types(events)[-1] == "result"
    assert MARKER not in caplog.text, "malformed output is still made of the reader's data"


@pytest.mark.asyncio
async def test_match_success_log_carries_no_content(caplog):
    with caplog.at_level(logging.INFO, logger="trabahero"):
        with patch_runtime(
            match_flow.runtime,
            chat_stream=fake_stream_provider([f'{{"job_id": "1", "reasoning": "knows {MARKER}"}}\n']),
            parse_match=lambda text: [{"job_id": "1", "score": 80, "reasoning": f"knows {MARKER}"}],
            parse_json=lambda text: None,
        ):
            events = await collect_events(match_flow._match_event_stream([{"role": "user", "content": "match"}]))

    assert event_types(events)[-1] == "result", "the stream must still complete"
    assert MARKER not in caplog.text


@pytest.mark.asyncio
async def test_match_parse_failure_log_carries_no_content(caplog):
    with caplog.at_level(logging.INFO, logger="trabahero"):
        with patch_runtime(
            match_flow.runtime,
            chat_stream=fake_stream_provider([f"job 1: {MARKER}, a good fit\n"]),
            parse_match=lambda text: 42,
            parse_json=lambda text: None,
        ):
            events = await collect_events(match_flow._match_event_stream([{"role": "user", "content": "match"}]))

    assert event_types(events)[-1] == "error", "an unreadable answer must be reported"
    assert MARKER not in caplog.text


@contextlib.contextmanager
def patch_runtime(runtime, chat_stream, parse_resume=None, parse_match=None, parse_json=None):
    """Swap the collaborators the stream functions reach through `runtime`."""
    replacements = {
        "get_chat_stream": staticmethod(lambda: chat_stream),
        "get_sse": staticmethod(lambda: fake_sse),
    }
    if parse_resume is not None:
        replacements["get_parse_resume"] = staticmethod(lambda: parse_resume)
    if parse_match is not None:
        replacements["get_parse_match"] = staticmethod(lambda: parse_match)
    if parse_json is not None:
        replacements["get_parse_json"] = staticmethod(lambda: parse_json)
    with contextlib.ExitStack() as stack:
        for name, value in replacements.items():
            stack.enter_context(patch.object(runtime, name, value))
        yield
