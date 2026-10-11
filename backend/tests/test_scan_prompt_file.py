"""The scan prompt must not allow an anomaly about something's absence.

A scan was returning "does not ask for a processing fee" as an anomaly. That is
a finding about what the posting does NOT contain, which can never be evidence of
anything. The rule has to be in the prompt text the backend actually loads:
`SYSTEM_PROMPT.md` is the hand-shortened file that ships, and it had lost the
guard that `prompts.py`'s longer field rules still carried.
"""

import re
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
    ), "the prompt must state that an anomaly describes what the posting contains, not what it lacks"


def test_prompt_requires_the_anomaly_to_be_quotable():
    """An anomaly must name something the reader can point at in the posting."""
    assert any(
        phrase in low
        for phrase in (
            "point to",
            "quote",
            "exactly as written",
        )
    ), "an anomaly must be traceable to text in the posting"


def test_prompt_forbids_naming_a_pattern_without_its_element():
    """'Advance-fee fraud' may only be named when the fee element is present."""
    assert (
        "name no pattern" in low or "unless the posting actually contains" in low
    ), "a scam pattern may not be named unless the posting contains its concrete element"
    # The pattern's element must be spelled out, not left to the model's judgement.
    assert "processing fee" in low or "asks the applicant for money" in low


def test_prompt_says_absent_salary_is_not_an_anomaly():
    assert "salary" in low
    assert any(
        phrase in low
        for phrase in (
            "states no salary",
            "does not state a salary",
            "no salary",
        )
    ), "a posting that states no salary must not be reported as an anomaly"


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


def test_prompt_does_not_instruct_a_missing_name_anomaly():
    """A missing name is a missing input, not a finding.

    Instructing one contradicted the "never flag the absence of something" rule
    in the same list, and it added risk-score weight for an input we lacked
    rather than for something wrong with the post. The frontend asks for the
    name instead.

    Previously this asserted on two exact strings ("company name not stated",
    "anomaly: company name") and so missed a softer instruction elsewhere in
    the prompt that used different wording. It is a change detector that only
    caught the phrasing it was written against, so it now checks the severity
    list, which is where an instruction like this hides.

    Both spellings are checked because the parser still accepts the pre-rename
    `RED FLAG:` line, so a prompt that reintroduced either would produce a
    finding the shipped prompt no longer sanctions.
    """
    for body, label in ((text, "SYSTEM_PROMPT.md"), (rules, "prompts.py")):
        low = body.lower()
        assert "company name not stated" not in low, f"{label} still instructs the anomaly"
        assert "anomaly: company name" not in low, f"{label} still instructs the anomaly"
        assert "red flag: company name" not in low, f"{label} still instructs the anomaly"


class TestTaskForEarningIsReportable:
    """A paid-task offer has to have a bucket, or the model has nowhere to put it.

    A screenshot of a DM saying "follow this task and after doing so you will
    earn your salary/reward" was reported at low risk. The reason is structural,
    not model quality, and it survives every model: the prompt's severity ladder
    is anchored on the *employer demanding something* — money, goods, a deposit.
    A task-for-earning offer asks for no payment, so nothing there matched, and
    the only things that made it not-a-job were the absences the prompt forbids
    reporting. The model had a prohibition and no permission.

    The fix is a positive anchor with a concrete element, in the same
    prohibition-plus-element form the three existing patterns use — not an
    enumeration of reportable things, which would just be a whitelist with
    different clothes.
    """

    def test_the_pattern_is_named_with_its_element(self):
        for body, label in ((text, "SYSTEM_PROMPT.md"), (rules, "prompts.py")):
            low = body.lower()
            assert "task-for-earning" in low, (
                f"{label} has no bucket for an offer of paid tasks; without one the "
                "model can only report the absences, which the prompt forbids"
            )

    def test_the_element_is_something_the_posting_actually_contains(self):
        """The element is the unit of work, not the reader's ignorance.

        Naming the absence of a role here would reintroduce the bug where a
        nameless posting scored 4: the trigger has to be text the posting
        contains.
        """
        for body, label in ((text, "SYSTEM_PROMPT.md"), (rules, "prompts.py")):
            low = body.lower()
            assert "discrete tasks" in low or "discrete task" in low, label
            assert "rather than describing a role" in low, label

    def test_work_then_payment_is_not_itself_an_anomaly(self):
        """The ordinary order must stay clean, or every job posting is flagged.

        This is the trap the case exposed: "do this task, then get paid" reads as
        work-before-money reversed, which is how most jobs are actually paid.
        What separates the two is the unit of work — a task or an earning event
        rather than a role.
        """
        for body, label in ((text, "SYSTEM_PROMPT.md"), (rules, "prompts.py")):
            low = body.lower()
            assert "ordinary order" in low, (
                f"{label} must say that work followed by payment is not itself an anomaly"
            )

    def test_mid_severity_has_this_example(self):
        """A pattern with no severity example has nowhere to land.

        `mid` carried a single example, so a model reaching for anything else
        fell back to `low` — which scores 4.
        """
        for body, label in ((text, "SYSTEM_PROMPT.md"), (rules, "prompts.py")):
            mid = _severity_line(body, "mid")
            assert mid, f"{label}: no mid severity line"
            assert "task" in mid.lower(), f"{label}: mid does not cover a paid-task offer"


def _severity_line(body: str, severity: str) -> str:
    """The text of one severity's line, or '' if absent."""
    for ln in body.splitlines():
        stripped = ln.strip().lstrip("-*").strip()
        if stripped.lower().startswith(f"{severity}:"):
            return stripped
    return ""


