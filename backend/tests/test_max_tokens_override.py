"""Per-endpoint max_tokens.

`AI_MAX_TOKENS` was documented as the budget knob but only the scan honoured it.
Every other endpoint passed a hardcoded literal, so the four values were
coincidentally equal to the env default and the skew was invisible: raise
AI_MAX_TOKENS and the scan grew while verification stayed put.

The literals are gone. The budget is now resolved per endpoint, mirroring
`resolve_model` — a model and the token budget it needs are the same axis, and
only the endpoints that genuinely differ get a knob.

The load-bearing property is that resolution is total. Blank, zero, or a
non-numeric value must fall back to the shared budget rather than reach the
provider, where a bad `max_tokens` is a request it may reject outright.
"""

import pytest

from app.config import Settings
from app.services import lm_client

REAL_CHAT = lm_client.chat


class TestResolveMaxTokens:
    def test_falls_back_to_the_shared_budget(self):
        s = Settings(_env_file=None, ai_max_tokens=2048)

        assert s.resolve_max_tokens("verify") == 2048
        assert s.resolve_max_tokens("scan") == 2048
        assert s.resolve_max_tokens("resume") == 2048

    def test_an_override_wins_for_that_endpoint_only(self):
        s = Settings(
            _env_file=None,
            ai_max_tokens=2048,
            ai_max_tokens_verify="4096",
        )

        assert s.resolve_max_tokens("verify") == 4096
        assert s.resolve_max_tokens("scan") == 2048

    def test_the_offer_call_follows_the_verify_budget(self):
        """Both ask for schema-enforced JSON, so they share a budget.

        They were 2048 and 1536 for no reason anyone recorded; a reasoning model
        needs the room more on the longer of the two, and a split budget is two
        things to tune for one prompt shape.
        """
        s = Settings(_env_file=None, ai_max_tokens=2048, ai_max_tokens_verify="4096")

        assert s.resolve_max_tokens("offer") == 4096

    def test_a_blank_override_falls_back(self):
        """A blank line in a .env must not become a request the provider rejects."""
        s = Settings(_env_file=None, ai_max_tokens=2048, ai_max_tokens_verify="   ")

        assert s.resolve_max_tokens("verify") == 2048

    def test_a_non_numeric_override_falls_back(self):
        """A typo costs recall, not a verdict — same rule as the search depth."""
        s = Settings(_env_file=None, ai_max_tokens=2048, ai_max_tokens_verify="lots")

        assert s.resolve_max_tokens("verify") == 2048

    def test_a_zero_override_falls_back(self):
        s = Settings(_env_file=None, ai_max_tokens=2048, ai_max_tokens_verify="0")

        assert s.resolve_max_tokens("verify") == 2048

    def test_a_padded_numeric_override_is_accepted(self):
        s = Settings(_env_file=None, ai_max_tokens=2048, ai_max_tokens_verify=" 4096 ")

        assert s.resolve_max_tokens("verify") == 4096


class TestTheBudgetIsWired:
    """Resolution is worthless if the callers never ask for it.

    The hardcoded literals this replaced all sat at the call site, so the only
    way to catch a regression is to assert on the value that reaches the request
    body rather than on the resolver alone.
    """

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "endpoint,attribute,configured,expected",
        [
            ("verify", "ai_max_tokens_verify", "4096", 4096),
            ("offer", "ai_max_tokens_verify", "4096", 4096),
            ("scan", "ai_max_tokens_scan", "1024", 1024),
        ],
    )
    async def test_each_endpoint_sends_its_own_budget(
        self, monkeypatch, endpoint, attribute, configured, expected
    ):
        # Configured as a string, because that is what a .env delivers and what
        # lets a blank value be meaningful instead of a validation error.
        captured = {}

        class Completions:
            async def create(self, **kwargs):
                captured.update(kwargs)
                msg = type("M", (), {"content": "ok", "model_extra": {}})()
                return type("R", (), {"choices": [type("C", (), {"message": msg})()]})()

        class Client:
            chat = type("Chat", (), {"completions": Completions()})()

        monkeypatch.setattr(lm_client, "_get_client", lambda: Client())
        monkeypatch.setattr(lm_client.settings, "ai_max_tokens", 2048)
        monkeypatch.setattr(lm_client.settings, "ai_max_tokens_scan", "1024")
        monkeypatch.setattr(lm_client.settings, attribute, configured)

        # No max_tokens passed: resolution has to happen inside the client.
        await REAL_CHAT([{"role": "user", "content": "hi"}], endpoint=endpoint)

        assert captured["max_tokens"] == expected
