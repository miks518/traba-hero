"""`red` must mean a source contradicts a claim, not that nothing was found.

This is the rule that keeps small Philippine employers from being scored as
suspicious. A sole proprietorship with no website, no listing and no reviews is
the ordinary case, and it is the population this product exists for. If silence
scored, the most common real employer would be the most penalised one.

The two states are distinguished in the prompt prose the backend actually loads,
so this reads `VERIFY_PROMPT.md` and the in-module fallback rather than a
constant.
"""

from pathlib import Path

import pytest

from app.services.scanner.verification_prompt import (
    VERIFY_CLAIM_CATEGORIES,
    VERIFY_SYSTEM_PROMPT,
    _FALLBACK_VERIFY_PROMPT,
)

PROMPT = Path(__file__).resolve().parents[1] / "VERIFY_PROMPT.md"


@pytest.fixture(params=["file", "fallback"], ids=["VERIFY_PROMPT.md", "fallback"])
def prompt(request):
    if request.param == "file":
        return PROMPT.read_text(encoding="utf-8").lower()
    return _FALLBACK_VERIFY_PROMPT.lower()


def test_red_requires_a_contradiction(prompt):
    assert "contradict" in prompt, (
        "red must be defined as a source contradicting a claim — otherwise "
        "'nothing found' and 'contradicted' are the same state"
    )


def test_silence_is_not_red(prompt):
    assert any(
        phrase in prompt
        for phrase in (
            "never red",
            "not red",
            "yellow, not red",
            "nothing found is yellow",
        )
    ), "the prompt must state explicitly that an unconfirmed claim is yellow"


def test_green_confirms_and_adds_nothing(prompt):
    assert any(
        phrase in prompt
        for phrase in ("confirm", "supports the claim", "backs up")
    ), "green must mean a retrieved source supports the claim"


def test_no_verdict_words_in_the_output_rules(prompt):
    for word in ("legitimate", "fraudulent", "genuine"):
        assert f"never use {word}" in prompt or f"do not use {word}" in prompt or \
            f"never write {word}" in prompt, (
            f"the output rules must still ban {word} — this is the libel guardrail"
        )


def test_finding_must_not_name_a_status(prompt):
    for word in ("verified", "safe", "authorized"):
        assert word in prompt, (
            f"the prompt must forbid {word} in a finding — a status adjective is "
            "a conclusion, and the reader draws conclusions from a source they can open"
        )


def test_every_claim_category_is_documented():
    assert "channel" in VERIFY_CLAIM_CATEGORIES[0].lower() or any(
        "channel" in c.lower() for c in VERIFY_CLAIM_CATEGORIES
    ), "the impersonation check must be a category or it cannot be scored"
    assert any("location" in c.lower() or "branch" in c.lower()
               for c in VERIFY_CLAIM_CATEGORIES)


def test_scheme_corroboration_requires_the_same_scheme():
    body = (PROMPT.read_text(encoding="utf-8") + _FALLBACK_VERIFY_PROMPT).lower()
    assert "same scheme" in body or "this specific scheme" in body, (
        "a page about task-for-earning schemes generally establishes nothing "
        "about this posting and must not redden a category"
    )


# ---------------------------------------------------------------------------
# Strengthening of the two tests above that passed under a deliberate break.
# Both survive a mutation that removes the rule, which is worse than not having
# them, so they are pinned here in a form that does not.
# ---------------------------------------------------------------------------


def _finding_rule(prompt: str) -> str:
    """The FIELD RULES bullet for `finding`, scoped rather than whole-document.

    Scoping is the whole point: these words also occur in the green status rule
    ("not that the posting is safe") and inside worked examples, so a
    whole-document presence check cannot tell a prohibition from a mention.
    """
    bullets = [
        ln for ln in prompt.splitlines() if ln.strip().lower().startswith("- finding:")
    ]
    assert len(bullets) == 1, "the finding field rule must be findable and unique"
    return bullets[0].lower()


@pytest.fixture(params=["file", "fallback"], ids=["VERIFY_PROMPT.md", "fallback"])
def finding_rule(request):
    if request.param == "file":
        return _finding_rule(PROMPT.read_text(encoding="utf-8"))
    return _finding_rule(_FALLBACK_VERIFY_PROMPT)


def test_the_finding_rule_bans_the_status_words_rather_than_mentioning_them(finding_rule):
    """Mutation check: deleting the ban sentence entirely left the plan's
    `test_finding_must_not_name_a_status` passing, because "safe" survives in
    the green status rule and "verified"/"authorized" survived in the worked
    example beside it. Presence is not a prohibition.

    This asserts the words inside the `finding` bullet, where a ban has to
    live, and that the bullet carries a prohibition rather than an example.
    """
    for word in ("verified", "safe", "authorized", "legitimate"):
        assert word in finding_rule, (
            f"the finding rule must forbid {word}; found only as a passing "
            "mention elsewhere in the prompt"
        )
    assert any(
        marker in finding_rule
        for marker in ("never write", "do not write", "do not use", "never use")
    ), "the rule must prohibit these words, not merely mention them"


def test_both_prompt_copies_carry_the_same_scheme_rule_separately():
    """Mutation check: the plan's version concatenates the two copies, so it
    passes even when only the fallback has the rule — which is precisely the
    one-sided drift this prompt has suffered before.

    Each copy is checked on its own, because a deployment missing
    VERIFY_PROMPT.md verifies against the fallback alone and must get the same
    rule.
    """
    for name, copy in (
        ("VERIFY_PROMPT.md", PROMPT.read_text(encoding="utf-8").lower()),
        ("fallback", _FALLBACK_VERIFY_PROMPT.lower()),
    ):
        assert "same scheme" in copy or "this specific scheme" in copy, (
            f"{name} is missing the same-scheme rule; the two copies must agree "
            "on their own, not in combination"
        )


def test_the_tuple_the_schema_and_the_prose_name_the_same_categories():
    """Three places name the categories and they have drifted apart before.

    The tuple feeds the schema enum, and the prose tells the model what each
    one means. A category added to one and not the others is either
    unreachable (a strict enum refuses it) or invented (the model improvises a
    fourth), and `EXPECTED_CATEGORIES` in the parser is a fourth list that is
    deliberately still the old three.
    """
    from app.services.scanner.verification_prompt import VERIFY_RESPONSE_SCHEMA

    enum = VERIFY_RESPONSE_SCHEMA["properties"]["checks"]["items"]["properties"]["category"]["enum"]
    assert tuple(enum) == VERIFY_CLAIM_CATEGORIES

    for copy in (PROMPT.read_text(encoding="utf-8"), _FALLBACK_VERIFY_PROMPT):
        for category in VERIFY_CLAIM_CATEGORIES:
            assert f'"{category}"' in copy, (
                f"{category} is in the schema enum but not described in the prose"
            )