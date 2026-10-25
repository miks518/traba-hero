"""One agent that holds the posting for the whole proceeding.

Task 16 of the verdict-procedure plan. The relay is the defect: the scan model
read the flyer, the verify model read a compression of the scan, and the fact
that decided the verdict was often not in the room when the verdict was
written. Here the posting is re-sent on every turn and never summarised on
the way, the tools are metered, and a refused query costs no credit.
"""

import pytest

from app.services.fetch import FetchRefused, FetchedPage
from app.services.scanner import agent
from app.services.scanner.agent import AgentLimits, run_agent
from app.services.search import SearchOutcome, SearchResult
from tests.conftest import class_settings

FINAL_ANSWER = '{"valid": true, "findings": [], "attributes": {}, "record": []}'

POSTING = [
    {"type": "text", "text": "JOB POSTING: warehouse staff, Cebu, PHP 18,000 monthly"}
]


class _FakeTools:
    """The two tools, recording what they were asked and never touching the net."""

    def __init__(self):
        self.searched: list[str] = []
        self.fetched: list[str] = []

    def search(self, query):
        self.searched.append(query)
        return SearchOutcome(
            results=[
                SearchResult(
                    title="Acme Hiring Page",
                    url="https://acme.example.com/",
                    snippet="We are hiring warehouse staff.",
                    score=0.9,
                )
            ],
            ok=True,
        )

    async def fetch(self, url, max_bytes):
        self.fetched.append(url)
        return FetchedPage(url=url, text="Warehouse staff wanted in Cebu.", truncated=False)


def _scripted_model(script):
    """A model that plays its turns from a script and records every request.

    Each request is snapshotted: the agent mutates its transcript list in
    place, and a recorded reference would show every call the final state.
    """
    calls = []

    async def chat_turn(messages, **kwargs):
        calls.append([dict(m) for m in messages])
        return script[min(len(calls), len(script)) - 1]

    chat_turn.calls = calls
    return chat_turn


def _posting_user_messages(messages):
    """The user messages that carry the posting verbatim."""
    out = []
    for m in messages:
        parts = m["content"] if isinstance(m["content"], list) else []
        if m["role"] == "user" and any(
            isinstance(p, dict) and p.get("text") == POSTING[0]["text"] for p in parts
        ):
            out.append(m)
    return out


def _all_text(messages):
    chunks = []
    for m in messages:
        if isinstance(m["content"], str):
            chunks.append(m["content"])
        else:
            for part in m["content"]:
                if isinstance(part, dict) and isinstance(part.get("text"), str):
                    chunks.append(part["text"])
    return " ".join(chunks)


@pytest.mark.asyncio
async def test_the_posting_is_re_sent_on_every_turn(monkeypatch):
    """The relay is the defect. The same posting must be in every request."""
    fake_model = _scripted_model([
        "TOOL: search\nARGUMENT: acme hiring cebu",
        FINAL_ANSWER,
    ])
    monkeypatch.setattr(agent, "chat_turn", fake_model)
    result = await run_agent(
        POSTING, system_prompt="system", tools=_FakeTools(), limits=AgentLimits()
    )
    assert result.turns == 2
    for i, messages in enumerate(fake_model.calls, 1):
        assert len(_posting_user_messages(messages)) == i, (
            "the posting must appear once per turn, re-sent with the transcript"
        )


@pytest.mark.asyncio
async def test_the_search_budget_is_three(monkeypatch):
    """Three searches are the credit ceiling; a fourth is refused, not spent."""
    fake_model = _scripted_model([
        f"TOOL: search\nARGUMENT: acme hiring {n}" for n in range(6)
    ])
    monkeypatch.setattr(agent, "chat_turn", fake_model)
    tools = _FakeTools()
    result = await run_agent(
        POSTING,
        system_prompt="system",
        tools=tools,
        limits=AgentLimits(max_turns=6, max_searches=3),
    )
    assert tools.searched == ["acme hiring 0", "acme hiring 1", "acme hiring 2"]
    assert result.searches == 3
    # The refusal is told to the model, in the request after the refused turn
    # — turn 4's call is refused while turn 4 is being served, so it is turn
    # 5's request (calls[4]) that carries it.
    assert "budget" in _all_text(fake_model.calls[4]).lower()


@pytest.mark.asyncio
async def test_a_refused_query_does_not_spend_a_credit(monkeypatch):
    """A query the safety filter drops never reaches the search."""
    fake_model = _scripted_model([
        "TOOL: search\nARGUMENT: acme scam",
        FINAL_ANSWER,
    ])
    monkeypatch.setattr(agent, "chat_turn", fake_model)
    tools = _FakeTools()
    result = await run_agent(
        POSTING, system_prompt="system", tools=tools, limits=AgentLimits()
    )
    assert tools.searched == []
    assert result.searches == 0
    # The model is told the call could not be run, so it can choose another.
    assert "refused" in _all_text(fake_model.calls[1]).lower()


@pytest.mark.asyncio
async def test_the_loop_stops_at_the_turn_limit(monkeypatch):
    fake_model = _scripted_model([
        f"TOOL: search\nARGUMENT: acme hiring {n}" for n in range(9)
    ])
    monkeypatch.setattr(agent, "chat_turn", fake_model)
    tools = _FakeTools()
    result = await run_agent(
        POSTING,
        system_prompt="system",
        tools=tools,
        limits=AgentLimits(max_turns=3, max_searches=10),
    )
    assert len(fake_model.calls) == 3
    assert result.turns == 3
    # A tool call on the final turn is not executed: its results would land in
    # a request that never happens, so the credit stays unspent.
    assert tools.searched == ["acme hiring 0", "acme hiring 1"]


