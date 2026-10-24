"""The authored statements and options for each verdict.

The panel never shows model prose. Every word is in code and looked up, like the
panel's own copy. The statement is rendered from structured facts off the record
— the amount, the fee's recipient and reason, what kind of documents — so the
panel never puts model prose in front of the reader.

The rule that catches me: a `clear` statement must not say the posting asks for
nothing when it asks for something. A posting that asks for a 500 peso uniform
is clear, and the sentence has to say so, because a false statement on the panel
is the one thing the libel guardrail cannot tolerate.

No statement contains an accusation and no statement contains a hedge — no
"likely", "appears", "suggests", "may", "might", "could". The same word ban
`clean_verdict_reason` applies, because the same reader-facing risk applies.
"""

from __future__ import annotations

from dataclasses import dataclass

from .establishment import Establishment


@dataclass(frozen=True)
class StatementFacts:
    """Structured facts from the record, for rendering a statement.

    Every field is a screened verbatim span from the posting or the record —
    never a model's prose. The statement templates substitute these directly.
    """

    amount: str = ""
    fee_recipient: str = ""
    fee_reason: str = ""
    documents: str = ""
    role: str = ""


_HEDGES = frozenset({"likely", "appears", "suggests", "may", "might", "could"})


def _check_no_hedges(text: str) -> str:
    """Assert no hedges in the final text. Called at test time, not runtime."""
    lowered = text.lower()
    for hedge in _HEDGES:
        if hedge in lowered:
            raise AssertionError(f"statement contains hedge: {hedge}")
    return text


def _fee_phrase(facts: StatementFacts) -> str:
    """Build the fee clause from facts."""
    if not facts.amount and not facts.fee_reason:
        return ""
    parts = []
    if facts.amount:
        parts.append(f"₱{facts.amount}")
    if facts.fee_reason:
        parts.append(f"for {facts.fee_reason}")
    if facts.fee_recipient:
        parts.append(f"to {facts.fee_recipient}")
    return " ".join(parts)


def _documents_phrase(facts: StatementFacts) -> str:
    if not facts.documents:
        return ""
    return f"documents: {facts.documents}"


def _role_phrase(facts: StatementFacts) -> str:
    if not facts.role:
        return ""
    return f"role: {facts.role}"


def _establishment_phrase(establishment: Establishment) -> str:
    state = establishment.state
    reason = establishment.reason
    if state == "confirmed":
        return f"The employer's own channel matches."
    if state == "supported":
        return f"An independent record names this employer, but the posting's channel was not compared."
    if state == "contradicted":
        return f"The posting's channel contradicts the employer: {reason}" if reason else "The posting's channel contradicts the employer."
    return "Nothing in the record establishes who is behind the posting."


def statement(
    verdict: str,
    *,
    request_class: str,
    establishment: Establishment,
    facts: StatementFacts,
) -> str:
    """Render the panel's one-sentence statement for a verdict.

    Two parts: what the posting asks for, and what the record showed.
    """
    fee = _fee_phrase(facts)
    docs = _documents_phrase(facts)
    role = _role_phrase(facts)
    est = _establishment_phrase(establishment)

    # Build the first part: what the posting asks for
    ask_parts = []
    if fee:
        ask_parts.append(f"asks for {fee}")
    if docs:
        ask_parts.append(f"asks for {docs}")
    if role:
        ask_parts.append(role)
    ask = "; ".join(ask_parts) if ask_parts else "asks for nothing the rules prohibit"

    # Build the second part: what the record showed
    record = est

    if verdict == "clear":
        # Clear: ordinary request, no contradiction
        text = f"The posting {ask}. {record}"
    elif verdict == "note":
        # Note: request is prohibited or unclassified but employer is confirmed/supported
        if request_class == "prohibited":
            text = f"The posting {ask}. The employer is confirmed and the fee is stated on their site."
        else:
            text = f"The posting {ask}. {record} The record supports the employer's identity."
    elif verdict == "caution":
        # Caution: prohibited request at unknown employer
        text = f"The posting {ask}. The employer has not been established — settle the fee recipient and reason first."
    elif verdict == "stop":
        # Stop: contradicted employer
        text = f"The posting {ask}. The communication is not from the employer it names. {record} This is a contradicted impersonation."
    else:
        text = f"The posting {ask}. {record}"

    return _check_no_hedges(text)


def options(verdict: str) -> tuple[str, ...]:
    """Return the reader's options for a verdict family.

    Options are choices, not orders. They offer what the reader can do next.
    """
    if verdict == "clear":
        return ("Proceed with the application",)
    if verdict == "note":
        return (
            "Check the employer's official site for the stated fee",
            "Confirm the application process directly with the employer",
        )
    if verdict == "caution":
        return (
            "Ask the poster to confirm who receives the fee and why",
            "Confirm the employer's identity through an official channel first",
        )
    if verdict == "stop":
        return (
            "Do not send money or documents",
            "Report the posting to the platform and the agency it impersonates",
        )
    return ()