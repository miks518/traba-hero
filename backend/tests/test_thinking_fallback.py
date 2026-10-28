"""The thinking-off fallback.

A model can accept a thinking-disabled request and still fail it: some
reasoning models deliberate and return no content at all, which surfaces as
`EmptyModelResponse` and reads to the user as "The AI service returned no
content". A provider that rejects `enabled: false` outright is already
recovered by the parameter-drop fallback in `test_lm_param_fallback.py`; the
gap this file pins is the accepted-but-empty shape.

The contract: a request that went out with thinking disabled and came back
with nothing is retried once with thinking enabled. If the retry produces
content, the model is remembered for the process so later requests start with
thinking on instead of re-paying the doomed attempt. A model that fails both
ways is not remembered, and a request that never disabled thinking is never
retried.

No live provider calls: the client is faked, and the empty shapes are the ones
the streaming and non-streaming paths actually produce.
"""

import pytest

from app.services import lm_client
from app.services.lm_client import EmptyModelResponse

# The offline fixture in conftest patches `lm_client.chat` and
# `lm_client.chat_stream_pieces` with canned fakes. These tests exercise the
# real functions against a faked *client* instead, so the real functions are
# captured here, at import — before any fixture has patched them — and
# restored for the duration of each test. Nothing reaches a live provider:
# `_get_client` is replaced per test.
_REAL_CHAT = lm_client.chat
_REAL_STREAM = lm_client.chat_stream_pieces


@pytest.fixture(autouse=True)
def _use_real_lm_functions(monkeypatch):
    monkeypatch.setattr(lm_client, "chat", _REAL_CHAT)
    monkeypatch.setattr(lm_client, "chat_stream_pieces", _REAL_STREAM)


class FakeDelta:
    """A streaming delta. `model_extra` stands in for OpenRouter's reasoning
    fields, which the OpenAI SDK models do not declare."""

    def __init__(self, content=None):
        self.content = content
        self.refusal = None
        self.model_extra = {}


class FakeChoice:
    def __init__(self, delta=None, finish_reason=None):
        self.delta = delta
        self.finish_reason = finish_reason


class FakeChunk:
    def __init__(self, choice=None):
        self.choices = [choice] if choice else []
        self.model_extra = {}


class FakeCompletion:
    """A non-streaming completion. `reasoning` mirrors the reasoning-only
    output an unmanaged thinking model produces when it answers nothing."""

    def __init__(self, content="", reasoning=""):
        extra = {"reasoning": reasoning} if reasoning else {}
        self.choices = [
            type("Choice", (), {"message": type("Message", (), {"content": content, "model_extra": extra})()})()
        ]


async def _stream(chunks):
    for chunk in chunks:
        yield chunk


def _fake_client(monkeypatch, responses, captured):
    """A client whose `create` walks `responses` in order.

    A response may be an exception (raised), a list of chunks (returned as a
    stream), or anything else (returned as a completion). Every call's kwargs
    are captured so tests can read what actually went out.
    """

    class Completions:
        async def create(self, **kwargs):
            captured.append(kwargs)
            response = responses[len(captured) - 1]
            if isinstance(response, Exception):
                raise response
            if isinstance(response, list):
                return _stream(response)
            return response

    class Chat:
        completions = Completions()

    class Client:
        chat = Chat()

    monkeypatch.setattr(lm_client, "_get_client", lambda: Client())


@pytest.fixture(autouse=True)
def _clear_process_state():
    """Both memories are process-wide state; isolate each test."""
    lm_client._unsupported_params.clear()
    lm_client._thinking_required_models.clear()
    yield
    lm_client._unsupported_params.clear()
    lm_client._thinking_required_models.clear()


