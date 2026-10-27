"""The scan prompt must not allow an anomaly about something's absence.

A scan was returning "does not ask for a processing fee" as an anomaly. That is
a finding about what the posting does NOT contain, which can never be evidence of
anything. The rule has to be in the prompt text the backend actually loads:
`SYSTEM_PROMPT.md` is the hand-shortened file that ships, and it had lost the
guard that `prompts.py`'s longer field rules still carried.
"""

import re
from pathlib import Path

from app.services.scanner.prompts import SCAN_FIELD_RULES, SCAN_FORMAT_BLOCK

PROMPT = Path(__file__).resolve().parents[1] / "SYSTEM_PROMPT.md"
FALLBACK_RULES = Path(__file__).resolve().parents[1] / "app/services/scanner/prompts.py"

text = PROMPT.read_text(encoding="utf-8")
rules = FALLBACK_RULES.read_text(encoding="utf-8")
low = text.lower()


def test_the_scan_prompt_has_no_byte_order_mark():
    """A BOM on a prompt file is invisible and reaches the model.

    `load_system_prompt()` does `read_text(encoding="utf-8").strip()`, and
    `str.strip()` does not remove U+FEFF — zero-width no-break space is not
    whitespace — so the whole scan system prompt was being sent starting with an
    invisible character. Nothing failed. The prompt simply began with a glyph no
    one wrote.

    Checked on the raw bytes rather than the decoded string, because reading with
    `encoding="utf-8"` leaves the BOM in place and a string assertion would then
    be testing `startswith` on text that still has it.

    Worth having as a test because it keeps coming back: any editor configured to
    save UTF-8 *with* BOM will reintroduce it on every save, and the failure is
    invisible from the prompt's behaviour.
    """
    assert not PROMPT.read_bytes().startswith(b"\xef\xbb\xbf")


def test_contact_method_is_a_typed_line_and_claimed_type_exists():
    """`CONTACT_METHOD` is repeatable and typed, and `CLAIMED_TYPE` is captured.

    **Why this shape.** A flyer offered the employer's real address and a
    free-mail address side by side. The slot was singular, so one of them was
    written and the other lost - and the lost one could not arrive by another
    route, because a free email domain is forbidden from being an anomaly. The
    channel that mattered had nowhere to live, so the one check that can detect
    an impersonation never saw it.

    One typed line per channel beats a singular slot holding a joined string:
    the type is free signal, nothing has to be split on a separator, and a
    repeat cannot silently overwrite. It also needed a parser change — a plain
    `attributes[key] = value` keeps only the last line, which is the bug this
    replaces. See `TestRepeatableAttributeKeys` in `test_anomaly_parsing.py`.

    `CLAIMED_TYPE` is the other half of the same observation. "It says CHED" and
    "it presents itself as a government office" are two different facts about
    the same poster, and only the second one says what to compare the fee
    against.

    All three copies are asserted, because they are separate strings and they
    have drifted before. `SYSTEM_PROMPT.md` is what ships; the two constants are
    what a deployment missing the file falls back to.
    """
    # Behaviour, in the file and the field rules.
    for source in (text, SCAN_FIELD_RULES):
        lowered = source.lower()
        assert "claimed_type" in lowered
        assert "write a line for every channel" in lowered, lowered[:80]
        assert "do not join them into one line" in lowered, lowered[:80]
        # The old phrasing asserted the opposite, so its absence is half the
        # test: a prompt carrying both "the channel it directs applicants to"
        # and "every channel" says two things, and the model resolves the
        # contradiction the way it happens to on the day.
        assert "contact_method: <channel it directs applicants to" not in lowered

    # The typed line itself, in the two format blocks.
    for source in (text, SCAN_FORMAT_BLOCK):
        lowered = source.lower()
        assert "contact_method: <email | website | phone | messaging | form | address>" in lowered
        assert "one line per channel" in lowered
        assert "claimed_type: <government" in lowered
        assert "job_title: <the position as the posting titles it" in lowered


def test_the_singular_wording_is_gone_from_all_three():
    """The old phrasing asserted the opposite, so its absence is the real test.

    A prompt carrying both "the channel it directs applicants to" and "every
    channel" is a prompt that says two things, and a model resolves the
    contradiction the way it happens to on the day.
    """
    for source in (text, SCAN_FORMAT_BLOCK, SCAN_FIELD_RULES):
        lowered = source.lower()
        assert "contact_method: <channel it directs applicants to" not in lowered


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
    the prompt that used different wording, so it now checks the whole body of
    both copies.

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


