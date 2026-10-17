"""The anomaly code set, and the rules for reading one off a model response.

A leaf module on purpose. Both `app/services/lm_client.py` (which validates a
model's response) and `app/services/scanner/prompts.py` (which states the set
to the model) need the same list, and `lm_client` is a leaf that imports only
`openai` and `app.config` — so putting the tuple in either of those two would
mean one of them importing the other. One home, no cycle.

The taxonomy, its grounding, and why it is grouped by what the reader gives up
rather than by scam type is in
`docs/superpowers/specs/2026-10-17-anomaly-code-set.md`.

**This is the scan's vocabulary.** The spec's Family E (`EMPLOYER_UNTRACEABLE`,
`CLAIM_CONTRADICTED`) is deliberately absent: those are verification's, and
verification already reports them through its own six claim categories with a
status and a source. Emitting them here would give one finding two codes.
"""

ANOMALY_CODES = (
    # --- Family M: the reader loses money -------------------------------
    "FEE_MANDATORY",
    "FEE_CONDITIONAL",
    "PURCHASE_REQUIRED",
    "DEPOSIT_REQUIRED",
    "PAYMENT_FORWARDING",
    # --- Family I: the reader loses documents or accounts ---------------
    "CREDENTIALS_BEFORE_INTERVIEW",
    "DOCUMENTS_VIA_THIRD_PARTY",
    "IMPERSONATES_AUTHORITY",
    # --- Family C: labour sold as the product ---------------------------
    "TASK_FOR_EARNING",
    # --- Family O: the escape valve -------------------------------------
    "OTHER",
)

_CODE_SET = frozenset(ANOMALY_CODES)


def normalise_code(raw: object) -> str:
    """Fold a model's answer onto the set.

    Case and surrounding whitespace are forgiven, because rejecting `fee_mandatory`
    would send a correct answer down the `OTHER` path and make the drift signal
    unreadable — a set that only accepts one spelling measures the model's
    formatting, not the taxonomy's coverage.

    An unrecognised value becomes `OTHER`. It is never dropped: the finding is
    real and the `flag` label carries the description, so the escape valve is
    usable without a second free-text field.

    Returns `""` for an absent value. Absent and `OTHER` are different claims —
    the first means the response predates codes or omitted the line, the second
    means the model answered the escape valve deliberately.
    """
    if raw is None:
        return ""
    text = str(raw).strip()
    if not text:
        return ""
    upper = text.upper()
    return upper if upper in _CODE_SET else "OTHER"


# Words that cannot honestly appear in a *quotation* of a job posting about
# itself, because they are the model's judgment rather than the poster's words.
#
# Deliberately narrower than the prompt's own OUTPUT RULES, which also bans
# absolutes (always, never, definitely, 100%). Those are too common in ordinary
# posting text — "100% legit", "always welcome" — so banning them here would
# drop legitimate quotes for no gain. The absolutes ban still applies to the
# `reasoning` field, where it belongs.
_QUOTE_BANNED = (
    "scam",
    "scammer",
    "fraud",
    "fraudulent",
    "fake",
    "falsify",
    "falsified",
    "suspicious",
    "illegitimate",
    "likely",
    "probably",
    "seemingly",
    "appears to",
    "suggests that",
    "might be a",
    "could indicate",
)


def quote_is_clean(raw: object) -> bool:
    """Whether a quote may be shown to the reader as the posting's own words.

    A quotation is presented as something the posting said. A hedged or
    accusatory span is therefore not a quotation — it is the model speaking
    wearing the posting's clothes, which is the exact failure the citation
    binding exists to prevent on the verification side.

    A rejected quote degrades the card to its explanation, which is honest.
    The reverse — showing reconstructed text as the poster's words — is not
    available as a failure mode.
    """
    if raw is None:
        return False
    text = str(raw).strip()
    if not text:
        return False
    lowered = text.lower()
    return not any(word in lowered for word in _QUOTE_BANNED)


def clean_quote(raw: object) -> str:
    """The quote if it may be shown, else empty."""
    text = str(raw or "").strip()
    return text if quote_is_clean(text) else ""
