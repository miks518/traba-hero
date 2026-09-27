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
    """Calculate risk score from verification items. Each category contributes based on status.
    Red = full weight, Yellow = half weight, Green = none.

    Returns (None, None) when nothing was confirmed, i.e. when every item is
    yellow. A score built entirely out of "we found no information" measures the
    search, not the posting, so reporting it as a risk figure would put a number
    on the panel that the system never actually determined. An empty item list
    means verification produced no findings at all, for the same reason.
    """
    if not items or all(item.status == "yellow" for item in items):
        return None, None

    category_weights = {
        "Company Existence": 40,
        "SEC Registration": 25,
        "Reputation": 35,
    }
    total_weight = sum(category_weights.values())  # 100
    penalty = 0
    for item in items:
        label = item.label.strip()
        weight = category_weights.get(label, 10)
        if item.status == "red":
            penalty += weight
        elif item.status == "yellow":
            penalty += weight // 2
    score = min(100, round(penalty / total_weight * 100))
    return score, _level_for(score)


# The posting is what the user actually asked about, so it carries the larger
# share. External verification is corroborating evidence and can move the number
# in either direction, but it is never allowed to be the whole answer.
POSTING_SHARE = 0.6
VERIFICATION_SHARE = 0.4


def _combine_scores(posting_score: int | None, verify_score: int | None) -> tuple[int | None, str | None]:
    """Blend the posting score with the external verification score.

    Whichever stage is missing is simply absent, not treated as zero: a posting
    that could not be looked up online is not penalised for the missing lookup,
    and a posting with no reported indicators is not raised by a clean employer
    record.
    """
    if posting_score is None:
        if verify_score is None:
            return None, None
        return verify_score, _level_for(verify_score)
    if verify_score is None:
        return posting_score, _level_for(posting_score)
    blended = round(posting_score * POSTING_SHARE + verify_score * VERIFICATION_SHARE)
    return blended, _level_for(blended)
