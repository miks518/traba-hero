from app.models.schemas import VerificationItem


def _calculate_risk_score_from_verify(items: list[VerificationItem]) -> tuple[int, str]:
    """Calculate risk score from verification items. Each category contributes based on status.
    Red = full weight, Yellow = half weight, Green = none. Returns (score, riskLevel)."""
    category_weights = {
        "Company Name": 30,
        "Company Existence": 25,
        "SEC Registration": 15,
        "Scam Reports": 30,
        "Online Presence": 15,
        "Social Reputation": 25,
    }
    total_weight = sum(category_weights.values())  # 140
    penalty = 0
    for item in items:
        label = item.label.strip()
        weight = category_weights.get(label, 10)
        if item.status == "red":
            penalty += weight
        elif item.status == "yellow":
            penalty += weight // 2
    score = min(100, round(penalty / total_weight * 100))
    if score <= 30:
        level = "low"
    elif score <= 50:
        level = "moderate"
    elif score <= 75:
        level = "high"
    else:
        level = "critical"
    return score, level
