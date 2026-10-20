"""The final level, in code.

The verification model used to emit `risk_level` and `risk_score` alongside the
Channel Match status. That put the observation and the verdict in the same
output, so a model that read "the posting's email is a Gmail address" as a
contradiction could produce "Do not proceed" from one weak finding. The model now
reports channel facts, `channel_match` assigns that category's severity, and this
module combines the posting's findings with the refutation score into the level
the panel shows.

The arithmetic is not reimplemented here. `risk_calculator` holds the weights and
the additive rule, and the retirement that took it off the production path is
reversed deliberately: the model owning the level is the defect this module
fixes. The derivation and its limits are unchanged and still documented there.

Two rules are specific to this module:

* A strong Channel Match contradiction (a government office using a non-.gov.ph
  domain, or a lookalike of the official domain) gets a floor of `high`. One
  refuted Channel Match is worth 25 points, which is `low` on its own; that is
  right for "we could not confirm the channel", and wrong for "the posting names
  a government office and sends applicants to an address that is not the
  government's." The floor does not make it critical - the combined score still
  has to reach 76 - so a strong channel finding alone cannot claim the most
  serious headline.
* A free email plus an independent finding is red on the Channel Match card, but
  it is not a floor. The posting's own finding already carries its weight, and
  the two together are what the reader sees.
"""

from __future__ import annotations

from app.models.schemas import VerificationItem

from .risk_calculator import (
    _combine_scores,
    _level_for,
    _posting_risk_from_flags,
    _refutation_score_from_verify,
)

# The bottom of the `high` band. `_level_for` gives `moderate` at 50 and `high`
# at 51, so a strong channel contradiction that would otherwise score 50 is the
# one case where the floor has to move the number, not only the label.
STRONG_CHANNEL_SCORE_FLOOR = 51

_STRONG_CHANNEL_RULES = frozenset({"government", "lookalike"})


def code_verdict(
    anomalies: list,
    items: list[VerificationItem],
    assessments: list = (),
) -> tuple[int, str, dict]:
    """Return (score, level, breakdown) from the posting and the refutation sum.

    This is the only place the wire's `riskLevel` and `riskScore` are produced.
    Nothing from the model's own `risk_level` / `risk_score` is an input; the
    verification flow reads those for logs only.

    A `stale` anomaly assessment removes its finding from the posting score. That
    is the one way the model's evidence work still moves the level, and it is
    attached to the specific finding the source accounts for. `yellow` and `red`
    assessments change nothing here: an absent or general source is not evidence
    in the reader's favour, and a contradicted finding already carries its weight.
    """
    scored_anomalies, stale_excluded = _without_stale(anomalies, assessments)
    posting_score, _posting_level, breakdown = _posting_risk_from_flags(scored_anomalies)
    refutation_score = _refutation_score_from_verify(items)
    total, level = _combine_scores(posting_score, refutation_score)

    channel_rule = _strong_channel_rule(items)
    floor_applied = False
    if channel_rule:
        if total is None or total < STRONG_CHANNEL_SCORE_FLOOR:
            total = STRONG_CHANNEL_SCORE_FLOOR
            level = _level_for(total)
            floor_applied = True

    breakdown = {
        **breakdown,
        "verification_score": refutation_score,
        "final_score": total,
        "sources": ["posting", "verification"],
        "risk_level": level,
        "level_source": "code",
        "channel_escalation": channel_rule,
        "channel_floor": floor_applied,
        "stale_excluded": stale_excluded,
    }
    return total, level or "low", breakdown


def _without_stale(anomalies: list, assessments: list) -> tuple[list, int]:
    """Drop the findings a retrieved employer-specific source accounts for.

    The parser only lets a `stale` assessment through when its `source_url` was
    retrieved, and demotes an unbacked one to `yellow`. So this filter is reading
    a fact the retrieval layer already checked, not a model conclusion on its own.
    """
    stale_indices = {
        getattr(assessment, "index", None)
        for assessment in assessments or []
        if getattr(assessment, "status", "") == "stale"
    }
    if not stale_indices:
        return list(anomalies or []), 0
    kept = [
        anomaly
        for index, anomaly in enumerate(anomalies or [], 1)
        if index not in stale_indices
    ]
    return kept, len(anomalies or []) - len(kept)


def _strong_channel_rule(items: list[VerificationItem]) -> str:
    for item in items:
        if (
            item.label == "Channel Match"
            and item.status == "red"
            and item.escalation in _STRONG_CHANNEL_RULES
        ):
            return item.escalation
    return ""
