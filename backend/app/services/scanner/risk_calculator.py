"""Live again as of 2026-10-21, as the arithmetic behind `verdict.py`.

This file was retired on 2026-10-17 because it priced the *category* of a
finding, and a category cannot carry context: a processing fee was worth 40
whoever asked for it. A post demanding money from a name that appears nowhere
and a post demanding the same money from a government office with a matching
address and its own portal were identical inputs, and the ladder could only give
them one answer. The retirement assumed the verification model would own the
level, because that stage holds what the ladder never could - who is asking, and
whether they exist.

That assumption failed in a specific, observable way. A real employer whose
posting used a Gmail address while its own site was `company.com.ph` produced a
red Channel Match and, because the same model also emitted `risk_level`, "Do not
proceed". The model had the context and still priced a category; one weak
observation carried the whole verdict.

The current split keeps the part the model is good at - reporting what the
posting names and what the employer's own results use - and puts the severity of
that comparison in `channel_match.py`. The final level is this file's arithmetic
over two code-owned inputs: the posting's findings and the refutation score. The
retirement's objection still stands as a limit: the weights price a category and
cannot tell who is asking. `verdict.py` compensates in one visible place, with a
floor for a strong Channel Match contradiction, and documents why the rest of the
objection is why the model's own `risk_level` is not an input.

The Saaty matrix is a statement about *method*, not about these numbers. AHP
assumes a fixed, commensurable variable set, and an unstructured job posting does
not have one: "only woman or lesbian" had no cell in the ladder and was scored at
whatever the model guessed, while an advance-fee demand sat in a cell that was
worth 40 by construction. A method that cannot represent a variable should not
be the thing deciding how dangerous a job is.

What is live: `_posting_risk_from_flags`, `_combine_scores`, `_level_for`, and
`_refutation_score_from_verify` are called by `verdict.py`. `tests/test_code_verdict.py`
guards that wiring, and the three "unassessed is not low" contracts that the
retirement introduced are still asserted there.
"""

from app.models.schemas import Anomaly, VerificationItem

# Weights used to turn the indicators reported in a posting into a score. They
# are deliberately simple and fixed so the number can be explained to the user:
# a high-severity indicator is a concrete instruction or request inside the
# posting, a mid is a checkable gap, a low is something common in Philippine
# postings that is weak on its own.
#
# Derivation: the 40/12/4 proportions are reproducible from a Saaty pairwise
# comparison matrix of 3/9/3 (high:mid, high:low, mid:low), which is perfectly
# consistent at CR = 0.0000 against a 0.10 threshold. Implemented proportions are
# 71.4/21.4/7.1 against AHP's 69.2/23.1/7.7 — within 2.2 percentage points. See
# SCORING-SOURCES.md §1. The remaining free parameter is the scale anchor (one
# high-severity indicator = 40 points), which AHP cannot derive and which the
# sensitivity analysis in §5 of that file covers.
#
# Deliberately NOT fitted to labelled scam data: fitting would rediscover
# subtraction, since a verified-legitimate employer plus a clean posting
# correlates with "legitimate" in labelled data. That would reverse the
# asymmetry `_combine_scores` was rewritten to enforce.
POSTING_SEVERITY_WEIGHTS = {"high": 40, "mid": 12, "low": 4}

# Evidence stage. A claim the retrieval CONTRADICTS costs points; a claim it
# confirms, and a claim it learned nothing about, both cost nothing.
#
# Derived, not chosen. `REFUTATION_WEIGHTS` was previously set by judgement and
# `SCORING-SOURCES.md` section 8 flagged it as the one number in this file with
# no method behind it. It is now the principal eigenvector of a 6x6 Saaty
# pairwise matrix, reported in SCORING-SOURCES.md section 8:
#
#     lambda_max = 6.2777  CI = 0.0555  RI = 1.24  CR = 0.0448  PASS (< 0.10)
#
# Reproduce with `python scripts/derive_refutation_weights.py`, which lists every
# judgment it was built from so a disagreement can be changed one integer at a
# time rather than argued about as a finished number.
#
# **AHP derives proportions, not points.** The anchor - one refuted Channel Match
# worth 25 - is a free parameter AHP cannot derive, defended by the sensitivity
# analysis in section 9, exactly as the severity anchor is in section 5.
#
# The hierarchy is unchanged from the judgement weights that preceded it:
# Channel Match > Similar Offers > Reputation > Location / Branch >
# Company Existence = Official Registration. What changed is the spacing, from a
# 4.2x top-to-bottom spread to 12.5x. That is a real narrowing of what the last
# three can move, and it is the number to argue about first - see section 8.
REFUTATION_WEIGHTS = {
    "Channel Match": 25,
    "Similar Offers": 13,
    "Reputation": 7,
    "Location / Branch": 4,
    "Company Existence": 2,
    "Official Registration": 2,
}

