"""The anomaly taxonomy: a `code` and a verbatim `quote` per finding.

Two fields, added so the new report panel can render a finding as an
authored phrase plus the posting's own words, and so the gold set can be
labeled with a closed vocabulary instead of free prose.

Three properties are load-bearing and each has a test below:

1. **The code is a closed set, and an unknown one becomes `OTHER` rather than
   being dropped.** The set labels; it does not gate. A finding the taxonomy
   does not cover must still reach the reader, which is why the existing
   `flag` label is what carries `OTHER`'s free text — there is no new field
   for it.
2. **`CODE:` and `QUOTE:` are ordinary English words.** A job summary
   containing "Enter CODE: 4471" must not be truncated by the parser, which is
   the documented failure mode for the ATTRIBUTES keys. They are gated on
   being inside the anomaly block for that reason.
3. **Both fields are optional on read**, so a scan stored before this change
   still renders.
"""

from app.models.schemas import Anomaly
from app.services.anomaly_codes import ANOMALY_CODES, normalise_code
from app.services.lm_client import _parse_custom
from app.services.scanner.prompts import load_system_prompt
from app.services.scanner.scan_result import _anomalies


def _parse(*lines: str):
    return _parse_custom("VALID: true\n" + "\n".join(lines) + "\nEMPLOYER NAME: Acme\n")


def _wire(*lines: str):
    """Parse a response and put the anomalies on the schema.

    Normalisation and quote screening live in `_anomalies` rather than in the
    parser, for two reasons: `_anomalies` is the last gate before the wire, so
    a caller that builds the dict itself is covered too; and the parser keeping
    the raw value means a model's typo stays greppable in the logs instead of
    being silently rewritten. These tests therefore assert at the schema layer,
    which is where the guarantee the panel relies on actually holds.
    """
    return _anomalies(_parse(*lines)["anomalies"])


# --- the code ------------------------------------------------------------


def test_a_code_line_attaches_to_the_anomaly_above_it():
    result = _parse(
        "ANOMALY: Asks applicants to pay a processing fee | The post asks for a fee | high",
        "CODE: FEE_MANDATORY",
        "END ANOMALIES",
    )

    assert result["anomalies"][0]["code"] == "FEE_MANDATORY"


def test_a_code_line_before_the_next_anomaly_does_not_carry_backwards():
    """Two anomalies, two codes. A shared `last_anomaly` that never resets
    would give both findings the second one's code, which is the kind of bug
    that reads as plausible output.
    """
    result = _parse(
        "ANOMALY: Asks applicants to pay a processing fee | The post asks for a fee | high",
        "CODE: FEE_MANDATORY",
        "ANOMALY: Sends applicants to a recruitment portal | Documents go to a third party | mid",
        "CODE: DOCUMENTS_VIA_THIRD_PARTY",
        "END ANOMALIES",
    )

    codes = [a["code"] for a in result["anomalies"]]
    assert codes == ["FEE_MANDATORY", "DOCUMENTS_VIA_THIRD_PARTY"]


def test_an_unknown_code_becomes_other_and_keeps_the_label():
    """A code outside the set is a labelling miss, not a reason to suppress a
    real finding. `OTHER` carries the model's own words in `flag`, which is
    what makes the escape valve usable without a second free-text field.
    """
    anomaly = _wire(
        "ANOMALY: Asks for a refundable seminar fee | Fee returned on attendance | high",
        "CODE: FEE_MANDATROY",
        "END ANOMALIES",
    )[0]

    assert anomaly.code == "OTHER"
    assert anomaly.flag == "Asks for a refundable seminar fee"
    assert anomaly.severity == "high"


def test_the_parser_keeps_the_raw_code_so_a_typo_stays_greppable():
    """The raw value survives to the log line. Rewriting it at parse time would
    hide the model's most common failure — a misspelled code — inside exactly
    the number it is supposed to make visible.
    """
    result = _parse(
        "ANOMALY: Asks for a fee | A fee | high",
        "CODE: FEE_MANDATROY",
        "END ANOMALIES",
    )

    assert result["anomalies"][0]["code"] == "FEE_MANDATROY"


