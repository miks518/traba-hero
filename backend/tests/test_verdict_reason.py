"""The one-line verdict reason.

The report panel's verdict block has two parts: an authored headline derived
from the level, and one sentence saying why, for *this* posting. The headline
is authored so it cannot drift between runs. This field is the reason it is not
also authored â€” the reason has to reference what the posting actually said, and
only the model has read it.

Three properties are load-bearing:

1. **It is capped.** A one-line slot that accepts a paragraph will eventually
   hold a paragraph, and the block is the first thing on the panel.
2. **It is screened before it reaches the panel.** This is the most prominent
   sentence the product emits and the only one a model writes, so it carries
   the tone ban the prompts state: no accusation, no hedge, no absolute. A
   rejected reason degrades the block to the authored headline alone, which is
   safe, rather than showing the reader a conclusion.
3. **It is optional on read.** A verification recorded before this field, or a
   provider that ignored it, must still render.
"""

import pytest

from app.services.scanner.verification_flow import _read_verify_output
from app.services.scanner.verification_prompt import (
    VERIFY_RESPONSE_SCHEMA,
    verdict_reason_is_clean,
)


def _json(**overrides):
    payload = {
        "checks": [
            {
                "category": "Channel Match",
                "status": "red",
                "finding": "The posting directs applicants to a third-party domain.",
                "source_title": "Recruitment notice",
                "source_url": "https://example.com/notice",
            }
        ],
        "evidence": [],
        "report": "The employer's own domain does not host this posting.",
        "recommendation": "Ask the recruiter to confirm the address on the company website.",
        "risk_level": "high",
        "risk_score": 70,
    }
    payload.update(overrides)
    return payload


# --- the schema ----------------------------------------------------------


def test_the_schema_carries_the_reason_and_requires_it():
    assert "verdict_reason" in VERIFY_RESPONSE_SCHEMA["properties"]
    assert "verdict_reason" in VERIFY_RESPONSE_SCHEMA["required"]


def test_the_schema_caps_the_reason_at_a_length_a_one_line_slot_can_hold():
    """A cap the provider enforces is better than a cap this code truncates to:
    truncation produces a sentence that ends mid-clause, which reads as a bug.
    """
    prop = VERIFY_RESPONSE_SCHEMA["properties"]["verdict_reason"]

    assert prop.get("maxLength") == 140


# --- reading it ----------------------------------------------------------


def test_the_reason_is_read_from_the_json():
    _, _, _, _, _, _, _, reason, _assessments = _read_verify_output(
        '{"checks": [], "evidence": [], "report": "r", "recommendation": "x", '
        '"risk_level": "high", "risk_score": 70, '
        '"verdict_reason": "This post asks you to send application documents to a third-party site."}'
    )

    assert reason == "This post asks you to send application documents to a third-party site."


def test_an_absent_reason_is_empty_rather_than_an_error():
    """A verification recorded before this field must still render. The
    headline carries the verdict on its own; the reason is an addition.
    """
    _, _, _, _, _, _, _, reason, _assessments = _read_verify_output(
        '{"checks": [], "evidence": [], "report": "r", "recommendation": "x", '
        '"risk_level": "low", "risk_score": 10}'
    )

    assert reason == ""


def test_a_blank_reason_is_empty():
    _, _, _, _, _, _, _, reason, _assessments = _read_verify_output(
        '{"checks": [], "evidence": [], "report": "r", "recommendation": "x", '
        '"risk_level": "low", "risk_score": 10, "verdict_reason": "   "}'
    )

    assert reason == ""


# --- the screen ----------------------------------------------------------


@pytest.mark.parametrize(
    "reason",
    [
        "This is a scam recruitment post.",
        "The posting is fraudulent and asks for an advance fee.",
        "This looks like a fake employer.",
        "The employer is legitimate, so this is safe to apply to.",
        "The posting is probably a scam.",
        "This appears to be an advance-fee scheme.",
        "This suggests the employer does not exist.",
        "You will always lose money to this posting.",
        "This is definitely a scam.",
    ],
)
def test_a_reason_breaking_the_tone_rules_is_dropped(reason):
    """The single most visible sentence in the product, and the only one a
    model writes.

    A verdict naming a post a scam is the libel exposure the whole prompt rule
    set exists to prevent, and putting it in the panel's headline slot would
    make it the most prominent instance of exactly that.
    """
    assert verdict_reason_is_clean(reason) is False


