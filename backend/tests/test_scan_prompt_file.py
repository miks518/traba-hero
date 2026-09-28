"""The scan prompt must not allow a red flag about something's absence.

A scan was returning "does not ask for a processing fee" as a red flag. That is
a flag about what the posting does NOT contain, which can never be evidence of
anything. The rule has to be in the prompt text the backend actually loads:
`SYSTEM_PROMPT.md` is the hand-shortened file that ships, and it had lost the
guard that `prompts.py`'s longer field rules still carried.
"""

from pathlib import Path

PROMPT = Path(__file__).resolve().parents[1] / "SYSTEM_PROMPT.md"
FALLBACK_RULES = Path(__file__).resolve().parents[1] / "app/services/scanner/prompts.py"

text = PROMPT.read_text(encoding="utf-8")
rules = FALLBACK_RULES.read_text(encoding="utf-8")
low = text.lower()


def test_prompt_forbids_flagging_an_absence():
    assert "does not" in low
    assert any(
        phrase in low
        for phrase in (
            "never flag the absence",
            "not flag what is missing",
            "flag only what the posting contains",
            "never about what the posting does not contain",
            "absence of something",
        )
    ), "the prompt must state that a flag describes what the posting contains, not what it lacks"


def test_prompt_requires_the_flag_to_be_quotable():
    """A flag must name something the reader can point at in the posting."""
    assert any(
        phrase in low
        for phrase in (
            "point to",
            "quote",
            "exactly as written",
        )
    ), "a flag must be traceable to text in the posting"


def test_prompt_forbids_naming_a_pattern_without_its_element():
    """'Advance-fee fraud' may only be named when the fee element is present."""
    assert (
        "name no pattern" in low or "unless the posting actually contains" in low
    ), "a scam pattern may not be named unless the posting contains its concrete element"
    # The pattern's element must be spelled out, not left to the model's judgement.
    assert "processing fee" in low or "asks the applicant for money" in low


def test_prompt_says_absent_salary_is_not_a_flag():
    assert "salary" in low
    assert any(
        phrase in low
        for phrase in (
            "states no salary",
            "does not state a salary",
            "no salary",
        )
    ), "a posting that states no salary must not be flagged for it"


def test_the_fallback_prompt_carries_the_same_guard():
    """prompts.py builds FALLBACK_SYSTEM_PROMPT, used when the file is missing.

    It must not reintroduce the absence-flag bug, so the guard belongs in both.
    """
    low_rules = rules.lower()
    assert any(
        phrase in low_rules
        for phrase in (
            "only for something you can point to",
            "never invent a flag",
        )
    )
    assert "do not flag" in low_rules, "the fallback must keep its do-not-flag list"


def test_prompt_keeps_the_never_invent_rule():
    assert "never invent" in low