def test_an_anomaly_with_no_code_line_still_parses():
    """The field is optional on read, so a response written before this change
    — or from a model that ignored the line — is not lost.
    """
    result = _parse(
        "ANOMALY: Asks applicants to pay a processing fee | The post asks for a fee | high",
        "END ANOMALIES",
    )

    assert result["anomalies"][0]["code"] == ""
    assert result["anomalies"][0]["flag"] == "Asks applicants to pay a processing fee"


def test_normalise_code_folds_case_and_whitespace():
    """A model writing `fee_mandatory` or ` FEE_MANDATORY ` meant the same
    code. Rejecting it would send correct output down the `OTHER` path and make
    the drift signal meaningless.
    """
    assert normalise_code("fee_mandatory") == "FEE_MANDATORY"
    assert normalise_code("  Fee_Mandatory  ") == "FEE_MANDATORY"
    # Absent is not OTHER. "" means the response predates codes or the model
    # emitted no CODE line; OTHER means the model said "this is other". Merging
    # them would make stored history indistinguishable from a real escape-valve
    # answer, and the OTHER rate is the drift signal.
    assert normalise_code("") == ""
    assert normalise_code(None) == ""


def test_every_code_is_uppercase_and_unique():
    """The set is a wire value, so the invariants are checked rather than
    assumed. A duplicate would make one code unreachable and silently merge
    two findings into one label.
    """
    assert len(set(ANOMALY_CODES)) == len(ANOMALY_CODES)
    assert all(c == c.upper() for c in ANOMALY_CODES)
    assert all(c.replace("_", "").isalnum() for c in ANOMALY_CODES)


# --- the quote -----------------------------------------------------------


def test_a_quote_line_attaches_to_the_anomaly_above_it():
    result = _parse(
        "ANOMALY: Asks applicants to pay a processing fee | The post asks for a fee | high",
        "CODE: FEE_MANDATORY",
        "QUOTE: pay a 500 peso processing fee",
        "END ANOMALIES",
    )

    assert result["anomalies"][0]["quote"] == "pay a 500 peso processing fee"


def test_a_quote_carrying_a_conclusion_is_dropped():
    """A quotation is presented to the reader as the posting's own words.

    A hedged or accusatory span is therefore not a quotation — it is the model
    speaking, wearing the posting's clothes. Dropping the quote leaves the
    finding intact and the card renders its explanation alone, which is the
    honest degradation.
    """
    anomaly = _wire(
        "ANOMALY: Asks applicants to pay a processing fee | The post asks for a fee | high",
        "CODE: FEE_MANDATORY",
        "QUOTE: this is likely a scam fee request",
        "END ANOMALIES",
    )[0]

    assert anomaly.quote == ""
    assert anomaly.flag == "Asks applicants to pay a processing fee"
    assert anomaly.code == "FEE_MANDATORY"


def test_a_quote_carrying_an_accusatory_word_is_dropped():
    anomaly = _wire(
        "ANOMALY: Asks applicants to pay a processing fee | The post asks for a fee | high",
        "QUOTE: fraudulent processing fee, do not pay",
        "END ANOMALIES",
    )[0]

    assert anomaly.quote == ""


def test_an_ordinary_quote_survives():
    """The overcorrection guard.

    A posting's own text legitimately contains reassurance and absolutes — "100%
    legit", "always welcome", "no experience needed, just apply". Screening
    those out would drop real quotes for nothing, so the check is narrower than
    the prompt's own word ban: it targets the model's judgment, not ordinary
    posting copy.
    """
    for quote in (
        "100% legit company, apply now",
        "Always welcome to apply",
        "no experience needed, just come to the gate",
    ):
        anomaly = _wire(
            "ANOMALY: States the company has been open a decade | Ten years in business | low",
            f"QUOTE: {quote}",
            "END ANOMALIES",
        )[0]
        assert anomaly.quote == quote, quote


def test_an_anomaly_with_no_quote_line_still_parses():
    result = _parse(
        "ANOMALY: Asks applicants to pay a processing fee | The post asks for a fee | high",
        "END ANOMALIES",
    )

    assert result["anomalies"][0]["quote"] == ""