@pytest.mark.parametrize(
    "reason",
    [
        "This post asks you to pay a fee before you are hired.",
        "It sends your documents to a site that is not the employer's own.",
        "The pay offered is far above the usual range for this role.",
        "Nothing in the post asks for money.",
        "The employer could not be found online, so its registration is unconfirmed.",
    ],
)
def test_an_ordinary_reason_survives_the_screen(reason):
    """The overcorrection guard.

    A reason that names what the posting *asks for* is the whole point of the
    slot. Screening those would leave the block with nothing but an authored
    headline and no explanation, which is the panel working least.
    """
    assert verdict_reason_is_clean(reason) is True


def test_a_banned_reason_leaves_the_verdict_intact():
    """Degradation, not failure. The level and the checks are unaffected; only
    the sentence is withheld, so the reader still gets the verdict.
    """
    items, _, _, _, _, level, score, reason, _assessments = _read_verify_output(
        '{"checks": [], "evidence": [], "report": "r", "recommendation": "x", '
        '"risk_level": "critical", "risk_score": 95, '
        '"verdict_reason": "This is definitely a scam."}'
    )

    assert reason == ""
    assert level == "critical"
    assert score == 95


# --- the wire ------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_reason_reaches_the_wire():
    """The reader is not the contract; the SSE payload is.

    A field that is read and never emitted is a field the panel never sees, and
    the panel's most prominent slot would be empty for a reason that looks like
    a model failure rather than a wiring gap.
    """
    from unittest.mock import patch

    from httpx import ASGITransport, AsyncClient

    import json

    from app.main import app

    payload = json.dumps({
        "checks": [{
            "category": "Channel Match",
            "status": "red",
            "finding": "Applicants are sent to a domain the employer does not control.",
            "source_title": "Notice",
            "source_url": "https://notacme.example/apply",
        }],
        "evidence": [],
        "report": "The employer's own domain does not host this posting.",
        "recommendation": "Ask the recruiter to confirm the address on the company website.",
        "risk_level": "high",
        "risk_score": 70,
        "verdict_reason": "It sends your documents to a site that is not the employer's own.",
    })

    with patch("app.routers.scan.chat", return_value=payload):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/verify",
                json={"company_name": "Acme Corp", "job_summary": "Developer at Acme Corp"},
            )

    assert resp.status_code == 200
    assert '"verdictReason"' in resp.text
    assert "not the employer&#39;s own" in resp.text or "not the employer's own" in resp.text


@pytest.mark.asyncio
async def test_a_banned_reason_reaches_the_wire_as_empty():
    """End to end, so the screen cannot be bypassed by a caller that sets the
    field directly on the payload.
    """
    from unittest.mock import patch

    from httpx import ASGITransport, AsyncClient

    import json

    from app.main import app

    payload = json.dumps({
        "checks": [{
            "category": "Channel Match",
            "status": "red",
            "finding": "Applicants are sent to a domain the employer does not control.",
            "source_title": "Notice",
            "source_url": "https://notacme.example/apply",
        }],
        "evidence": [],
        "report": "r",
        "recommendation": "x",
        "risk_level": "critical",
        "risk_score": 95,
        "verdict_reason": "This is definitely a scam.",
    })

    with patch("app.routers.scan.chat", return_value=payload):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/verify",
                json={"company_name": "Acme Corp", "job_summary": "Developer at Acme Corp"},
            )

    assert '"verdictReason": ""' in resp.text
    assert "definitely a scam" not in resp.text
    # The model's `risk_level` is no longer the verdict. This response carries
    # no usable check and no channel facts, so the code has nothing to score and
    # emits no verdict. The sentence is withheld and the model's "critical" did
    # not reach the wire - which is the point of moving the level into code.
    assert '"verdict": "critical"' not in resp.text
    assert '"verdict": null' in resp.text
    assert '"riskLevel"' not in resp.text


# --- the prompt contract -------------------------------------------------


def test_the_prompt_file_states_the_rule():
    from app.services.scanner.verification_prompt import load_verify_prompt

    prompt = load_verify_prompt()

    assert "verdict_reason" in prompt
    assert "one sentence" in prompt.lower()


def test_the_fallback_prompt_states_the_rule():
    """Same drift class as the scan fallback: `load_verify_prompt()` reads the
    file, so a test against it alone proves nothing about the copy a deployment
    ships without it.
    """
    from app.services.scanner.verification_prompt import _FALLBACK_VERIFY_PROMPT

    assert "verdict_reason" in _FALLBACK_VERIFY_PROMPT
    assert "one sentence" in _FALLBACK_VERIFY_PROMPT.lower()
