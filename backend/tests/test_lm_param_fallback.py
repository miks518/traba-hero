"""Parameter-rejection fallback in lm_client.

A model ID on OpenRouter can route to several endpoints, and not all of them
support `reasoning` or schema-enforced output. The request is therefore retried
without the offending parameter and then left out for the rest of the process.

The load-bearing property is that a rejection is *recognised*. OpenRouter reports
an unroutable parameter combination as a 404, not the 400 the fallback was
written against, so a model with no structured-output endpoint took the whole
verification request down instead of degrading to the text parser.

No live provider calls: the client is faked and the error bodies are the real
ones from a failing deployment, not invented.
"""

import pytest

from app.services import lm_client


ROUTING_404_BODY = (
    "Error code: 404 - {'error': {'message': 'No endpoints found that can handle "
    "the requested parameters. To learn more about provider routing, visit: "
    "https://openrouter.ai/docs/guides/provider-selection', 'code': 404, "
    "'metadata': {'routing_funnel': [{'step': 'Initial Endpoints', "
    "'endpoint_count': 1}], 'failed_routing_step': 'Filter by Parameters'}}}"
)


class FakeAPIError(Exception):
    """Stands in for the OpenAI SDK's provider exceptions.

    `_rejected_param` reads `status_code` off the exception rather than isinstance-
    checking it, so a duck-typed stand-in exercises the same path without
    depending on a specific SDK exception class.
    """

    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def _fake_client(monkeypatch, failures, captured):
    """Return a client whose `create` fails `failures` times, then succeeds."""

    class Completions:
        async def create(self, **kwargs):
            captured.append(kwargs.get("extra_body") or {})
            if len(captured) <= len(failures):
                raise failures[len(captured) - 1]
            return "ok"

    class Chat:
        completions = Completions()

    class Client:
        chat = Chat()

    monkeypatch.setattr(lm_client, "_get_client", lambda: Client())


@pytest.fixture(autouse=True)
def _clear_dropped_params():
    """The dropped-parameter set is process-wide state; isolate each test."""
    lm_client._unsupported_params.clear()
    yield
    lm_client._unsupported_params.clear()


class TestRecognisingARejection:
    def test_a_routing_404_is_a_parameter_rejection(self):
        """OpenRouter's answer to 'no endpoint takes these parameters'."""
        exc = FakeAPIError(404, ROUTING_404_BODY)

        assert lm_client._rejected_param(exc, set()) == "structured"

    def test_structured_is_dropped_before_reasoning(self):
        """`provider.require_parameters` is the strictest routing constraint.

        It is the flag that turns an unroutable combination into a 404, so it is
        the first thing worth giving up. Reasoning is far more widely supported
        and is last to go.
        """
        exc = FakeAPIError(404, ROUTING_404_BODY)

        assert lm_client._rejected_param(exc, {"structured"}) == "reasoning"

    def test_a_plain_400_naming_a_parameter_still_works(self):
        exc = FakeAPIError(400, "Error: reasoning is not supported by this endpoint")

        assert lm_client._rejected_param(exc, set()) == "reasoning"

    def test_a_400_naming_structured_output_still_works(self):
        exc = FakeAPIError(400, "Error: response_format json_schema is not supported")

        assert lm_client._rejected_param(exc, set()) == "structured"

    def test_a_genuine_404_is_not_treated_as_a_parameter_rejection(self):
        """A model that does not exist is a config error, not a capability gap.

        Dropping parameters would not make the request routable, so the 404 has
        to propagate — otherwise a typo in MODEL_NAME would be reported as the
        model having no structured output, which is a different and wrong fix.
        """
        exc = FakeAPIError(404, "Error code: 404 - {'error': {'message': 'No endpoints found for stealth/nonexistent'}}")

        assert lm_client._rejected_param(exc, set()) is None

    def test_an_unrelated_404_is_not_a_parameter_rejection(self):
        exc = FakeAPIError(404, "Error code: 404 - {'error': {'message': 'Not Found'}}")

        assert lm_client._rejected_param(exc, set()) is None

    def test_a_429_is_never_a_parameter_rejection(self):
        """A rate limit is a real condition and must reach the caller."""
        exc = FakeAPIError(429, "Rate limit exceeded")

        assert lm_client._rejected_param(exc, set()) is None


class TestTheRetryActuallyRetries:
    @pytest.mark.asyncio
    async def test_a_routing_404_retries_without_structured_output(self, monkeypatch):
        """The user's failure: scan works, verify dies on its second AI call.

        `/api/scan` sends labeled text and no `response_format`, so it routes
        fine. `/api/verify` sends `response_format` plus
        `provider.require_parameters`, the model has no endpoint supporting
        that, and the 404 propagated out of the SSE stream.
        """
        captured = []
        _fake_client(
            monkeypatch,
            [FakeAPIError(404, ROUTING_404_BODY)],
            captured,
        )

        result = await lm_client._create_completion(
            model="stealth/space-bunny-alpha",
            messages=[],
            _structured={
                "response_format": {"type": "json_schema"},
                "provider": {"require_parameters": True},
            },
        )

        assert result == "ok"
        # First attempt carried the schema, the retry must not.
        assert "response_format" in captured[0]
        assert "response_format" not in captured[1]
        # require_parameters travels with the schema, so it goes too.
        assert "provider" not in captured[1]

    @pytest.mark.asyncio
    async def test_structured_is_remembered_for_the_rest_of_the_process(self, monkeypatch):
        """A second verification must not re-pay for the same failed request."""
        captured = []
        # One routing 404, then everything succeeds.
        _fake_client(monkeypatch, [FakeAPIError(404, ROUTING_404_BODY)], captured)

        await lm_client._create_completion(
            model="m",
            messages=[],
            _structured={"response_format": {"type": "json_schema"}},
        )
        assert "structured" in lm_client._unsupported_params

        # A later, unrelated call must not carry the schema at all.
        await lm_client._create_completion(
            model="m",
            messages=[],
            _structured={"response_format": {"type": "json_schema"}},
        )

        assert "response_format" not in captured[-1]

    @pytest.mark.asyncio
    async def test_the_404_still_propagates_once_both_parameters_are_gone(self, monkeypatch):
        """Dropping everything must not turn an unroutable request into a silent
        success — and it must not loop."""
        captured = []
        _fake_client(
            monkeypatch,
            [FakeAPIError(404, ROUTING_404_BODY)] * 3,
            captured,
        )

        with pytest.raises(FakeAPIError):
            await lm_client._create_completion(
                model="m",
                messages=[],
                _structured={"response_format": {"type": "json_schema"}},
            )

        # structured, then reasoning, then give up.
        assert len(captured) == 3
