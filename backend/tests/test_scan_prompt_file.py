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


def test_prompt_does_not_instruct_a_missing_name_red_flag():
    """A missing name is a missing input, not a finding.

    Instructing one contradicted the "never flag the absence of something" rule
    in the same list, and it added risk-score weight for an input we lacked
    rather than for something wrong with the post. The frontend asks for the
    name instead.

    Previously this asserted on two exact strings ("company name not stated",
    "red flag: company name") and so missed a softer instruction elsewhere in
    the prompt that used different wording. It is a change detector that only
    caught the phrasing it was written against, so it now checks the severity
    list, which is where an instruction like this hides.
    """
    for body, label in ((text, "SYSTEM_PROMPT.md"), (rules, "prompts.py")):
        low = body.lower()
        assert "company name not stated" not in low, f"{label} still instructs the flag"
        assert "red flag: company name" not in low, f"{label} still instructs the flag"


def test_severity_list_never_offers_a_missing_name_as_an_example():
    """The severity list is where this instruction hid.

    "low: something like a missing employer name or a vague job description"
    sat in the shipped prompt while a later bullet banned exactly that. A model
    reading the severity examples took it as a sanctioned flag, emitted it at
    low severity, and the posting scored 4 for an input we simply never had.

    Only the part after each severity's colon is checked, because naming the
    phrase in order to forbid it is the opposite of instructing it. The low
    line may say "a missing employer name is NOT a low-severity flag"; what it
    must not do is offer one as an example of a low-severity finding.
    """
    for body, label in ((text, "SYSTEM_PROMPT.md"), (rules, "prompts.py")):
        block = _severity_block(body)
        assert block, f"{label} must have a Severity means: block"

        for line in block.splitlines():
            _, sep, example = line.partition(":")
            if not sep:
                continue
            # Prohibitions are allowed; examples are not.
            lowered = example.lower()
            if any(
                marker in lowered
                for marker in ("not a", "never", "do not", "don't", "is not")
            ):
                continue
            for phrase in (
                "missing employer name",
                "missing company name",
                "no employer name",
                "no company name",
                "employer not stated",
                "company not stated",
                "unnamed employer",
                "unclear employer",
                "vague job description",
            ):
                assert phrase not in lowered, (
                    f"{label} offers '{phrase}' as a severity example; a missing "
                    f"employer is a missing input, not a low-severity finding"
                )


def test_prompt_still_asks_for_the_employer_field():
    """The EMPLOYER NAME field is how the frontend detects the state."""
    assert "employer name" in low
    assert "not stated" in low


def _severity_block(body: str) -> str:
    """The text under "Severity means:", sub-bullets included.

    Scoped deliberately: the instruction that shipped lived in a sub-bullet
    three lines below the heading, so a slice of the heading's own line would
    not have seen it.

    Nesting depth decides membership rather than the bullet character, because
    this prompt writes sub-bullets under a `*` bullet as `    - high: ...`.
    A sub-bullet is therefore still part of the block even though it looks like
    the start of a new list.
    """
    lines = body.splitlines()
    start = next(
        (i for i, ln in enumerate(lines) if "severity means:" in ln.lower()),
        None,
    )
    if start is None:
        return ""

    def indent(ln: str) -> int:
        return len(ln) - len(ln.lstrip())

    base = indent(lines[start])
    block = [lines[start]]
    for ln in lines[start + 1:]:
        if not ln.strip():
            continue
        # Anything at or left of the heading's own level ends the block.
        if indent(ln) <= base:
            break
        block.append(ln)
    return "\n".join(block)


def _posting_analysis_block(body: str) -> str:
    """The text under the POSTING ANALYSIS field rule, sub-bullets included."""
    lines = body.splitlines()
    start = next(
        (i for i, ln in enumerate(lines) if ln.strip().startswith("- POSTING ANALYSIS")),
        None,
    )
    if start is None:
        return ""
    block = []
    for ln in lines[start + 1:]:
        # A new top-level field rule ends the block; an indented sub-bullet does not.
        if ln.strip() and not ln.startswith("  ") and ln.strip().startswith("- "):
            break
        block.append(ln)
    return "\n".join(block)


def test_posting_analysis_cannot_say_legitimate_or_scam():
    """A verdict naming a post a scam, or a company legitimate, is the libel risk.

    The opening line of the prompt lists these words, but a long prompt drifts:
    the rule has to be repeated in the field that produces the verdict, next to
    the instruction to base it on the reported flags.
    """
    for body, label in ((text, "SYSTEM_PROMPT.md"), (rules, "prompts.py")):
        block = _posting_analysis_block(body).lower()
        assert block, f"{label}: could not find the POSTING ANALYSIS field rule"
        assert "legitimate" in block and "scam" in block, (
            f"{label}: the POSTING ANALYSIS rule must name the words it forbids"
        )
        # It must also say what to write instead, or the model has no alternative.
        assert "what the posting asks for" in block, (
            f"{label}: the rule must give the model an allowed phrasing"
        )