# --- the prose hazard ----------------------------------------------------


def test_a_code_line_inside_a_prose_section_is_prose_not_a_keyword():
    """`CODE:` is an ordinary English word, and a job summary can begin a line
    with one — an instruction to quote a reference at the gate, a voucher code,
    a branch code.

    The keyword must be at the *start* of the line for this to test anything:
    `_SECTION_RE` is anchored, so `Enter CODE: 4471 at the gate` never matched
    it and the hazard was never exercised. An earlier version of this test had
    the keyword mid-line, passed with the gate removed, and was testing nothing.

    This is the documented failure mode for the ATTRIBUTES keys: a matched
    keyword closes the section first, so the line is dropped and the verdict
    goes with it — and `JOB SUMMARY` can vanish entirely, since `close_section`
    writes no key for an empty buffer.
    """
    result = _parse(
        "END ANOMALIES",
        "EMPLOYER NAME: Acme",
        "POSTING ANALYSIS:",
        "Check this before applying.",
        "CODE: 4471 must be quoted at the gate.",
        "END POSTING ANALYSIS",
        "JOB SUMMARY:",
        "A warehouse role, night shift.",
        "CODE: 9910 must be quoted at the gate.",
        "END JOB SUMMARY",
    )

    assert "CODE: 4471" in result["posting_analysis"]
    assert "CODE: 9910" in result["job_summary"]


def test_a_quote_line_inside_a_prose_section_is_prose_not_a_keyword():
    result = _parse(
        "END ANOMALIES",
        "POSTING ANALYSIS:",
        "The post sets out a reference step.",
        "QUOTE: A1 must be quoted when you call.",
        "END POSTING ANALYSIS",
        "JOB SUMMARY:",
        "A warehouse role, night shift.",
        "QUOTE: A2 must be quoted when you call.",
        "END JOB SUMMARY",
    )

    assert "QUOTE: A1" in result["posting_analysis"]
    assert "QUOTE: A2" in result["job_summary"]


def test_a_prose_code_line_does_not_become_the_previous_anomalys_code():
    """The other half of the hazard.

    Without the gate a `CODE:` line in a job summary does not merely get
    dropped — it reaches the handler and overwrites the code of whatever
    anomaly was parsed before it. The finding keeps its severity and its label
    and is silently relabelled, which is worse than losing a line because the
    result still looks correct.
    """
    result = _parse(
        "ANOMALY: Asks applicants to pay a processing fee | The post asks for a fee | high",
        "CODE: FEE_MANDATORY",
        "END ANOMALIES",
        "EMPLOYER NAME: Acme",
        "JOB SUMMARY:",
        "A warehouse role, night shift.",
        "CODE: 9910 must be quoted at the gate.",
        "END JOB SUMMARY",
    )

    anomaly = _anomalies(result["anomalies"])[0]
    assert anomaly.code == "FEE_MANDATORY"
    assert anomaly.severity == "high"


# --- the schema ----------------------------------------------------------


def test_the_anomaly_schema_carries_code_and_quote():
    anomaly = _anomalies([
        {
            "flag": "Asks applicants to pay a processing fee",
            "reasoning": "The post asks for a fee before starting work",
            "severity": "high",
            "code": "FEE_MANDATORY",
            "quote": "pay a 500 peso processing fee",
        }
    ])[0]

    assert isinstance(anomaly, Anomaly)
    assert anomaly.code == "FEE_MANDATORY"
    assert anomaly.quote == "pay a 500 peso processing fee"


def test_an_anomaly_stored_before_this_change_still_constructs():
    """Scan history predates both fields. A stored entry without them must keep
    rendering, which is the whole reason both default to empty rather than
    being required.
    """
    anomaly = Anomaly(flag="Asks for a fee", reasoning="A fee", severity="high")

    assert anomaly.code == ""
    assert anomaly.quote == ""