class TestTheEmptyResponseFallback:
    @pytest.mark.asyncio
    async def test_a_thinking_off_request_that_returns_nothing_is_retried_with_thinking_on(self, monkeypatch):
        captured = []
        _fake_client(
            monkeypatch,
            [FakeCompletion(content="", reasoning="a long deliberation"), FakeCompletion(content="VALID: true")],
            captured,
        )

        result = await lm_client.chat([{"role": "user", "content": "x"}], thinking=False)

        assert result == "VALID: true"
        assert captured[0]["extra_body"]["reasoning"]["enabled"] is False
        assert captured[1]["extra_body"]["reasoning"]["enabled"] is True

    @pytest.mark.asyncio
    async def test_the_retry_keeps_the_structured_output_body(self, monkeypatch):
        """`/api/verify` sends its schema with `thinking`; a fallback that
        dropped the schema would turn a verification into unparsed prose."""
        captured = []
        _fake_client(
            monkeypatch,
            [FakeCompletion(content=""), FakeCompletion(content="{}")],
            captured,
        )
        schema = {"response_format": {"type": "json_schema"}}

        result = await lm_client.chat(
            [{"role": "user", "content": "x"}], response_format=schema, thinking=False
        )

        assert result == "{}"
        assert "response_format" in captured[1]["extra_body"]

    @pytest.mark.asyncio
    async def test_a_successful_retry_remembers_the_model(self, monkeypatch):
        captured = []
        _fake_client(
            monkeypatch,
            [FakeCompletion(content=""), FakeCompletion(content="ok")],
            captured,
        )

        await lm_client.chat([{"role": "user", "content": "x"}], thinking=False)

        assert lm_client._thinking_required_models, "a retry that worked left no trace"

    @pytest.mark.asyncio
    async def test_a_remembered_model_starts_with_thinking_on(self, monkeypatch):
        """The whole point of the memory: the second request must not re-pay
        for the doomed thinking-off attempt."""
        captured = []
        _fake_client(
            monkeypatch,
            [FakeCompletion(content=""), FakeCompletion(content="ok"), FakeCompletion(content="ok again")],
            captured,
        )
        await lm_client.chat([{"role": "user", "content": "x"}], thinking=False)

        result = await lm_client.chat([{"role": "user", "content": "x"}], thinking=False)

        assert result == "ok again"
        assert len(captured) == 3, "the second request made a doomed attempt first"
        assert captured[2]["extra_body"]["reasoning"]["enabled"] is True

    @pytest.mark.asyncio
    async def test_thinking_on_requests_are_never_retried(self, monkeypatch):
        """The fallback exists for thinking that was *disabled*. A user who
        chose Advanced scan asked for thinking; one empty answer is reported,
        not silently redone."""
        captured = []
        _fake_client(monkeypatch, [FakeCompletion(content="")], captured)

        with pytest.raises(EmptyModelResponse):
            await lm_client.chat([{"role": "user", "content": "x"}], thinking=True)

        assert len(captured) == 1

    @pytest.mark.asyncio
    async def test_a_model_that_fails_both_ways_is_not_remembered(self, monkeypatch):
        """The memory records evidence that thinking-on works. A model that
        returns nothing either way has no such evidence, and memorising it
        would silently override the deployment's setting forever."""
        captured = []
        _fake_client(
            monkeypatch,
            [FakeCompletion(content=""), FakeCompletion(content="")],
            captured,
        )

        with pytest.raises(EmptyModelResponse):
            await lm_client.chat([{"role": "user", "content": "x"}], thinking=False)

        assert not lm_client._thinking_required_models

    @pytest.mark.asyncio
    async def test_an_unremembered_model_tries_thinking_off_again(self, monkeypatch):
        captured = []
        _fake_client(
            monkeypatch,
            [FakeCompletion(content=""), FakeCompletion(content=""), FakeCompletion(content="ok")],
            captured,
        )
        with pytest.raises(EmptyModelResponse):
            await lm_client.chat([{"role": "user", "content": "x"}], thinking=False)

        result = await lm_client.chat([{"role": "user", "content": "x"}], thinking=False)

        assert result == "ok"
        assert captured[2]["extra_body"]["reasoning"]["enabled"] is False

    @pytest.mark.asyncio
    async def test_the_deployment_default_counts_as_thinking_disabled(self, monkeypatch):
        """`thinking=None` with `AI_REASONING_ENABLED=false` puts the same
        `enabled: false` on the wire as the toggle does. The model that cannot
        honour one cannot honour the other."""
        monkeypatch.setattr(lm_client.settings, "ai_reasoning_enabled", False)
        captured = []
        _fake_client(
            monkeypatch,
            [FakeCompletion(content=""), FakeCompletion(content="ok")],
            captured,
        )

        result = await lm_client.chat([{"role": "user", "content": "x"}])

        assert result == "ok"
        assert captured[0]["extra_body"]["reasoning"]["enabled"] is False
        assert captured[1]["extra_body"]["reasoning"]["enabled"] is True

    @pytest.mark.asyncio
    async def test_the_provider_default_does_not_trigger_a_retry(self, monkeypatch):
        """With no reasoning body at all, the model is already at its provider
        default. A thinking-on retry would send the identical request."""
        monkeypatch.setattr(lm_client.settings, "ai_reasoning_enabled", None)
        captured = []
        _fake_client(monkeypatch, [FakeCompletion(content="")], captured)

        with pytest.raises(EmptyModelResponse):
            await lm_client.chat([{"role": "user", "content": "x"}])

        assert len(captured) == 1

    @pytest.mark.asyncio
    async def test_a_dropped_reasoning_parameter_does_not_trigger_a_retry(self, monkeypatch):
        """Once the provider has rejected `reasoning` outright, neither the
        thinking-off body nor a thinking-on one can be sent. The retry would be
        the same request twice."""
        monkeypatch.setattr(lm_client, "_unsupported_params", {"reasoning"})
        captured = []
        _fake_client(monkeypatch, [FakeCompletion(content="")], captured)

        with pytest.raises(EmptyModelResponse):
            await lm_client.chat([{"role": "user", "content": "x"}], thinking=False)

        assert len(captured) == 1


