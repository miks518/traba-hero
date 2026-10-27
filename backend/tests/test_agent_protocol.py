"""The agent's tool calls are labeled text, with the safety filter at the door.

Task 15 of the assessment-procedure plan. `lm_client.chat()` has no `tools=`
parameter, no multi-turn seam of its own, and native tool calling is not
guaranteed across OpenRouter routes — so the protocol is two labeled lines,
parsed here, and the conclusion-word filter drops a refused query before a
credit is spent on it.
"""

import pytest

from app.services import lm_client
from app.services.lm_client import chat_turn
from app.services.scanner.agent_protocol import (
    ToolCall,
    is_final_answer,
    parse_tool_calls,
)


def test_a_search_call_parses():
    assert parse_tool_calls("TOOL: search\nARGUMENT: knollridges company or employer") == (
        ToolCall("search", "knollridges company or employer"),
    )


def test_text_that_merely_mentions_search_is_not_a_call():
    assert parse_tool_calls("I would search for the employer now.") == ()


def test_a_conclusion_word_in_an_argument_is_refused():
    # The query is refused before it is issued, so the parser must drop it.
    assert parse_tool_calls("TOOL: search\nARGUMENT: acme scam") == ()


def test_a_fetch_call_is_not_refused_for_a_conclusion_word():
    # The banned-terms filter governs what we search for, not where a search
    # result may point: an official advisory page can legitimately live on a
    # domain with "scam" in its path.
    assert parse_tool_calls("TOOL: fetch\nARGUMENT: https://www.cicc.gov.ph/scam-alerts") == (
        ToolCall("fetch", "https://www.cicc.gov.ph/scam-alerts"),
    )


def test_two_calls_parse_in_order():
    text = (
        "TOOL: search\nARGUMENT: knollridges company or employer\n"
        "TOOL: fetch\nARGUMENT: https://knollridges.com.ph/careers"
    )
    assert parse_tool_calls(text) == (
        ToolCall("search", "knollridges company or employer"),
        ToolCall("fetch", "https://knollridges.com.ph/careers"),
    )


def test_a_call_with_no_argument_is_dropped():
    assert parse_tool_calls("TOOL: search\nARGUMENT:") == ()


def test_an_unknown_tool_is_dropped():
    assert parse_tool_calls("TOOL: browse\nARGUMENT: https://x.example.com") == ()


def test_a_turn_with_no_tool_call_is_the_final_answer():
    assert is_final_answer('{"valid": true, "findings": []}') is True


def test_a_turn_with_a_tool_call_is_not_the_final_answer():
    assert is_final_answer("TOOL: search\nARGUMENT: acme company or employer") is False


def test_a_refused_call_is_still_not_a_final_answer():
    # The harness must tell the model the query was refused and let it choose
    # another, not read the turn as an answer and hand prose to the parser.
    assert is_final_answer("TOOL: search\nARGUMENT: acme scam") is False


@pytest.mark.asyncio
async def test_chat_turn_sends_the_whole_transcript(monkeypatch):
    """The posting is re-sent every turn; nothing between here and the
    provider summarises it. That is the whole fix for the relay."""
    seen = {}

    async def recorder(messages, **kwargs):
        seen["messages"] = messages
        seen["kwargs"] = kwargs
        return "final answer"

    monkeypatch.setattr(lm_client, "chat", recorder)
    messages = [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "the posting"},
        {"role": "assistant", "content": "TOOL: search\nARGUMENT: acme"},
        {"role": "user", "content": "search results"},
    ]
    out = await chat_turn(messages, endpoint="assess")
    assert out == "final answer"
    assert seen["messages"] == messages
    assert seen["kwargs"]["endpoint"] == "assess"