# The evidence stage may add up to half the scale. See `_combine_scores`.
MAX_REFUTATION_SCORE = 50

# Results recorded before a rename carry a label this table no longer names, and
# it must keep carrying its weight. An unweighted label is not a default of 0
# here — it *returns* 0, which becomes None, so a refuted claim would render as a
# stage that never ran. The cost is silent: the category still renders, so nothing
# looks broken.
#
# Mirrors `_LEGACY_LABELS` in verification_parser. Kept as its own literal rather
# than imported: that module pulls in the verification prompt, and this one is a
# pure scoring module that has to stay importable on its own. Two copies is a
# drift risk, so `TestBothLegacyTablesAgree` compares them on every run.
_LEGACY_LABEL_MAP = {
    "sec registration": "Official Registration",
    "scheme corroboration": "Similar Offers",
}

# Derived from `REFUTATION_WEIGHTS` at import, never restated. The lookup folds
# case on both sides, and a hand-written second copy of the table is a weight
# that can be added above and missed below -- which is the failure that produced
# this one. Asserted by `TestTheLabelLookupIsCaseInsensitive`.
_REFUTATION_WEIGHTS_BY_LOWER = {label.lower(): weight for label, weight in REFUTATION_WEIGHTS.items()}


def _weight_for(label: str) -> int:
    """Points for one refuted category. Zero for a label with no weight.

    Both sides of the lookup are case-folded. The structured path cannot produce
    a lowercase label -- the JSON schema's enum is title case and
    `verification_flow` goes through it -- but the labeled-text fallback accepts
    whatever label it reads, so a model answering `VERIFY: channel match`
    reaches here. It used to miss the table, score zero, and leave the stage
    returning `None`: a genuine refutation silently discarded, which is the one
    direction of error worth being paranoid about, because the reader would be
    shown a corroborated-as-clean posting.

    A label that is still not found after folding stays zero rather than picking
    up a default. Case folding widens the match, it does not invent one:
    "channel-match" is a different string and remains silence.
    """
    canonical = _LEGACY_LABEL_MAP.get(label.strip().lower(), label)
    return _REFUTATION_WEIGHTS_BY_LOWER.get(canonical.strip().lower(), 0)


def _level_for(score: int) -> str:
    if score <= 30:
        return "low"
    if score <= 50:
        return "moderate"
    if score <= 75:
        return "high"
    return "critical"


def _posting_risk_from_flags(flags: list) -> tuple[int, str, dict]:
    """Score a posting from the anomalies reported in it. Returns (score, level, breakdown).

    This is the base verdict and it is always available: it depends on nothing
    but the posting itself, so an offer with no employer name, or one that cannot
    be looked up online, still gets a number. Nothing here is inferred — the
    weights only count indicators that were actually reported.
    """
    counts = {"high": 0, "mid": 0, "low": 0}
    for flag in flags or []:
        severity = getattr(flag, "severity", None)
        if not severity and isinstance(flag, dict):
            severity = flag.get("severity")
        severity = str(severity or "mid").strip().lower()
        if severity not in counts:
            severity = "mid"
        counts[severity] += 1

    score = min(
        100,
        sum(counts[sev] * weight for sev, weight in POSTING_SEVERITY_WEIGHTS.items()),
    )
    breakdown = {
        "source": "posting",
        "high_count": counts["high"],
        "mid_count": counts["mid"],
        "low_count": counts["low"],
        "weights": dict(POSTING_SEVERITY_WEIGHTS),
        "posting_score": score,
    }
    return score, _level_for(score), breakdown

