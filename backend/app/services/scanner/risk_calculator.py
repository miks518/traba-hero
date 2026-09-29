from app.models.schemas import RedFlag, VerificationItem

# Weights used to turn the indicators reported in a posting into a score. They
# are deliberately simple and fixed so the number can be explained to the user:
# a high-severity indicator is a concrete instruction or request inside the
# posting, a mid is a checkable gap, a low is something common in Philippine
# postings that is weak on its own.
POSTING_SEVERITY_WEIGHTS = {"high": 40, "mid": 12, "low": 4}


def _level_for(score: int) -> str:
    if score <= 30:
        return "low"
    if score <= 50:
        return "moderate"
    if score <= 75:
        return "high"
    return "critical"


def _posting_risk_from_flags(flags: list) -> tuple[int, str, dict]:
    """Score a posting from the indicators reported in it. Returns (score, level, breakdown).

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
    """The penalty an employer's record adds. Only `red` carries weight.

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


def _combine_scores(posting_score: int | None, verify_score: int | None) -> tuple[int, str] | tuple[None, None]:
    """Add the verification penalty to the posting score, capped at 100.

    This was a 60/40 blend, and the blend was wrong in a way that inverted the
    meaning of the number. A posting that had already maxed out — three
    high-severity indicators — was pulled to 60 by a clean employer record,
    because averaging lets corroborating evidence outvote the thing the reader
    actually asked about. And a published scam report added 14 points over that
    clean record, so negative evidence moved the number far less than the
    absence of it. "We found nothing" scored 100, tying "three damning
    categories".

    So verification is now **asymmetric: it can only raise.** What the employer
    record establishes is that this company exists, is or is not registered, and
    what has been published about it. None of that makes a posting asking for an
    advance fee less dangerous, and a clean employer must not be able to pull a
    maxed posting back down to a number the reader would read as tolerable.

    A missing stage is absent, not zero: a posting that could not be looked up is
    not penalised for the failed lookup.
    """
    if posting_score is None:
        if verify_score is None:
            return None, None
        return verify_score, _level_for(verify_score)
    if verify_score is None:
        return posting_score, _level_for(posting_score)
    total = min(100, posting_score + verify_score)
    return total, _level_for(total)
