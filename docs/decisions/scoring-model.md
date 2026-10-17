# Decision record — the scoring model

Owner file: `backend/app/services/scanner/risk_calculator.py`.

---

## The two stages are additive and asymmetric

**Verification can only raise the number, never lower it.**

This replaced a 60/40 blend, and the blend was wrong in a way that inverted the meaning
of the score:

- A posting that had already maxed out — three high-severity anomalies, 100 — was
  pulled to **60** by a clean employer record, because averaging lets corroborating
  evidence outvote the thing the reader asked about.
- A published scam report then added only 14 points over that clean record, so
  **negative evidence moved the number far less than the absence of it.**
- And "we found nothing at all" scored 100, tying "three damning categories".

What an employer record establishes is that a company exists, is registered, and has
what published about it — none of which makes an advance-fee posting less dangerous.

`test_risk_model.py` pins each of these.

**The `max` is what lets the split stay balanced without reintroducing the blend.** A
plain 50/50 mean would report three high-severity anomalies plus an unlookable employer
as 50 — "moderate" — because half of nothing is nothing. The floor keeps the posting
stage's own full 0–100 range intact and gives evidence a guaranteed share of the
ceiling above it.

---

## A blend was the wrong shape, and so would have been subtraction

The instinct that verification should be able to pull a bad posting down is sound.
Deducting for a clean employer record is not:

- It can reach zero on a posting that demands an advance fee — the worst failure this
  product can have.
- "green reduces" is incoherent per category (green on Reputation can be a one-star
  employee account).
- Subtraction rewards an employer with no online footprint, making unverifiable look
  safer.

---

## `yellow` carries no weight, which is a change from the blend

It used to count for half, because something had to pull a blend's average down. Added
to a posting it would penalise a check that found nothing, so it now contributes zero and
an unconfirmed or verified-clean employer leaves the posting's own number untouched.

`green` is zero for a stronger reason: **green means a result stated a fact, not that
the fact was reassuring.**

`_refutation_score_from_verify` returns `None` rather than `(None, None)` — its
all-yellow short-circuit and the all-yellow short-circuit to `(None, None)` in the dead
`_calculate_risk_score_from_verify` are the same rule on two different scales.

**The category-weighing tests probe the weight with `red` items for this reason** — a
yellow would score 0 for every label and could not tell one weight apart from another,
so those tests would have passed without guarding the rename at all.

---

## `_calculate_risk_score_from_verify()` is dead code that reads as live

Nothing calls it; the verification flow calls `_refutation_score_from_verify()`. It is
retained only because `test_scanner_package.py` pins the package's symbol list, and
`test_verify.py` still asserts its output — which is exactly why a reader following the
score lands there and is misled.

Its scale is a *different* one (a share of the old 40/25/35 category weights normalised
to 100), so it is **not** a drop-in for the stage that replaced it.

**Do not treat a passing test against it as evidence that the evidence stage works.**

---

## Category ordering is defensible; the weights were re-derived

Channel Match carries the most weight because it is the only check that can detect an
impersonation, since a real employer passes every existence, registration and branch
check.

The weights themselves are recorded in `docs/scoring.md` along with their Saaty
derivation. `SCORING-SOURCES.md` §8 describes the debt the earlier employer-category
weights carried, and that debt is what the re-derivation replaced.

**Note:** two statements about the weight values disagree across the repo. They are
listed in the contradictions section of `AGENTS.md` rather than resolved here, because
resolving them requires reading the derivation script's output against the live table.