def _calculate_risk_score_from_verify(items: list[VerificationItem]) -> tuple[int | None, str | None]:
    """The employer-category penalty, from before the stage was renamed.

    Retained and exported because `test_scanner_package.py` pins the package's
    symbol list and this signature, but it is no longer on any production path:
    the verification flow calls `_refutation_score_from_verify`. Its scale is
    also a different one -- a share of the category weights, normalised to 100 --
    so it is not a drop-in for the stage that replaced it.

    `yellow` means the search returned nothing about a category. It carried half
    weight when the two stages were averaged, because something had to pull the
    average down. It cannot carry weight here: added to the posting it would
    penalise a check that found nothing, which is precisely what this project
    has repeatedly refused to do — absence of evidence produces no score. So
    yellow contributes zero, and a verified-clean or unverified employer leaves
    the posting's own number alone.

    `green` is zero for the same reason, and a stronger one: green means a result
    stated a fact, not that the fact was reassuring. On Reputation a green card
    can be a one-star employee account.

    Returns (None, None) when nothing was confirmed, so an employer nobody could
    look up leaves the number untouched.
    """
    if not items or all(item.status == "yellow" for item in items):
        return None, None

    category_weights = {
        "Company Existence": 40,
        "Official Registration": 25,
        "Reputation": 35,
    }
    # Results recorded before the rename used "SEC Registration". It carried the
    # registration weight then and must carry it now, or a stored verification
    # would silently rescore from 25 to the default weight of 10.
    legacy_weights = {"SEC Registration": 25}
    total_weight = sum(category_weights.values())  # 100
    penalty = 0
    for item in items:
        if item.status != "red":
            continue
        label = item.label.strip()
        weight = category_weights.get(label) or legacy_weights.get(label) or 10
        penalty += weight
    score = min(100, round(penalty / total_weight * 100))
    return score, _level_for(score)


def _refutation_score_from_verify(items: list[VerificationItem]) -> int | None:
    """Points for claims the retrieval contradicted. Returns None if nothing was refuted.

    Only `red` carries weight, and `red` now means a retrieved result contradicts
    a specific claim the posting made - not merely that a result stated
    something negative.

    `green` is zero because a confirmed claim means the claim is supported, not
    that the posting is safe: verification withholds trust, it never grants it.

    `yellow` is zero for the same reason `SearchOutcome.ok` and `.results` are
    independent. A claim nobody could confirm has not been refuted, and a sole
    proprietorship with no web presence is the ordinary case in the Philippines.
    Scoring silence would penalise the smallest employers - the ones this product
    exists for - for having no website.

    A label with no weight is silence too, not a default. The old table gave an
    unknown category a weight of 10, which meant a category this design never
    checked could outscore a confirmed claim at zero.

    Returns None rather than 0 when nothing was refuted, so the caller can tell
    "nothing was learned" from "a measurement of zero risk".
    """
    if not items:
        return None

    penalty = 0
    for item in items:
        if item.status != "red":
            continue
        penalty += _weight_for(item.label)

    if penalty <= 0:
        return None
    return min(MAX_REFUTATION_SCORE, penalty)


def _combine_scores(posting_score: int | None, refutation_score: int | None) -> tuple[int, str] | tuple[None, None]:
    """Add the refutation penalty to the posting score, with a floor.

    Asymmetric: evidence may only **raise**. What the retrieval establishes is
    that a claim is contradicted, not that a posting is safe. A clean employer
    record must not be able to pull a maxed posting down to a number the reader
    would read as tolerable.

    This was a 60/40 blend, and the blend was wrong in a way that inverted the
    meaning of the number. A posting that had already maxed out — three
    high-severity indicators — was pulled to 60 by a clean employer record,
    because averaging lets corroborating evidence outvote the thing the reader
    actually asked about. And a published scam report added 14 points over that
    clean record, so negative evidence moved the number far less than the
    absence of it. "We found nothing" scored 100, tying "three damning
    categories".

    The `max` is what makes a balanced split possible without reintroducing the
    blend. A plain 50/50 mean would report three high-severity anomalies plus an
    unlookable employer as 50 — "moderate" — because half of nothing is nothing.
    The floor keeps the posting's own full range intact and gives evidence a
    guaranteed share of the ceiling above it.

    A missing stage is absent, not zero: a posting that could not be looked up is
    not penalised for the failed lookup.
    """
    if posting_score is None:
        if refutation_score is None:
            return None, None
        return refutation_score, _level_for(refutation_score)
    if refutation_score is None:
        return posting_score, _level_for(posting_score)
    total = min(100, max(posting_score, posting_score + refutation_score))
    return total, _level_for(total)