def test_severity_list_never_offers_a_missing_name_as_an_example():
    """The severity list is where this instruction hid.

    "low: something like a missing employer name or a vague job description"
    sat in the shipped prompt while a later bullet banned exactly that. A model
    reading the severity examples took it as a sanctioned anomaly, emitted it at
    low severity, and the posting scored 4 for an input we simply never had.

    Only the part after each severity's colon is checked, because naming the
    phrase in order to forbid it is the opposite of instructing it. The low
    line may say "a missing employer name is NOT a low-severity anomaly"; what it
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
    """The text under the POSTING ANALYSIS field rule, sub-bullets included.

    Matches either markup: the `- POSTING ANALYSIS` field rule that `prompts.py`
    writes, or the `5. POSTING ANALYSIS` numbered section that `SYSTEM_PROMPT.md`
    writes. The two prompt copies use different structures, and a finder that
    only understood one of them reported "the rule is missing" when the rule was
    present in the other file - which is how a real guardrail reads as absent.

    Where the block *ends* depends on which form matched, because the same `- `
    prefix means "end of section" in one and "first bullet of the section" in
    the other. Getting that wrong returns an empty block, which the caller then
    reports as a missing rule - a false negative pointing the wrong way.

    What matters is locating the block, not enforcing a markup convention. The
    assertions *inside* it are unchanged and still require the banned words and
    an allowed phrasing.
    """
    lines = body.splitlines()
    start = None
    numbered = False
    for i, ln in enumerate(lines):
        stripped = ln.strip()
        if stripped.startswith("- POSTING ANALYSIS"):
            start = i
            break
        if re.match(r"^\d+\.\s*POSTING\s+ANALYSIS", stripped, re.IGNORECASE):
            start = i
            numbered = True
            break
    if start is None:
        return ""

    block = []
    for ln in lines[start + 1:]:
        stripped = ln.strip()
        if not stripped:
            block.append(ln)
            continue
        if numbered:
            # A new numbered section ends the block; its own `- ` bullets do not.
            if re.match(r"^\d+\.\s+[A-Z]", stripped):
                break
        else:
            # A new top-level field rule ends the block; an indented one does not.
            if not ln.startswith("  ") and stripped.startswith("- "):
                break
        block.append(ln)
    return "\n".join(block)


def test_posting_analysis_cannot_say_legitimate_or_scam():
    """A verdict naming a post a scam, or a company legitimate, is the libel risk.

    The opening line of the prompt lists these words, but a long prompt drifts:
    the rule has to be repeated in the field that produces the verdict, next to
    the instruction to base it on the reported anomalies.
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


# ---------------------------------------------------------------------------
# The drift that let the eleven failures above sit open for weeks.
# ---------------------------------------------------------------------------

# Each guardrail, and the phrase that states it. Checked against both copies.
#
# `prompts.py` builds FALLBACK_SYSTEM_PROMPT, used when SYSTEM_PROMPT.md is
# missing or unreadable. For a year the two carried different rules: commit
# a84da6f rewrote the file and dropped the guardrail block, while the Python
# copy kept it. Nothing compared them, so the prompt the backend actually loads
# ran without the absence rule, the quotable-evidence rule, the
# pattern-needs-its-element rule, the never-invent rule and task-for-earning -
# while every test reading the fallback still passed.
#
# The eleven tests above did catch it, which is why this was not invisible. It
# was red, and red for long enough that it read as a known condition rather
# than a live safety regression. That is the part worth fixing.
GUARDRAILS = (
    ("absence is never an anomaly", "never flag the absence"),
    ("an anomaly must be quotable", "point to"),
    ("salary absence", "states no salary"),
    ("never invent", "never invent"),
    ("pattern needs its element", "unless the posting actually contains"),
    ("task-for-earning is named", "task-for-earning"),
    ("task element is concrete", "discrete task"),
    ("work then payment is ordinary", "work followed by payment"),
    ("label is not a verdict", "must not name a conclusion"),
    ("posting analysis bans verdict words", "what the posting asks for"),
    # Added 2026-10-12 after a live probe. The model flagged a Gmail address and
    # an absent salary despite both being forbidden, because this list was in
    # prompts.py and not in SYSTEM_PROMPT.md. The file the backend loads is the
    # one that was missing it.
    ("ordinary things are never findings", "do not flag any of these on their own"),
    ("messenger applications are ordinary", "messenger-based application"),
    ("the ladder is not stretched to fit", "do not stretch the severity ladder"),
    ("mid means paid tasks, not a vague feeling", "paid tasks, orders, or referrals"),
    ("low is rarely correct", "rarely correct"),
    ("actionability bar", "do something differently after reading"),
)


def test_both_prompt_copies_carry_every_guardrail():
    for label, phrase in GUARDRAILS:
        assert phrase in low, f"SYSTEM_PROMPT.md lost the {label} guardrail"
        assert phrase in rules.lower(), f"prompts.py lost the {label} guardrail"


def test_a_guardrail_cannot_be_dropped_from_one_copy_alone():
    """The specific shape of the failure, stated as a guard on itself.

    Every check above would pass if both copies lost a rule at the same time.
    That is not hypothetical: the two files are edited by different means - one
    is prose in a .md, the other a string in a module - so they drift by
    accident far more easily than by decision.
    """
    for label, phrase in GUARDRAILS:
        in_file = phrase in low
        in_fallback = phrase in rules.lower()
        assert in_file == in_fallback, (
            f"the {label} guardrail is in SYSTEM_PROMPT.md={in_file} but "
            f"prompts.py={in_fallback}; one copy has drifted"
        )