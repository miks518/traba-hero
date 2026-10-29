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

# The real body from an NVIDIA NIM deployment (integrate.api.nvidia.com): its
# validator refuses the OpenRouter-only `provider` routing parameter outright,
# naming it in backticks — a phrasing none of the earlier hints matched.
NVIDIA_PROVIDER_400_BODY = (
    "Error code: 400 - {'message': 'Validation: Unsupported parameter(s): "
    "`provider`', 'type': 'Bad Request', 'code': 400}"
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

    def test_nvidias_400_naming_provider_in_backticks_is_recognised(self):
        """NVIDIA NIM refuses the OpenRouter-only routing parameter outright.

        Its validator phrases the rejection as "Unsupported parameter(s):
        `provider`", which none of the provider hints matched, so the 400
        propagated and /api/verify failed on every model that deployment
        offers — while /api/scan, which sends no `provider`, kept working.
        """
        exc = FakeAPIError(400, NVIDIA_PROVIDER_400_BODY)

        assert lm_client._rejected_param(exc, set()) == "provider"


class TestSamplingParameters:
    """`temperature` and friends are preferences, not capabilities.

    A provider that refuses one should cost the request nothing — the model has
    a default and will use it. The same is emphatically not true of `reasoning`
    or structured output, which change what comes back, so they are excluded from
    this group and `test_capability_parameters_are_not_treated_as_sampling`
    pins that.
    """

    def test_a_400_naming_a_sampling_parameter_is_recognised(self):
        exc = FakeAPIError(400, "Unsupported parameter: 'temperature' is not supported")

        assert lm_client._rejected_param(exc, set()) == "temperature"

    def test_a_complaint_about_the_value_is_also_recognised(self):
        """`temperature must be between 0 and 1` is not a statement about whether
        the parameter exists. Omitting it lets the provider apply its own
        default, which is the right degradation — and the alternative is failing
        a scan over a sampling preference."""
        exc = FakeAPIError(400, "temperature must be between 0 and 1")

        assert lm_client._rejected_param(exc, set()) == "temperature"

    def test_capability_parameters_are_not_treated_as_sampling(self):
        """The overcorrection, and the reason the two groups are separate lists.

        Recognising every rejected parameter and dropping it would silently
        remove structured output, and `/api/verify` would then parse prose and
        report nothing — a verification that renders empty with no error.
        """
        assert "reasoning" not in lm_client._GENERATION_PARAMS
        assert "structured" not in lm_client._GENERATION_PARAMS

    def test_a_400_that_names_nothing_is_still_unrecoverable(self):
        """The honest limit, recorded as a test so it cannot be forgotten.

        The real failure in production was `400 {'provider_name': 'AtlasCloud',
        'msg': 'bad request'}` — no parameter named, no field pointing at one.
        There is nothing to match on, so the fallback cannot help and the error
        propagates. Adding sampling parameters does not fix that case, and this
        test is what stops anyone reading the previous tests as though it did.
        """
        exc = FakeAPIError(400, "{'provider_name': 'AtlasCloud', 'msg': 'bad request'}")

        assert lm_client._rejected_param(exc, set()) is None

    @pytest.mark.asyncio
    async def test_the_retry_omits_the_rejected_sampling_parameter(self, monkeypatch):
        """Recognition alone would be worthless: the retry has to actually stop
        sending it, and these are top-level kwargs rather than `extra_body`
        entries, so there is no existing mechanism that would do it for free."""
        calls: list[dict] = []

        class Completions:
            async def create(self, **kwargs):
                calls.append(kwargs)
                if len(calls) == 1:
                    raise FakeAPIError(400, "Unsupported parameter: 'temperature'")
                return "ok"

        class Chat:
            completions = Completions()

        class Client:
            chat = Chat()

        monkeypatch.setattr(lm_client, "_get_client", lambda: Client())

        result = await lm_client._create_completion(model="m", messages=[], temperature=0.2)

        assert result == "ok"
        assert calls[0]["temperature"] == 0.2
        assert "temperature" not in calls[1], "the retry sent the rejected parameter again"

    @pytest.mark.asyncio
    async def test_a_dropped_sampling_parameter_is_not_sent_again(self, monkeypatch):
        """A second scan must not re-pay for the same discovery. This is the
        whole reason the unsupported set is consulted at send time and not only
        inside the retry loop."""
        calls: list[dict] = []

        class Completions:
            async def create(self, **kwargs):
                calls.append(kwargs)
                if len(calls) == 1:
                    raise FakeAPIError(400, "Unsupported parameter: 'temperature'")
                return "ok"

        class Chat:
            completions = Completions()

        class Client:
            chat = Chat()

        monkeypatch.setattr(lm_client, "_get_client", lambda: Client())

        await lm_client._create_completion(model="m", messages=[], temperature=0.2)
        await lm_client._create_completion(model="m", messages=[], temperature=0.2)

        assert len(calls) == 3
        assert "temperature" not in calls[2], (
            "the second request paid for the same rejection again"
        )


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

    @pytest.mark.asyncio
    async def test_nvidias_provider_rejection_retries_with_the_schema_intact(self, monkeypatch):
        """NVIDIA names one parameter; only that one may be dropped.

        Its 400 rejects `provider` while accepting `response_format`, so
        stripping the schema too would degrade /api/verify to prose parsing
        for a provider that never complained about it. The routing-404 case
        above is different: there the schema is what makes the request
        unroutable, so both go together.
        """
        captured = []
        _fake_client(monkeypatch, [FakeAPIError(400, NVIDIA_PROVIDER_400_BODY)], captured)

        result = await lm_client._create_completion(
            model="meta/llama-3.1-8b-instruct",
            messages=[],
            _structured={
                "response_format": {"type": "json_schema"},
                "provider": {"require_parameters": True},
            },
        )

        assert result == "ok"
        assert "provider" in captured[0]
        assert "provider" not in captured[1], "the retry sent the rejected parameter again"
        assert "response_format" in captured[1], "the schema was dropped though nothing rejected it"

    @pytest.mark.asyncio
    async def test_a_dropped_provider_parameter_is_not_sent_again(self, monkeypatch):
        """A second verification must not re-pay for the same rejection.

        `/api/verify` makes several AI calls per scan; each one builds a
        structured body carrying `provider`, so the drop has to hold for the
        rest of the process, not just the retry."""
        captured = []
        _fake_client(monkeypatch, [FakeAPIError(400, NVIDIA_PROVIDER_400_BODY)], captured)

        await lm_client._create_completion(
            model="m",
            messages=[],
            _structured={
                "response_format": {"type": "json_schema"},
                "provider": {"require_parameters": True},
            },
        )
        await lm_client._create_completion(
            model="m",
            messages=[],
            _structured={
                "response_format": {"type": "json_schema"},
                "provider": {"require_parameters": True},
            },
        )

        # First call: one rejection, one successful retry. Second call: no
        # failures left, and no `provider` in the request it sent.
        assert len(captured) == 3
        assert "provider" not in captured[1]
        assert "provider" not in captured[2], "a later request paid for the same rejection again"
