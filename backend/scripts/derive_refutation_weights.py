"""AHP derivation for the evidence-stage weights.

Run from `backend/`:  python scripts/derive_refutation_weights.py

The point is not to produce a number. It is to make the number *checkable*: the
pairwise judgments below are stated one at a time in the code, the principal
eigenvector is computed from them, and the consistency ratio is reported against
Saaty's 0.10 threshold. If someone disagrees with a judgment they can change one
integer in `JUDGMENTS` and re-run; what they get back is the weight that judgment
implies and whether the set is internally consistent.

Why pairwise judgments and not the old weights: `{"Channel Match": 25, ...}`
was chosen by judgement and, normalised, encodes a 4.2x spread. On Saaty's 1-9
scale that is "extremely more important" - a claim about the ordering that was
never checked, and one where an error in the ordering would be invisible because
nothing tested it.
"""

import math

# No numpy. This is a 6x6 matrix, so the eigenvector is a few lines of
# arithmetic, and `requirements.txt` does not carry numpy. Importing it would mean
# `pytest.importorskip` in the test that guards these weights - which skips
# silently on a clean install, leaving the guardrail present in the file and
# absent in practice. That is the failure mode this repository keeps warning
# about, applied to its own test.

# Saaty's Random Index, n = 1..10 (Saaty 1980; Triantaphyllou 1993).
RANDOM_INDEX = {1: 0.0, 2: 0.0, 3: 0.58, 4: 0.90, 5: 1.12, 6: 1.24, 7: 1.32,
                8: 1.41, 9: 1.45, 10: 1.49}

CR_THRESHOLD = 0.10

# Order is the claimed hierarchy, strongest first. It fixes the matrix layout
# only; nothing depends on it.
CRITERIA = [
    "Channel Match",
    "Similar Offers",
    "Reputation",
    "Location / Branch",
    "Company Existence",
    "Official Registration",
]

# One judgment per unordered pair, in Saaty's 1-9 fundamental scale:
# 1 equal, 3 moderate, 5 strong, 7 very strong, 9 extreme. Each entry is
# (more important, less important, value). The reciprocal is implied.
#
# The question behind every entry is the same: only `red` scores, so what
# matters is how much a refutation from this check would prove. Frequency does
# not enter this - `_refutation_score_from_verify` sums weights over the red
# items actually returned, so a check that stays silent contributes nothing on
# its own. A check that cannot be refuted needs no weight.
#
# A check a real employer always passes cannot tell a real employer from one
# borrowing its name. That is why the bottom two sit where they do.
JUDGMENTS = [
    # Channel Match - the only check that can expose an impersonation.
    ("Channel Match", "Similar Offers", 3),
    ("Channel Match", "Reputation", 5),
    ("Channel Match", "Location / Branch", 7),
    ("Channel Match", "Company Existence", 9),
    ("Channel Match", "Official Registration", 9),
    # Similar Offers - tests the specific way the posting asks applicants to
    # earn, which is the dominant Philippine recruitment-scam shape. Was
    # "Scheme Corroboration" until 2026-10; the weight is unchanged by the rename
    # because the check is, and only the reader-facing label moved.
    ("Similar Offers", "Reputation", 3),
    ("Similar Offers", "Location / Branch", 5),
    ("Similar Offers", "Company Existence", 7),
    ("Similar Offers", "Official Registration", 7),
    # Reputation - a published complaint is a named source contradicting the
    # posting, but it describes the employer's history rather than this posting.
    ("Reputation", "Location / Branch", 3),
    ("Reputation", "Company Existence", 5),
    ("Reputation", "Official Registration", 5),
    # Location / Branch - a contradiction needs a source that lists branches.
    # Small employers rarely have such a listing, so this mostly stays silent.
    ("Location / Branch", "Company Existence", 3),
    ("Location / Branch", "Official Registration", 3),
    # Existence and Registration are equally hard to refute: a company either has
    # a findable registration or has none, and "no filing was found" is silence
    # rather than a contradiction. Equal is the honest judgment.
    ("Company Existence", "Official Registration", 1),
]


def build_matrix() -> list[list[float]]:
    n = len(CRITERIA)
    index = {name: i for i, name in enumerate(CRITERIA)}
    matrix = [[1.0] * n for _ in range(n)]
    for more, less, value in JUDGMENTS:
        i, j = index[more], index[less]
        matrix[i][j] = float(value)
        matrix[j][i] = 1.0 / value
    return matrix


def geometric_mean_weights(matrix: list[list[float]]) -> list[float]:
    """Row geometric means, normalised - the standard AHP approximation."""
    n = len(matrix)
    gms = [math.prod(row) ** (1.0 / n) for row in matrix]
    total = sum(gms)
    return [gm / total for gm in gms]


