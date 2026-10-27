"""The Advanced-scan thinking override.

The frontend's checkbox sends `thinking` on the scan request. The backend must
honour it per request — `True` turns reasoning on even when
`AI_REASONING_ENABLED` defaults the deployment off, `False` turns it off even
when the deployment defaults it on, and no field keeps the configured
behaviour. The override lives in `_reasoning_params`, which is where the
deployment's own reasoning body is built, so the two can never disagree about
the shape of the payload.

No live provider calls: `_reasoning_params` is pure over settings.
"""

import pytest

from app.services import lm_client


def _with_reasoning_enabled(monkeypatch, value):
    monkeypatch.setattr(lm_client.settings, "ai_reasoning_enabled", value)


class TestThePerRequestOverride:
    def test_true_turns_reasoning_on_when_the_deployment_defaults_it_off(self, monkeypatch):
        # The user's own deployment: AI_REASONING_ENABLED=false, because
        # unmanaged thinking made every scan take minutes. The toggle is the
        # per-request choice to pay those minutes.
        _with_reasoning_enabled(monkeypatch, False)
        body = lm_client._reasoning_params(thinking=True)
        assert body["reasoning"]["enabled"] is True

    def test_false_turns_reasoning_off_when_the_deployment_defaults_it_on(self, monkeypatch):
        _with_reasoning_enabled(monkeypatch, True)
        body = lm_client._reasoning_params(thinking=False)
        assert body == {"reasoning": {"enabled": False}}

    def test_no_override_keeps_the_configured_behaviour(self, monkeypatch):
        _with_reasoning_enabled(monkeypatch, False)
        assert lm_client._reasoning_params(None) == {"reasoning": {"enabled": False}}
        _with_reasoning_enabled(monkeypatch, True)
        assert lm_client._reasoning_params(None)["reasoning"]["enabled"] is True

    def test_the_override_keeps_the_configured_effort(self, monkeypatch):
        # Thinking on means the deployment's own effort/cap settings ride along:
        # the toggle chooses whether to think, not how deeply.
        _with_reasoning_enabled(monkeypatch, False)
        monkeypatch.setattr(lm_client.settings, "ai_reasoning_effort", "low")
        body = lm_client._reasoning_params(thinking=True)
        assert body["reasoning"]["effort"] == "low"

    def test_the_override_reaches_the_request_body(self, monkeypatch):
        _with_reasoning_enabled(monkeypatch, False)
        body = lm_client._request_extra_body(None, thinking=True)
        assert body["reasoning"]["enabled"] is True

    def test_an_unsupported_reasoning_param_is_still_dropped_under_the_override(self, monkeypatch):
        # The provider-rejection memory outlives the override: a model that
        # rejected `reasoning` once must not have it forced back by the toggle.
        _with_reasoning_enabled(monkeypatch, False)
        monkeypatch.setattr(lm_client, "_unsupported_params", {"reasoning"})
        body = lm_client._request_extra_body(None, thinking=True)
        assert "reasoning" not in body

    def test_thinking_true_never_carries_a_max_tokens_cap(self, monkeypatch):
        # A cap truncates thinking and can make the provider re-attempt. The
        # toggle's whole point is letting the model finish thinking, so the
        # cap that guards the always-on default stays out of the override.
        _with_reasoning_enabled(monkeypatch, True)
        monkeypatch.setattr(lm_client.settings, "ai_reasoning_max_tokens", 1024)
        body = lm_client._reasoning_params(thinking=True)
        assert "max_tokens" not in body["reasoning"]


class TestTheScanRequestCarriesTheToggle:
    def test_the_field_defaults_to_off(self):
        from app.models.schemas import ScanRequest, ScanTextRequest, AnalyzeOfferRequest

        assert ScanRequest(images_base64=["dGVzdA=="]).thinking is False
        assert ScanTextRequest(text="x").thinking is False
        assert AnalyzeOfferRequest(text="x").thinking is False

    def test_the_field_is_accepted_on_all_three_scan_pipeline_requests(self):
        from app.models.schemas import ScanRequest, ScanTextRequest, AnalyzeOfferRequest

        assert ScanRequest(images_base64=["dGVzdA=="], thinking=True).thinking is True
        assert ScanTextRequest(text="x", thinking=True).thinking is True
        assert AnalyzeOfferRequest(text="x", thinking=True).thinking is True
