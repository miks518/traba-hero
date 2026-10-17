# Scoring

Sources and derivations: `SCORING-SOURCES.md` (repo root).
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

### Posting stage (always runs)

`_posting_risk_from_flags` counts the indicators the scan actually reported — high 40,
mid 12, low 4, capped at 100.

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

AHP yields proportions, never points. `SCORING-SOURCES.md` §9 shows the stable plateau
is anchor 25–30 and that the two boundaries fail in opposite directions: below 25 the
three-red case *understates*, above 30 a clean posting is *overstated*.

Choosing 25 means the reachable error is understatement, which is the right direction
for a tool whose output is read as advice about money.

**Say that rather than claiming the anchor is comfortably central — it is not.**

---

## Never synthesise a score in the client

The number the panel shows is computed in `risk_calculator.py` and sent in
`score_breakdown`, which records which stages contributed.

**Presenting a number the system never measured is the exact exposure the prompt rules
exist to prevent.**

---

## Known-unreconciled statements

Two statements about the weight tables disagree and are listed in `AGENTS.md` rather
than resolved here. See the contradictions list:

- `REFUTATION_WEIGHTS` is recorded with two different value sets across the repo.
- `POSTING_SEVERITY_WEIGHTS` is described both as originally chosen and as AHP-derived.
