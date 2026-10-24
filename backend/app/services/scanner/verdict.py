"""The verdict, as a decision procedure rather than a sum.

The score this module used to produce was a sum of weights over categories, and
nothing about "37" describes a posting. A reader asking where the number came from
had no answer that a Saaty matrix could supply: AHP needs a fixed, commensurable
variable set, and a job posting is not one. The numbers were also not derived from
job posts — they were derived from a comparison of three labels, and the label was
the model's opinion of the finding.

What replaces it has two axes, and both are code-owned:

- **What the posting asks for** — `ordinary`, `unclassified`, or `prohibited`,
  decided by `request_class.classify_request` from facts on the face of the
  posting.
- **Whether the record establishes who is asking** — `confirmed`, `supported`,
  `unknown` or `contradicted`, decided by `establishment`.

The grid is four rules deep:

| request class      | confirmed | supported | unknown | contradicted |
|--------------------|-----------|-----------|---------|--------------|
| ordinary           | clear     | clear     | clear   | **stop**     |
| cannot be classified | note    | note      | note    | **stop**     |
| prohibited         | note      | caution   | caution | **stop**     |

`contradicted` is the only path to `stop`. That is the strongest output this
system can produce, and the only one that needs evidence the posting cannot
supply about itself. `unknown` never rises above a note on its own, because
absence is not a finding. A prohibited request at a confirmed employer softens to
a note: the reader can go and see the request on the employer's own site.

The breakdown is the record of how the verdict was reached, and it carries no
number. `docs/decisions/scoring-model.md` records why the scale was abandoned.
"""

from __future__ import annotations

from app.services.scanner.establishment import Establishment, establishment_from_record

# Ordered weakest to strongest. The panel reads the first four; nothing else is
# a verdict.
VERDICTS = ("clear", "note", "caution", "stop")

# The request classes, in the order `request_class` ranks them. An unrecognised
# class is `unclassified`, never `ordinary`: a class the code cannot read is a
# missing input, and clearing a posting on a missing input is the failure worth
# avoiding.
_REQUEST_CLASSES = ("ordinary", "unclassified", "prohibited")

_REQUEST_RULES = {
    "ordinary": "ordinary_request",
    "unclassified": "unclassified_request",
}


def _normalise_request_class(request_class: str) -> str:
    text = str(request_class or "").strip().lower()
    return text if text in _REQUEST_CLASSES else "unclassified"


def _decide(request_class: str, state: str) -> tuple[str, str]:
    """Return `(verdict, rule)` for one cell of the grid.

    `rule` is the name of the rule that produced the verdict, so a reader — or a
    later bug report — can tell "the record contradicted the employer" from "the
    request was prohibited and the record established nothing".
    """
    if state == "contradicted":
        return "stop", "establishment_contradicted"

    if request_class == "prohibited":
        if state == "confirmed":
            return "note", "prohibited_at_confirmed_employer"
        return "caution", "prohibited_at_unestablished_employer"

    return ("note" if request_class == "unclassified" else "clear"), _REQUEST_RULES[request_class]


def _record(items: list) -> list[dict]:
    """The checks the verdict read, reduced to the fields that decided it.

    Deliberately not the whole `VerificationItem`: the explanation is already
    rendered on the card, and copying it here would let the two drift.
    """
    return [
        {
            "label": getattr(item, "label", ""),
            "status": getattr(item, "status", ""),
            "escalation": getattr(item, "escalation", ""),
            "source_url": getattr(item, "source_url", ""),
        }
        for item in items or []
    ]


def code_verdict(
    anomalies: list,
    items: list,
    assessments: list = (),
    *,
    request_class: str = "ordinary",
    establishment: Establishment | None = None,
) -> tuple[str, dict]:
    """Decide the verdict from the request class and the establishment.

    `establishment` is passed by a caller that has already decided it. Left out,
    it is read from the channel facts in `items` — the provisional mapping in
    `establishment.py`, which Part 4 replaces.

    `anomalies` and `assessments` are not inputs to the decision. The class
    already encodes what the findings asked for, and the flow drops stale findings
    before computing it. They are counted here because the breakdown is a record
    of what the decision was made from, and a reader is entitled to know how many
    findings stood.
    """
    normalised = _normalise_request_class(request_class)
    state = establishment or establishment_from_record(items)
    verdict, rule = _decide(normalised, state.state)

    stale_excluded = sum(
        1
        for assessment in assessments or []
        if getattr(assessment, "status", "") == "stale"
    )

    breakdown = {
        "verdict": verdict,
        "exposure": normalised,
        "establishment": {"state": state.state, "reason": state.reason},
        "rule": rule,
        "record": _record(items),
        "findings": len(anomalies or []),
        "stale_excluded": stale_excluded,
        "level_source": "code",
    }
    return verdict, breakdown
