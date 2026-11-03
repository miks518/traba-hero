"""Which way the money in a quoted span is going.

A posting states amounts in two directions, and the scan prompt has had to say
so twice: money TO the applicant is pay, money FROM the applicant is a fee. The
rule was prompt-only, and a field test of six postings had the model report a
fee on two of them whose only number was a salary. A prompt sentence is not a
control — `docs/decisions/search-retrieval.md` reached the same conclusion
about the conclusion-word filter.

This module is the control. `quote_pays_the_applicant` answers one question
about one span: does it tell the applicant to pay or buy something? A fee code
whose quote does not is the model inventing a fee, and the finding is dropped
at `scan_result._anomalies` before it can price a verdict.

**Precision beats recall.** A wrongful drop is invisible to the reader — the
finding vanishes, which `docs/decisions/absence-guardrail.md` chose over "shown
but unpriced" — so the vocabulary is a closed, concrete list of payment verbs,
and a quote carrying none of them is read as "this is not a payment request"
rather than "this might be". The one shape that needs care is the verb that is
also a noun: `fee`, `payment`, `bayad` and `deposit` all appear in a sentence
describing what an honest employer does *not* charge. Those are read as pay
language only when they are attached to a request (see `_FEE_NOUN_PATTERNS`).
"""

from __future__ import annotations

import re

# The money-moving words an applicant is directed to use, in both languages the
# product ships. Split into verbs and nouns because only the verbs are safe to
# match bare: `fee`, `payment`, `bayad` and `deposit` are also plain nouns that
# appear in a sentence saying there is none, so they need request shapes.
#
# A generic "requires" or "needs" is absent on purpose: it would fire on
# "requires 2 years experience".
_PAYMENT_VERBS = (
    "pay", "pays", "paid", "paying",
    "remit", "remits", "remittance",
    "shoulder", "shoulders",
    "buy", "buys", "buying", "purchase", "purchases",
    "cash out", "cashout", "top up", "topup", "add money", "bring money",
    "magbayad", "ibayad", "ipadala", "magdeposito", "bilhin", "magpasa",
)

# `bili` is deliberately absent from the list above: it is a Tagalog prefix as
# well as "buy", and a bare match fires on prose that names no purchase.
# `bayad` (fee/payment) is a noun, not a verb — it lives in `_CHARGE_NOUNS` so a
# negated "walang bayad" clears it.
#
# `send` is handled by `_SEND_PATTERNS`, never bare: "send your resume to
# hr@x.ph" is the ordinary application instruction and carries no money. Only a
# send that names a transfer target counts.
_SEND_PATTERNS = (
    r"\bsend\b[^.]{0,40}?\b(gcash|paymaya|maya|bank|account|money|cash)\b",
    r"\bsend\b[^.]{0,40}?\b(php|₱)\s?\d",
    r"\bsend\b\s*(php|₱|p)\s?\d",
    r"\b(send|transfer)\b[^.]{0,30}?\b(to|via)\b[^.]{0,20}?(\+?\d{7,})",
)

# Nouns that name a charge. Matched bare only when the span is not negated: a
# posting that writes "a P500 processing fee" is asking for it, and requiring a
# verb next to it would drop the ordinary Tagalog form "processing fee: P500".
_CHARGE_NOUNS = (
    "fee", "fees", "payment", "deposit", "deposits", "bond", "bayad",
    "downpayment", "down payment",
)

# `fee` and friends attached to a request shape, used to override a negation
# that belongs to a different noun: "we don't require experience, just pay the
# fee" must still read as a payment request.
_FEE_NOUN_PATTERNS = (
    r"\b(fee|fees|payment|deposit|bond)\b\s*(of|is|:|=|worth)?\s*"
    r"(php|p|₱|\d)",
    r"(pay|payment|fee|deposit|bond)\b[^.]{0,40}\b(before|upon|prior to|to (secure|confirm|reserve))",
    r"(request|charge|collect|require|asked|asking|asks)\b[^.]{0,30}\b(fee|payment|deposit|bond)\b",
)

# A clause stating there is no charge. The ordinary clean posting writes "no
# placement fee", and a bare noun match on `fee` would read that as a payment
# request — the exact inversion of what the span says.
#
# **The negation clears a fixed window of text, not a cleverly measured one.**
# Two attempts at "the negated noun and nothing after it" both broke in the
# same way: the lazy gap stopped one word early on `charge` in "do not charge
# any fee", and the boundary lookahead then refused the honest matches ("no
# placement fee is required"). The version below is boring on purpose — from the
# operator to the end of its clause — because a wrong clear is safe here: the
# guard only decides whether a *money* finding survives, and a real fee
# mentioned in the same clause as a negation is vanishingly rare, while a
# posting that says "no fee" is exactly the shape the field test produced.
_NO_CHARGE = (
    r"(?<![a-z])(cannot|can not|does not|do not|did not|doesn't|don't|didn't|"
    r"is not|isn't|are not|never|none|without|walang|no|not)\b"
    r"[^.;!?]{0,60}"
)

