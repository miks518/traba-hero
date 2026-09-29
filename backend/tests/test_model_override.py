"""Per-endpoint model selection.

`/api/scan` and `/api/verify` ask the provider for different things. The scan
reads a screenshot and wants prose in a labelled format; verification wants a
JSON object matching a schema, which is a far narrower request — only some models
have an endpoint OpenRouter can route that to.

One `MODEL_NAME` for both means picking a model that satisfies the stricter of the
two, and the looser one then runs on a worse model than it needed. `AI_MODEL_*`
lets a deployment choose per call, and falls back to the shared model so an
existing deployment changes nothing by setting it.

The load-bearing property is that the fallback is total: a blank, absent, or
mistyped override must resolve to `MODEL_NAME`, never to a request for a model
that does not exist.
"""

import pytest

from app.config import Settings
from app.services import lm_client

# The autouse offline fixture replaces `lm_client.chat` with a fake, so calling
# the module attribute would test the fake. Bound at import time, before the
# fixture patches, so these tests exercise the real function — the same trick
# conftest.py uses to capture REAL_AI_CHAT.
REAL_CHAT = lm_client.chat


class TestTheKnobIsActuallyWired:
    """A config field nothing reads is a field that looks configured.

    `resolve_model` can be perfect and still change nothing if the callers never
    pass an endpoint name, so this asserts on the model that reaches the
    request body rather than on the resolver.
    """

    @pytest.mark.asyncio
    async def test_chat_sends_the_models_override(self, monkeypatch):
        captured = {}

        class Completions:
            async def create(self, **kwargs):
                captured.update(kwargs)
                msg = type("M", (), {"content": "ok", "model_extra": {}})()
                return type("R", (), {"choices": [type("C", (), {"message": msg})()]})()

        class Client:
            chat = type("Chat", (), {"completions": Completions()})()

        monkeypatch.setattr(lm_client, "_get_client", lambda: Client())
        monkeypatch.setattr(lm_client.settings, "ai_model_verify", "verify/model")

        await REAL_CHAT([{"role": "user", "content": "hi"}], endpoint="verify")

        assert captured["model"] == "verify/model"

    @pytest.mark.asyncio
    async def test_chat_without_an_endpoint_uses_the_shared_model(self, monkeypatch):
        """The default path must be byte-identical to before the knob existed."""
        captured = {}

        class Completions:
            async def create(self, **kwargs):
                captured.update(kwargs)
                msg = type("M", (), {"content": "ok", "model_extra": {}})()
                return type("R", (), {"choices": [type("C", (), {"message": msg})()]})()

        class Client:
            chat = type("Chat", (), {"completions": Completions()})()

        monkeypatch.setattr(lm_client, "_get_client", lambda: Client())
        monkeypatch.setattr(lm_client.settings, "ai_model_scan", "scan/model")
        monkeypatch.setattr(lm_client.settings, "model_name", "shared/model")

        await REAL_CHAT([{"role": "user", "content": "hi"}])

        assert captured["model"] == "shared/model"


class TestResolveModel:
    def test_uses_the_shared_model_when_no_override_is_set(self):
        s = Settings(_env_file=None, model_name="stealth/space-bunny-alpha")

        assert s.resolve_model("verify") == "stealth/space-bunny-alpha"
        assert s.resolve_model("scan") == "stealth/space-bunny-alpha"

    def test_an_override_wins_for_that_call_only(self):
        s = Settings(
            _env_file=None,
            model_name="stealth/space-bunny-alpha",
            ai_model_verify="some/structured-capable-model",
        )

        assert s.resolve_model("verify") == "some/structured-capable-model"
        # The scan is unaffected: the point is that the two can differ.
        assert s.resolve_model("scan") == "stealth/space-bunny-alpha"

    def test_a_blank_override_falls_back(self):
        """Blank is a misconfiguration, not a model named ''.

        Sending an empty model ID would be a 404 of its own, and a blank value in
        a .env is the most likely way to get one.
        """
        s = Settings(_env_file=None, model_name="shared/model", ai_model_verify="   ")

        assert s.resolve_model("verify") == "shared/model"

    def test_an_unknown_endpoint_name_falls_back(self):
        """A typo in the endpoint key must not silently produce a bad model."""
        s = Settings(_env_file=None, model_name="shared/model", ai_model_verify="other/model")

        assert s.resolve_model("verfy") == "shared/model"

    def test_a_whitespace_padded_override_is_trimmed(self):
        s = Settings(
            _env_file=None,
            model_name="shared/model",
            ai_model_verify="  padded/model  ",
        )

        assert s.resolve_model("verify") == "padded/model"

    def test_a_blank_shared_model_is_reported_rather_than_guessed(self):
        """No model configured at all is a deployment error, not a default.

        `chat()` substitutes 'local-model' when this is empty, which is what an
        LM Studio or Ollama setup would use. Returning something here would hide
        a missing MODEL_NAME behind a plausible-looking name.
        """
        s = Settings(_env_file=None, model_name="")

        assert s.resolve_model("verify") == ""

    def test_the_overrides_default_to_unset(self):
        """A deployment that sets nothing must behave exactly as before."""
        s = Settings(_env_file=None)

        assert s.ai_model_verify == ""
        assert s.ai_model_scan == ""