@pytest.mark.asyncio
async def test_a_final_answer_ends_the_loop(monkeypatch):
    fake_model = _scripted_model([FINAL_ANSWER])
    monkeypatch.setattr(agent, "chat_turn", fake_model)
    tools = _FakeTools()
    result = await run_agent(
        POSTING, system_prompt="system", tools=tools, limits=AgentLimits()
    )
    assert result.text == FINAL_ANSWER
    assert result.turns == 1
    assert result.searches == 0
    assert result.fetches == 0


@pytest.mark.asyncio
async def test_a_fetch_is_executed_and_framed_as_untrusted(monkeypatch):
    fake_model = _scripted_model([
        "TOOL: fetch\nARGUMENT: https://acme.example.com/careers",
        FINAL_ANSWER,
    ])
    monkeypatch.setattr(agent, "chat_turn", fake_model)
    tools = _FakeTools()
    result = await run_agent(
        POSTING, system_prompt="system", tools=tools, limits=AgentLimits()
    )
    assert tools.fetched == ["https://acme.example.com/careers"]
    assert result.fetches == 1
    # The fetched page is data, the same framing format_results gives search.
    assert "untrusted" in _all_text(fake_model.calls[1]).lower()


@pytest.mark.asyncio
async def test_a_refused_fetch_is_reported_and_the_loop_continues(monkeypatch):
    class _RefusingTools(_FakeTools):
        async def fetch(self, url, max_bytes):
            raise FetchRefused("resolves to a private or reserved address")

    fake_model = _scripted_model([
        "TOOL: fetch\nARGUMENT: http://127.0.0.1/admin",
        FINAL_ANSWER,
    ])
    monkeypatch.setattr(agent, "chat_turn", fake_model)
    tools = _RefusingTools()
    result = await run_agent(
        POSTING, system_prompt="system", tools=tools, limits=AgentLimits()
    )
    assert result.fetches == 0
    assert "refused" in _all_text(fake_model.calls[1]).lower()


def test_the_agent_limits_have_their_shipped_defaults(monkeypatch):
    settings = class_settings(monkeypatch)
    assert settings.agent_max_turns == 4
    assert settings.agent_max_searches == 3
    assert settings.agent_max_fetches == 4
    assert settings.agent_max_fetch_bytes == 200_000


def test_the_runtime_seam_resolves_the_limits_from_settings(monkeypatch):
    from app.services.scanner.dependencies import runtime

    monkeypatch.setattr("app.config.settings.agent_max_turns", 9)
    assert runtime.get_agent_limits().max_turns == 9


@pytest.mark.asyncio
async def test_the_first_search_is_the_reserved_anchor(monkeypatch):
    """One search is reserved for the employer's own record, built by code.

    An agent that spent all three on discriminating queries about the posting
    could come back with nothing about the employer — and both `confirmed` and
    `supported` need the employer's own pages. The anchor runs before the
    model's own query, and the model is told the code chose it.
    """
    fake_model = _scripted_model([
        "TOOL: search\nARGUMENT: acme hiring cebu",
        FINAL_ANSWER,
    ])
    monkeypatch.setattr(agent, "chat_turn", fake_model)
    tools = _FakeTools()
    result = await run_agent(
        POSTING,
        system_prompt="system",
        tools=tools,
        limits=AgentLimits(),
        company="Acme Corporation",
    )
    assert tools.searched == [
        "Acme Corporation company or employer",
        "acme hiring cebu",
    ]
    assert result.searches == 2
    assert "reserved" in _all_text(fake_model.calls[1]).lower()


@pytest.mark.asyncio
async def test_the_anchor_leaves_two_searches_for_the_agent(monkeypatch):
    """1 reserved + 2 chosen = the 3-search ceiling."""
    fake_model = _scripted_model([
        "TOOL: search\nARGUMENT: acme branch cebu",
        "TOOL: search\nARGUMENT: acme permit number",
        "TOOL: search\nARGUMENT: acme job title listing",
        FINAL_ANSWER,
    ])
    monkeypatch.setattr(agent, "chat_turn", fake_model)
    tools = _FakeTools()
    result = await run_agent(
        POSTING,
        system_prompt="system",
        tools=tools,
        limits=AgentLimits(),
        company="Acme Corporation",
    )
    assert tools.searched == [
        "Acme Corporation company or employer",
        "acme branch cebu",
        "acme permit number",
    ]
    assert result.searches == 3
    assert "budget" in _all_text(fake_model.calls[3]).lower()


@pytest.mark.asyncio
async def test_without_a_company_no_anchor_is_reserved(monkeypatch):
    fake_model = _scripted_model([
        "TOOL: search\nARGUMENT: acme hiring cebu",
        FINAL_ANSWER,
    ])
    monkeypatch.setattr(agent, "chat_turn", fake_model)
    tools = _FakeTools()
    result = await run_agent(
        POSTING, system_prompt="system", tools=tools, limits=AgentLimits()
    )
    assert tools.searched == ["acme hiring cebu"]
    assert result.searches == 1


@pytest.mark.asyncio
async def test_the_anchor_runs_even_when_the_models_own_calls_are_refused(monkeypatch):
    """The employer lookup is the point of the session; the model's own
    refused calls are still explained beside it."""
    fake_model = _scripted_model([
        "TOOL: search\nARGUMENT: acme scam",
        FINAL_ANSWER,
    ])
    monkeypatch.setattr(agent, "chat_turn", fake_model)
    tools = _FakeTools()
    result = await run_agent(
        POSTING,
        system_prompt="system",
        tools=tools,
        limits=AgentLimits(),
        company="Acme Corporation",
    )
    assert tools.searched == ["Acme Corporation company or employer"]
    assert result.searches == 1
    text = _all_text(fake_model.calls[1]).lower()
    assert "reserved" in text
    assert "refused" in text
