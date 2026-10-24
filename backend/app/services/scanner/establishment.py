"""Whether the record establishes who is doing the asking.

The verdict has two axes, and this is the second one. The first is what the
posting asks for (`request_class`); this module decides how far the record got in
showing that the entity behind the posting is the entity it names.

Four states, in the vocabulary the reader is shown:

- `confirmed` - the posting's own channel is the employer's own channel. The
  comparison was made and it matched.
- `supported` - an independent record names the employer, but the posting's
  channel was not compared against it. Something exists; it is not the same claim.
- `unknown` - the lookup found nothing, or nothing that bears on identity.
  Absence is never a contradiction.
- `contradicted` - a retrieved source shows the posting's channel is not the
  entity's. This is the only state that can produce `stop`.

**This mapping is provisional.** Part 4 replaces it with a real decision over the
employer record. It is here in Part 2 so the verdict has a second axis to read,
and it is deliberately built from facts the code already owns: a channel
escalation and a category status. No model output enters.

A red `Reputation` is not a contradiction. Reputation is a claim about how an
employer behaves, not about who is asking, and treating one as the other is how a
bad review becomes an impersonation finding.
"""

from __future__ import annotations

from dataclasses import dataclass

# `contradicted` last: it is the strongest state and the only one that stops.
STATES = ("confirmed", "supported", "unknown", "contradicted")

# The channel escalations that contradict the posting's claim about who it is.
# Both involve a domain the employer does not control, and both are code-owned:
# `channel_match` decides them, and the government branch needs no retrieved
# source because the posting supplied the claim and the domain.
CONTRADICTING_ESCALATIONS = frozenset({"government", "lookalike"})


@dataclass(frozen=True)
class Establishment:
    """The second axis of the verdict.

    `reason` is shown to the reader as the record's finding, so it states what was
    compared and what came back, never a conclusion about the poster.
    """

    state: str
    reason: str = ""


def _channel_reason(item) -> str:
    if item.status == "red" and item.escalation == "government":
        return "The posting presents itself as a government office and gives a channel outside that office's domain."
    if item.status == "red" and item.escalation == "lookalike":
        return "The posting's channel differs from the employer's own domain in a lookalike spelling."
    return ""


def establishment_from_record(items: list) -> Establishment:
    """Read the channel facts and the category statuses.

    Channel Match is read first because it is the only category that compares the
    posting's channel with the employer's. A green Company Existence means the
    employer exists, not that the poster is that employer, so it supports rather
    than confirms.
    """
    channel = next(
        (item for item in items or [] if getattr(item, "label", "") == "Channel Match"),
        None,
    )
    if channel is not None:
        if (
            getattr(channel, "status", "") == "red"
            and getattr(channel, "escalation", "") in CONTRADICTING_ESCALATIONS
        ):
            return Establishment("contradicted", _channel_reason(channel))
        if getattr(channel, "escalation", "") == "match":
            return Establishment(
                "confirmed",
                "The posting's own channel matches the employer's.",
            )

    if any(
        getattr(item, "label", "") == "Company Existence"
        and getattr(item, "status", "") == "green"
        for item in items or []
    ):
        return Establishment(
            "supported",
            "An independent result names this employer, but the posting's channel was not compared with it.",
        )

    return Establishment(
        "unknown",
        "Nothing in the record establishes who is behind the posting.",
    )