class TestTheStreamingFallback:
    @pytest.mark.asyncio
    async def test_an_empty_stream_is_retried_with_thinking_on(self, monkeypatch):
        """The empty-stream error is only ever raised after zero pieces were
        yielded, so the retry is invisible to the caller — the scan just runs
        longer."""
        captured = []
        _fake_client(
            monkeypatch,
            [
                [FakeChunk()],
                [FakeChunk(FakeChoice(FakeDelta(content="VALID:"))), FakeChunk(FakeChoice(FakeDelta(content=" true")))],
            ],
            captured,
        )

        pieces = [p async for p in lm_client.chat_stream_pieces([{"role": "user", "content": "x"}], thinking=False)]

        assert pieces == ["VALID:", " true"]
        assert captured[0]["extra_body"]["reasoning"]["enabled"] is False
        assert captured[1]["extra_body"]["reasoning"]["enabled"] is True

    @pytest.mark.asyncio
    async def test_a_content_stream_that_fails_is_not_retried(self, monkeypatch):
        """`EmptyModelResponse` only fires on a stream with no content, so a
        partial stream reaching the error path would mean duplicated output.
        There is no such path — this pins that a failed stream with content is
        simply reported, not redone."""
        captured = []
        _fake_client(monkeypatch, [[FakeChunk()]], captured)

        with pytest.raises(EmptyModelResponse):
            async for _ in lm_client.chat_stream_pieces([{"role": "user", "content": "x"}], thinking=True):
                pass

        assert len(captured) == 1

    @pytest.mark.asyncio
    async def test_a_streaming_retry_remembers_the_model(self, monkeypatch):
        captured = []
        _fake_client(
            monkeypatch,
            [
                [FakeChunk()],
                [FakeChunk(FakeChoice(FakeDelta(content="VALID: true")))],
                [FakeChunk(FakeChoice(FakeDelta(content="ok")))],
            ],
            captured,
        )
        first = [p async for p in lm_client.chat_stream_pieces([{"role": "user", "content": "x"}], thinking=False)]
        assert first == ["VALID: true"]

        second = [p async for p in lm_client.chat_stream_pieces([{"role": "user", "content": "x"}], thinking=False)]

        assert second == ["ok"]
        assert len(captured) == 3
        assert captured[2]["extra_body"]["reasoning"]["enabled"] is True


class TestTheMemoryIsConsultedAtSendTime:
    @pytest.mark.asyncio
    async def test_a_remembered_model_never_sends_thinking_off(self, monkeypatch):
        """The flip lives in `_create_completion`, so it holds for every caller
        of the client, not only the two paths that carry the fallback."""
        lm_client._thinking_required_models.add("m")
        captured = []
        _fake_client(monkeypatch, ["ok"], captured)

        await lm_client._create_completion(model="m", messages=[], _thinking=False)

        assert captured[0]["extra_body"]["reasoning"]["enabled"] is True


class TestTheDisabledCheck:
    def test_explicit_false_is_disabled(self):
        assert lm_client._reasoning_disabled(False) is True

    def test_explicit_true_is_not_disabled(self):
        assert lm_client._reasoning_disabled(True) is False

    def test_none_follows_the_deployment_setting(self, monkeypatch):
        monkeypatch.setattr(lm_client.settings, "ai_reasoning_enabled", False)
        assert lm_client._reasoning_disabled(None) is True

        monkeypatch.setattr(lm_client.settings, "ai_reasoning_enabled", None)
        assert lm_client._reasoning_disabled(None) is False

    def test_an_effort_only_body_is_not_disabled(self, monkeypatch):
        """`effort: low` with no `enabled` leaves thinking at the provider
        default — on, for a reasoning model — so there is nothing to fall back
        from."""
        monkeypatch.setattr(lm_client.settings, "ai_reasoning_enabled", None)
        monkeypatch.setattr(lm_client.settings, "ai_reasoning_effort", "low")

        assert lm_client._reasoning_disabled(None) is False

    def test_a_dropped_reasoning_parameter_is_not_disabled(self, monkeypatch):
        """The body would carry no reasoning either way, so a thinking-on retry
        cannot change the outcome."""
        monkeypatch.setattr(lm_client, "_unsupported_params", {"reasoning"})

        assert lm_client._reasoning_disabled(False) is False
