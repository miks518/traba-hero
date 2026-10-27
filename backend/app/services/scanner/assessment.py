"""The assessment, as a decision procedure rather than a sum.

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

The grid is three colours deep:

| request class      | confirmed | supported | unknown | contradicted |
|--------------------|-----------|-----------|---------|--------------|
| ordinary           | green     | green     | green   | **red**      |
| cannot be classified | yellow  | yellow    | yellow  | **red**      |
| prohibited         | yellow    | yellow    | yellow  | **red**      |

`contradicted` is the only path to `red`. That is the strongest output this
system can produce, and the only one that needs evidence the posting cannot
supply about itself. `unknown` never rises above `yellow` on its own, because
absence is not a finding. A prohibited request at a confirmed employer softens
into the same `yellow`: the reader can go and see the request on the employer's
own site. What separates the two yellows is the *rule* in the breakdown, which
the panel renders under the chip — the colour says "uncertain", the rule says
why.

The breakdown is the record of how the assessment was reached, and it carries no
number. `docs/decisions/scoring-model.md` records why the scale was abandoned.
"""

from __future__ import annotations

from app.services.scanner.establishment import Establishment, establishment_from_record

# The assessment tokens are the panel's colours: `green`, `yellow`, `red`.
# They name the strength of the evidence relation, not a verdict about the
# posting and not an instruction to the reader — the chip words on the panel
# are "Nothing found against it", "Caution" and "Contradicted", and the sentence
# under each chip is the rule that produced it. Three colours, five rules: the
# two yellows the old ladder carried (`note`, `caution`) were both uncertainty,
# and a chip for a tier the product's own user never noticed was not carrying
# its weight. What distinguishes them now is the rule in the breakdown, which
# the panel renders under the chip.
ASSESSMENTS = ("green", "yellow", "red")

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
    """Return `(assessment, rule)` for one cell of the grid.

    `rule` is the name of the rule that produced the assessment, so a reader — or a
    later bug report — can tell "the record contradicted the employer" from "the
    request was prohibited and the record established nothing".
    """
    if state == "contradicted":
        return "red", "establishment_contradicted"

    if request_class == "prohibited":
        if state == "confirmed":
            return "yellow", "prohibited_at_confirmed_employer"
        return "yellow", "prohibited_at_unestablished_employer"

    return ("yellow" if request_class == "unclassified" else "green"), _REQUEST_RULES[request_class]


def _record(items: list) -> list[dict]:
    """The checks the assessment read, reduced to the fields that decided it.

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


def code_assessment(
    anomalies: list,
    items: list,
    assessments: list = (),
    *,
    request_class: str = "ordinary",
    establishment: Establishment | None = None,
) -> tuple[str, dict]:
    """Decide the assessment from the request class and the establishment.

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
    assessment, rule = _decide(normalised, state.state)

    stale_excluded = sum(
        1
        for assessment in assessments or []
        if getattr(assessment, "status", "") == "stale"
    )

    breakdown = {
        "assessment": assessment,
        "exposure": normalised,
        "establishment": {"state": state.state, "reason": state.reason},
        "rule": rule,
        "record": _record(items),
        "findings": len(anomalies or []),
        "stale_excluded": stale_excluded,
        "level_source": "code",
    }
    return assessment, breakdown