def test_the_code_is_normalised_on_the_way_onto_the_schema():
    """`_anomalies` is the last gate before the wire, so it is where an
    unrecognised code becomes `OTHER`. Normalising only in the parser would
    leave the value unchecked for any caller that builds a dict itself.
    """
    anomaly = _anomalies([
        {"flag": "Asks for a fee", "reasoning": "A fee", "severity": "high", "code": "NOT_A_CODE"},
    ])[0]

    assert anomaly.code == "OTHER"


# --- the prompt contract -------------------------------------------------


def test_the_prompt_file_names_every_code_in_the_set():
    """The set lives in Python and the prompt restates it, so the two can
    drift. This is the guard, in the direction that matters: a code the parser
    will accept but the prompt never mentions is one the model cannot use.
    """
    prompt = load_system_prompt()

    missing = [c for c in ANOMALY_CODES if c not in prompt]
    assert missing == [], f"codes the parser accepts but the prompt never names: {missing}"


def test_the_prompt_file_names_no_code_outside_the_set():
    """The other direction. A code left in the prompt after removal from the
    tuple would be emitted, silently rewritten to `OTHER`, and read as drift.
    """
    import re

    prompt = load_system_prompt()
    # Only the taxonomy block is scanned: elsewhere the prompt is prose, and
    # SCREAMING_SNAKE words appear in other roles.
    block = prompt.split("ANOMALY CODES:")[-1].split("END ANOMALY CODES")[0]
    named = set(re.findall(r"\b[A-Z][A-Z_]{3,}\b", block))

    stray = named - set(ANOMALY_CODES)
    assert stray == set(), f"codes in the prompt but not in the set: {stray}"


def test_the_prompt_requires_a_verbatim_quote_not_a_paraphrase():
    """The current rule allows "quoted or closely paraphrased". A quote block
    cannot render a paraphrase, so the looser half of the rule would leave the
    model obeying it and the panel rendering reconstructed text as the
    posting's words.
    """
    prompt = load_system_prompt().lower()

    assert "closely paraphrased" not in prompt
    assert "verbatim" in prompt


def test_the_prompt_keeps_the_code_set_a_label_not_a_gate():
    """The escape valve has to be stated, or a model that cannot fit the
    taxonomy will suppress a real finding rather than report `OTHER` — which
    is the enumeration trap the `task-for-earning` fix already had to undo
    once.
    """
    prompt = load_system_prompt().lower()

    assert "other" in prompt
    assert "suppress" in prompt or "instead of staying silent" in prompt


# --- the fallback copy ---------------------------------------------------


def test_the_fallback_prompt_carries_the_code_set():
    """`load_system_prompt()` reads `SYSTEM_PROMPT.md`, so a test against it
    only proves the file is right. `FALLBACK_SYSTEM_PROMPT` is what a
    deployment shipping without the file scans against, and nothing else
    asserts it — adding the taxonomy to the file alone left it out of the
    fallback and the suite stayed green.

    That is the drift `test_a_guardrail_cannot_be_dropped_from_one_copy_alone`
    exists for, generalised to a whole block rather than a phrase.
    """
    from app.services.scanner.prompts import FALLBACK_SYSTEM_PROMPT

    missing = [c for c in ANOMALY_CODES if c not in FALLBACK_SYSTEM_PROMPT]
    assert missing == [], f"codes missing from the fallback prompt: {missing}"


def test_the_fallback_prompt_carries_the_quote_rule():
    """The verbatim rule is the one that keeps reconstructed text out of the
    panel's quotation block, so the fallback cannot ship without it.
    """
    from app.services.scanner.prompts import FALLBACK_SYSTEM_PROMPT

    lowered = FALLBACK_SYSTEM_PROMPT.lower()
    assert "quote:" in lowered
    assert "verbatim" in lowered
    assert "closely paraphrased" not in lowered


def test_the_format_block_names_the_two_new_lines():
    """`SCAN_FORMAT_BLOCK` is the single definition of the output shape — the
    fallback prompt and the user-message skeleton are both built from it. A
    format the skeleton does not mention is a format the model is not told.
    """
    from app.services.scanner.prompts import SCAN_FORMAT_BLOCK

    assert "CODE:" in SCAN_FORMAT_BLOCK
    assert "QUOTE:" in SCAN_FORMAT_BLOCK