def test_the_prompt_asks_for_no_severity():
    """Severity is gone from the scan's output, and its absence is pinned.

    The ANOMALY line used to end in `| <severity>` and carry a high/mid/low
    ladder. Nothing downstream decided anything by it: the verify assessment is
    the request-class × establishment grid (`assessment.py`), the panel's card
    states come from the evidence, and the over-cap selection now ranks by the
    taxonomy the finding carries. A model asked to price a judgement nothing
    reads as a price is the exact "model prices a category" shape the redesign
    removed — see `docs/decisions/scan-severity-removal.md`.

    Asserted on both copies, because either one alone reintroduces it, and on
    the whole word rather than a phrase: the ladder's words could come back in
    a different dressing ("priority", "weight") and only an absence check on
    the concept's name catches the drift at the source.
    """
    for body, label in ((text, "SYSTEM_PROMPT.md"), (rules, "prompts.py")):
        assert "severity" not in body.lower(), (
            f"{label} still asks the model for severity; the scan output has no "
            "severity slot and no downstream consumer"
        )


def test_the_anomaly_line_has_two_slots():
    """`ANOMALY: <label> | <reasoning>` in both format blocks.

    The parser splits on the pipe and takes two parts. A third slot would be
    parsed as part of the reasoning at best, silently, so the shape is pinned
    rather than assumed.
    """
    for body, expected in (
        (text, "anomaly: <label> | <reasoning>"),
        (SCAN_FORMAT_BLOCK, "anomaly: label | reasoning"),
    ):
        assert expected in body.lower(), (
            f"{expected!r} missing: the ANOMALY line must be label | reasoning, nothing more"
        )
        assert "label | reasoning |" not in body.lower(), (
            "a prompt copy still carries a third slot on the ANOMALY line"
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
    """A assessment naming a post a scam, or a company legitimate, is the libel risk.

    The opening line of the prompt lists these words, but a long prompt drifts:
    the rule has to be repeated in the field that produces the assessment, next to
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
    ("label is not a assessment", "must not name a conclusion"),
    ("posting analysis bans assessment words", "what the posting asks for"),
    # Added 2026-10-12 after a live probe. The model flagged a Gmail address and
    # an absent salary despite both being forbidden, because this list was in
    # prompts.py and not in SYSTEM_PROMPT.md. The file the backend loads is the
    # one that was missing it.
    ("ordinary things are never findings", "no combination of these that makes one of them a finding"),
    ("messenger applications are ordinary", "messenger-based application"),
    ("actionability bar", "do something differently after reading"),
    # Added 2026-10-14. The model kept flagging a Gmail address after
    # "on their own" was added as a prohibition, because "on their own" is a
    # permission as much as a ban: it reads as "a free email domain is flaggable
    # when something else is also wrong." Only the absolute form is pinned here,
    # so the carve-out cannot be reintroduced as the guardrail.
    ("a generic or personal email is never an anomaly", "a generic or personal email is not an anomaly"),
    # Added 2026-10-28. A DM asking for a name, contact number and email was
    # reported as "Asks for personal details via informal direct message ...
    # bypasses secure, official application channels" — the model re-framed the
    # banned informal-channel flag as a data-collection finding, and no rule
    # covered that framing. The closure states the ordinary case positively.
    ("a dm asking for contact details is the application", "the contact details are the application"),
    ("the channel formality is not the concern", "never by the formality of the channel"),
    ("the ordinary case is in the anomaly definition", "differs from nothing: it is the ordinary case"),
    # Added 2026-10-16. A live scan spent both model-authored queries chasing
    # business registration, which `build_queries` already covers with
    # "<company> company or employer" — two of three credits buying a second copy
    # of pages the first search had already returned, and nothing left for the
    # two categories no query was aimed at. The model was not misbehaving: it had
    # no way of knowing the employer lookup had already run.
    ("the employer lookup is named", 'with the words "company or employer"'),
    ("a query must not repeat the employer lookup", "never write a query asking whether the company exists"),
    ("the query budget is four", "at most four"),
    ("queries target what a general lookup cannot settle", "what a general lookup cannot settle"),
    ("location is an element worth querying", "the location, branch or address the posting names"),
    ("similar postings are an element worth querying", "the same work posted elsewhere"),
    ("a quoted number is an element worth querying", "a number the posting quotes"),
    ("similar offers is reachable", "the only thing similar offers can be judged from"),
    ("two queries for one thing is one query", "write only one"),
    # Added 2026-10-18. CONTACT_METHOD became repeatable and typed, and
    # CLAIMED_TYPE was added, because a posting that presents itself as a
    # government office is a different claim from one that names a company.
    ("every channel gets a line", "write a line for every channel"),
    ("a channel line carries its type", "email | website | phone | messaging | form | address"),
    ("the claimed type is captured", "claimed_type"),
    # Added 2026-10-18, for the adaptive search planner. Row 2 asks whether the
    # posting's role is listed on the employer's own site, and "<role> <employer>"
    # is the only form of that question. With no role, the row falls back to
    # "<employer> hiring", which is the generic lookup Round 1 already ran.
    ("the role is captured", "job_title"),
    ("the role is captured for the employer's own site", "on the employer's own site"),
)


def test_both_prompt_copies_carry_every_guardrail():
    for label, phrase in GUARDRAILS:
        assert phrase in low, f"SYSTEM_PROMPT.md lost the {label} guardrail"
        assert phrase in rules.lower(), f"prompts.py lost the {label} guardrail"


def test_the_prompt_does_not_still_forbid_a_similar_postings_query():
    """The rule that blocked Similar Offers is gone, and its absence is asserted
    rather than assumed.

    "Write a query only for something the posting actually states" forbade the
    one query that category can be judged from. Similar Offers asks whether a
    result describes *other postings of this same offer*, which is not a claim
    the posting made about itself, so the old wording ruled it out. It was
    replaced rather than amended, which means a partial edit could leave both
    wordings in place and the model would have to choose between them.
    """
    for body, label in ((low, "SYSTEM_PROMPT.md"), (rules.lower(), "prompts.py")):
        assert "write a query only for something the posting actually states" not in body, (
            f"{label} still forbids a query for other postings of the same work"
        )
        assert "or for other postings of the same work" in body, label


def test_the_named_lookup_matches_the_query_the_backend_actually_builds():
    """The prompt names the static lookup so the model can avoid repeating it.

    That only helps while the name is true. `build_queries` is free to change,
    and a prompt still saying "company or employer" after it stopped building
    that query would describe a search that does not happen - so the two are
    compared rather than trusted.
    """
    from app.services.search import build_queries

    built = build_queries("Acme")
    assert len(built) == 1, f"expected one employer query, got {built}"
    assert "company or employer" in built[0].lower()
    assert 'with the words "company or employer"' in low
    assert 'with the words "company or employer"' in rules.lower()


def test_the_ordinary_things_rule_carries_no_carve_out():
    """`on their own` is a permission as much as a ban.

    A scan kept reporting a Gmail address as an anomaly. The prompt had been
    fixed once, on 2026-10-12, by adding a bullet listing ordinary things not to
    flag — but that bullet said "do not flag any of these **on their own**", and
    the carve-out is the only statement in the prompt that permits flagging one
    of them. A model reading a posting with a free address *plus* something else
    unsatisfying could resolve that contradiction in favour of reporting it, and
    two later absolute rules forbidding exactly this did not stop it.

    A `GUARDRAILS` entry cannot catch this: every entry asserts a phrase is
    present, and the defect is a phrase being *absent*. So the absence is pinned
    here, in both copies, because either one alone reintroduces the permission.
    """
    for name, source in (("SYSTEM_PROMPT.md", low), ("prompts.py", rules.lower())):
        assert "on their own" not in source, (
            f"{name} reintroduced an 'on their own' carve-out, which permits "
            "flagging a free email domain when the posting has another oddity"
        )


def test_the_data_harvest_framing_stays_out_of_the_prompt():
    """The framings the model invented must not enter the prompt, even to
    forbid them.

    A DM asking for a name, contact number and email was reported as "Asks
    for personal details via informal direct message ... bypasses secure,
    official application channels". The model re-framed the banned
    informal-channel flag as a data-collection finding, which no rule
    covered. The fix states the ordinary case positively ("the contact
    details are the application") and deliberately does not repeat the
    failure's vocabulary: a prompt that names the re-framing in order to
    forbid it hands the model the phrase, and the severity-list lesson is
    that the model takes the half it needs. So the absence is pinned instead
    - in both copies, because either one alone reintroduces the framing as
    advice.
    """
    for name, source in (("SYSTEM_PROMPT.md", low), ("prompts.py", rules.lower())):
        for phrase in ("personal details", "bypass", "harvest"):
            assert phrase not in source, (
                f"{name} carries {phrase!r}; the data-harvest framing of an "
                "informal application must stay out of the prompt entirely, "
                "not merely be forbidden"
            )


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