_NO_CHARGE_PATTERNS = (_NO_CHARGE,)


# Where `pay` is the noun rather than the verb. A salary side is pay TO the
# applicant, so the span is not a charge even though it contains the word.
_PAY_NOUN_PATTERNS = (
    r"\b(month|week|day|hour|13th)\s+pay\b",
    r"\bpay\s+(rate|scale|grade|period|day|week|month)\b",
)


def _normalise(text: str) -> str:
    """One line, one casing, and punctuation stripped.

    The comma matters: a posting writes `P1,500`, and the amount patterns have
    to see `1500`. Curly quotes and non-breaking spaces arrive from screenshots
    and PDFs, so they are folded here rather than in each pattern.
    """
    text = str(text or "")
    for mark in ("\u2018", "\u2019", "\u201c", "\u201d"):
        text = text.replace(mark, '"')
    text = text.replace("\u00a0", " ").replace("\u2013", "-").replace("\u2014", "-")
    text = re.sub(r"(?<=\d),(?=\d)", "", text)
    return re.sub(r"\s+", " ", text).strip().lower()


def _strip_no_charge(text: str) -> str:
    """Remove each "there is no fee" clause, leaving anything else in the span.

    A posting can say "no placement fee" in one clause and demand a deposit in
    the next. Deleting only the negated clause keeps the deposit visible, while
    deleting the whole span would clear it.
    """
    for pattern in _NO_CHARGE_PATTERNS:
        text = re.sub(pattern, " ", text)
    return text


def quote_pays_the_applicant(quote: str) -> bool:
    """Whether a quoted span contains an instruction to pay or buy.

    A bare amount — `P18,000-P22,000/month`, `up to PHP 25,000` — returns
    `False`. That is the case the guard exists for: a model reading a salary as
    a fee. `FEE_RECIPIENT`/`FEE_TIMING` are not consulted, because they are the
    same model's answer about the same span and an invented fee usually comes
    with an invented recipient.
    """
    text = _normalise(quote)
    if not text:
        return False

    # A span that says there is no charge cannot be a payment request, however
    # many charge nouns it names. The negated clause is removed rather than
    # aborting the whole span: "no placement fee. A P1,000 deposit is required."
    # clears the first half and must keep the second.
    if re.search(_NO_CHARGE, text):
        text = _strip_no_charge(text)
        if not text.strip():
            return False

    # `pay` is a noun as well as a verb: "13th month pay", "pay rate" and "pay
    # period" are pay TO the applicant, and the verb branch below would read
    # them as a charge. Checked before the verb branch, and it ends the
    # question: a span whose only money language is the salary noun side is not
    # a request for money.
    if any(re.search(noun_form, text) for noun_form in _PAY_NOUN_PATTERNS):
        return False

    # A request shape overrides a negation that belongs to a different noun:
    # "we don't require experience, just pay the fee" still asks for the fee.
    for pattern in _FEE_NOUN_PATTERNS:
        if re.search(pattern, text):
            return True

    for pattern in _SEND_PATTERNS:
        if re.search(pattern, text):
            return True

    for verb in _PAYMENT_VERBS:
        # Word-boundary on the verb alone rather than padding the list: `paid`
        # must not match inside `unpaid`.
        if re.search(rf"(?<![a-z]){re.escape(verb)}(?![a-z])", text):
            return True

    for noun in _CHARGE_NOUNS:
        if re.search(rf"(?<![a-z]){re.escape(noun)}(?![a-z])", text):
            return True

    return False


def amount_is_pay(quote: str) -> bool:
    """Whether the span describes pay rather than a charge.

    Kept separate from `quote_pays_the_applicant` because the two answer
    different questions and only one of them may decide a drop: a posting that
    mentions a salary is not thereby cleared of a fee elsewhere in the same
    span. This is used for the log line that explains a drop, never as the
    reason for it.
    """
    text = _normalise(quote)
    return any(word in text for word in _PAY_WORDS)


# Language that marks an amount as pay rather than a charge. Used only by
# `amount_is_pay`, which is diagnostic.
_PAY_WORDS = (
    "salary", "wage", "allowance", "commission", "incentive", "bonus",
    "13th month", "pay rate", "per day", "per hour", "per month", "/day",
    "/month", "/hour", "sweldo", "sahod",
)