def principal_eigenvector(matrix: list[list[float]], iterations: int = 500) -> list[float]:
    """Power iteration on the matrix, normalised to sum to 1.

    500 iterations on a 6x6 matrix with positive entries converges long before
    the last one; the count is a ceiling, not a cost.
    """
    n = len(matrix)
    vector = [1.0] * n
    for _ in range(iterations):
        vector = [sum(matrix[i][j] * vector[j] for j in range(n)) for i in range(n)]
        total = sum(vector)
        vector = [v / total for v in vector]
    return vector


def consistency(matrix: list[list[float]], weights: list[float]) -> tuple[float, float, float]:
    """Return (lambda_max, CI, CR).

    `lambda_max` is the Rayleigh quotient: the mean of `A w / w` over the
    criteria. Averaging rather than taking one column is the usual remedy when
    the eigenvector is approximate.
    """
    n = len(matrix)
    ratios = [
        sum(matrix[i][j] * weights[j] for j in range(n)) / weights[i]
        for i in range(n)
    ]
    lambda_max = sum(ratios) / n
    ci = (lambda_max - n) / (n - 1)
    cr = ci / RANDOM_INDEX[n] if n in RANDOM_INDEX and RANDOM_INDEX[n] else 0.0
    return lambda_max, ci, cr


def anchor_to_points(weights: list[float], anchor_criterion: str, anchor_points: int) -> list[int]:
    """Scale proportions so `anchor_criterion` is worth exactly `anchor_points`.

    AHP yields proportions, never point values. This is the free parameter
    `docs/scoring.md` calls out for the severity weights, and it is
    defended the same way here - by sensitivity analysis.

    Largest-remainder rounding, so the vector still sums in proportion rather
    than drifting a point or two.
    """
    scale = anchor_points / weights[CRITERIA.index(anchor_criterion)]
    exact = [w * scale for w in weights]
    floors = [int(v) for v in exact]
    # Hand the leftover points to whichever criteria lost the most to truncation.
    remainder = round(sum(exact)) - sum(floors)
    order = sorted(range(len(exact)), key=lambda i: exact[i] - floors[i], reverse=True)
    for i in order[:max(0, remainder)]:
        floors[i] += 1
    return floors


def main() -> None:
    matrix = build_matrix()
    gm = geometric_mean_weights(matrix)
    pe = principal_eigenvector(matrix)
    lambda_max, ci, cr = consistency(matrix, pe)

    print("Pairwise comparison matrix (Saaty 1-9 scale)\n")
    header = "".join(f"{name[:11]:>13}" for name in CRITERIA)
    print(f"{'':22}{header}")
    for i, name in enumerate(CRITERIA):
        row = "".join(f"{matrix[i][j]:>13.3f}" for j in range(len(CRITERIA)))
        print(f"{name:22}{row}")

    print("\nWeights\n")
    print(f"{'Criterion':22}{'Geometric mean':>16}{'Principal eig.':>17}")
    for i, name in enumerate(CRITERIA):
        print(f"{name:22}{gm[i] * 100:>15.2f}%{pe[i] * 100:>16.2f}%")
    print(f"{'TOTAL':22}{sum(gm) * 100:>15.2f}%{sum(pe) * 100:>16.2f}%")

    print("\nConsistency\n")
    print(f"  lambda_max = {lambda_max:.4f}")
    print(f"  CI         = {ci:.4f}")
    print(f"  RI  (n=6)  = {RANDOM_INDEX[6]}")
    print(f"  CR         = {cr:.4f}   threshold {CR_THRESHOLD}   "
          f"{'PASS' if cr < CR_THRESHOLD else 'FAIL'}")

    # Anchor: one refuted Channel Match is worth half the evidence stage's
    # ceiling, since MAX_REFUTATION_SCORE is 50.
    points = anchor_to_points(pe, "Channel Match", 25)
    current = {"Channel Match": 25, "Similar Offers": 15, "Reputation": 10,
               "Location / Branch": 8, "Company Existence": 6, "Official Registration": 6}

    print("\nPoints, anchored so one Channel Match red = 25\n")
    print(f"{'Criterion':22}{'AHP':>7}{'Current':>9}{'Gap':>7}{'Ratio now':>12}{'Ratio AHP':>11}")
    for i, name in enumerate(CRITERIA):
        print(f"{name:22}{points[i]:>7}{current[name]:>9}{points[i] - current[name]:>+7}"
              f"{current[name] / current['Channel Match']:>12.2f}{pe[i] / pe[0]:>11.2f}")
    print(f"{'TOTAL':22}{sum(points):>7}{sum(current.values()):>9}")


if __name__ == "__main__":
    main()