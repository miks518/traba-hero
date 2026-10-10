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
# The weights are the one thing in this file not yet derived. `SCORING-SOURCES.md`
# section 8 found the employer category weights nearly flat (40/25/35 is a 1.6x
# spread, barely distinguishable from equal importance on Saaty's scale), and
# these were chosen on the same judgement rather than by the pairwise method in
# `SCORING-SOURCES.md` section 1. They MUST be re-derived before this ships to a
# panel, with the consistency ratio reported. The ordering is defensible now:
# Channel Match is the only check that can detect an impersonation, because a
# real employer passes every existence, registration and branch check.
REFUTATION_WEIGHTS = {
    "Channel Match": 25,
    "Scheme Corroboration": 15,
    "Reputation": 10,
    "Location / Branch": 8,
    "Company Existence": 6,
    "Official Registration": 6,
}

# The evidence stage may add up to half the scale. See `_combine_scores`.
MAX_REFUTATION_SCORE = 50

# Results recorded before the rename used "SEC Registration". It carried the
# registration weight then and must carry it now, or a stored verification
# silently rescores to the default of 0 -- which returns None, so a refuted
# claim would render as a stage that never ran. The value is spelled the way
# `REFUTATION_WEIGHTS` spells it, because the lookup key is lowercased and a
# lowercase value would score every legacy result at zero.
#
# Mirrors `_LEGACY_LABELS` in verification_parser. Kept as its own literal rather
# than imported: that module pulls in the verification prompt, and this one is a
# pure scoring module that has to stay importable on its own. Two copies is a
# drift risk and is recorded as one rather than quietly accepted.
_LEGACY_LABEL_MAP = {"sec registration": "Official Registration"}


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
        label = item.label.strip()
        label = _LEGACY_LABEL_MAP.get(label.lower(), label)
        penalty += REFUTATION_WEIGHTS.get(label, 0)

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
