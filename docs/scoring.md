# Scoring

Sources: the derivations are executable. `backend/scripts/derive_refutation_weights.py`
holds the pairwise matrices, and `backend/tests/test_risk_model.py` recomputes them on
every run.
Decision records: `docs/decisions/scoring-model.md`.

---

## Bands

| Level | Range |
|---|---|
| Low | 0–30 |
| Moderate | 31–50 |
| High | 51–75 |
| Critical | 76–100 |

**High/Critical jobs are excluded from resume matching.**

---

## Two stages, summed as `max(posting, posting + refutation)`, capped at 100

Verification is asymmetric: **it can only raise the number, never lower it.** See
`docs/decisions/scoring-model.md` for why the 60/40 blend was replaced and why
substitution would be equally wrong.

`verdict.py` produces the final level from these two stages. The verify model no
longer returns `risk_level` or `risk_score`; if an old response carries them, the
flow logs them and ignores them. A strong Channel Match contradiction — a
government claim with a non-`.gov.ph` channel, or a lookalike of the official
domain — gets a floor of `high` (51). It does not reach `critical` on its own;
the combined score still has to pass 75.

### Posting stage (always runs)

`_posting_risk_from_flags` counts the indicators the scan actually reported — high 40,
mid 12, low 4, capped at 100.

A `stale` anomaly assessment removes that specific finding before this count. This
is the one way the model's evidence work moves the level: a retrieved
employer-specific source that accounts for a finding means the finding no longer
stands, and the code should not keep pricing it. `yellow` and `red` assessments
do not change the posting score.

This depends on nothing but the posting, so an offer that names no employer, or one that
cannot be looked up, still gets a verdict.

### Employer stage (only when a name exists)

`_refutation_score_from_verify` is a **penalty that only `red` contributes to**, capped
at 50 (`MAX_REFUTATION_SCORE`).

- It returns `None` when nothing was refuted — the search confirmed nothing either way,
  so it contributes nothing at all.
- `green` also contributes nothing: it means a result stated a fact, not that the fact
  was reassuring.
- A missing stage is **absent, not zero**. A posting that could not be looked up is not
  penalised for the missing lookup, and a posting with no reported indicators is not
  raised by a clean employer record.

---

## Both weight tables are AHP-derived, and the derivations are reproducible

`POSTING_SEVERITY_WEIGHTS` (40/12/4) follows from a Saaty pairwise matrix of 3/9/3 at
CR = 0.0000.

`REFUTATION_WEIGHTS` is the principal eigenvector of a 6×6 matrix over the six
verification categories, anchored so one refuted Channel Match = 25 points.

Re-run `cd backend && python scripts/derive_refutation_weights.py` to see the matrix,
the eigenvector and the ratio. The script holds each judgment as one tuple, so a
disagreement is one integer to change.

`TestTheEvidenceWeightsAreDerivedNotChosen` and `TestTheDocumentedSensitivityIsReal`
recompute both on every suite run, so a weight cannot drift from its matrix without a
failure.

### The anchor is the free parameter, and it sits at a boundary on purpose

AHP yields proportions, never points. `TestTheDocumentedSensitivityIsReal` recomputes the
plateau at anchors 25 and 30 on every run; it holds at 25–30, and the two boundaries fail
in opposite directions: below 25 the three-red case *understates*, above 30 a clean
posting is *overstated*.

Choosing 25 means the reachable error is understatement, which is the right direction
for a tool whose output is read as advice about money.

**Say that rather than claiming the anchor is comfortably central — it is not.**

---

## Never synthesise a score in the client

The number is computed in `verdict.py`, which calls `risk_calculator.py`'s
arithmetic, and sent in `score_breakdown`, which records which stages contributed.
The verify model does not produce it. The panel renders the level and the authored
instruction, not the number; the score is still used for the level bands and resume
matching.

**Presenting a number the system never measured is the exact exposure the prompt rules
exist to prevent.**

---

## Known-unreconciled statements

Listed in `AGENTS.md` rather than resolved here:

- `REFUTATION_WEIGHTS` is recorded with two different value sets across the repo. The
  `25/15/10/8/6/6` set survives only in the deprecated `UNFINISHED-WORK.md`; the code and
  the tests use `25/13/7/4/2/2`.
- `POSTING_SEVERITY_WEIGHTS` provenance is one-sided since `SCORING-SOURCES.md` was
  deleted. This file says AHP-derived, and `test_risk_model.py` re-derives it.
