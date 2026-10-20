# Decision record — the scoring model

Owner files: `backend/app/services/scanner/risk_calculator.py` (weights and
arithmetic), `backend/app/services/scanner/verdict.py` (the code-owned final
level), `backend/app/services/scanner/channel_match.py` (Channel Match severity).

---

## Amendment (2026-10-21): the level is code-owned again

The model's `risk_level` and `risk_score` are no longer inputs to the verdict.
The reason is a reproducible false positive, not a preference: a real employer
whose posting used `name.company@gmail.com` while its own site was
`company.com.ph` produced a red Channel Match and, because the same model emitted
the overall level, "Do not proceed" from one weak observation.

The split that replaced it:

- The model reports Channel Match **facts** in `channel_match`: the printed
  channels, the official channels, whether the posting claims to be government,
  and a factual sentence. It does not assign the category's status.
- `channel_match.py` assigns that status from the facts. A free email at an
  otherwise matching company is yellow. A government claim with a non-`.gov.ph`
  channel, or a lookalike of the official domain, is red. A non-matching channel
  plus an independent finding is red. Everything else is yellow.
- `verdict.py` combines the posting's findings with `_refutation_score_from_verify`
  using the arithmetic below. A strong Channel Match red gets a floor of
  `high` (51), not `critical`; the most serious headline still needs the combined
  score to reach 76.
- A `stale` anomaly assessment removes that specific finding from the posting
  score. This keeps the 2026-10-20 feature's purpose without letting the model
  write the level. `yellow` and `red` assessments change nothing.

The model's fields are still read by the parser for old or schema-less responses,
and logged when present, but the flow does not pass them to `code_verdict`. The
schema no longer asks for them. `tests/test_code_verdict.py` fails if the flow
stops calling `code_verdict` or if the schema starts asking for a level again.

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

## Amendment (2026-10-20, superseded in part on 2026-10-21): stale findings

The additive asymmetry above still governs the arithmetic. The 2026-10-20
amendment moved the level to the verify model so it could weigh the anomaly
assessments. The 2026-10-21 amendment takes the level back into code; the stale
rule survives, implemented as an exclusion rather than a model judgement:

- A finding an **employer-specific** source accounts for (`stale`) is removed
  from the posting score. The finding no longer stands, and the code should not
  keep pricing it.
- A finding a source contradicts (`red`) keeps its weight. The contradiction is
  not a reason to stop counting what the posting asked for.
- A finding that is `yellow` never lowers it. A general page about a practice,
  an absent source, or a failed search is not evidence in the reader's favour.

The parser only keeps a `stale` assessment when its `source_url` was retrieved,
and demotes an unbacked one to `yellow`. The exclusion is therefore reading a
fact the retrieval layer checked, not a model conclusion on its own. It does not
make the employer's record clean and cannot subtract from unrelated findings.

The earlier rule's reason still binds on the status-bearing checks: a `green`
category carries zero weight, and the absence of a bad record must not make an
advance-fee posting look safer. See
`docs/superpowers/specs/2026-10-20-anomaly-evidence-assessment-design.md` §7 and
`docs/decisions/verification-design.md`.

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

Nothing calls it; `verdict.py` calls `_posting_risk_from_flags()` and
`_combine_scores()`. It is retained only because `test_scanner_package.py` pins
the package's symbol list, and `test_verify.py` still asserts its output — which
is exactly why a reader following the score lands there and is misled.

Its scale is a *different* one (a share of the old 40/25/35 category weights
normalised to 100), so it is **not** a drop-in for the stage that replaced it.

**Do not treat a passing test against it as evidence that the evidence stage works.**

---

## Category ordering is defensible; the weights were re-derived

Channel Match carries the most weight because it is the only check that can detect an
impersonation, since a real employer passes every existence, registration and branch
check.

The weights themselves are recorded in `docs/scoring.md` along with their Saaty
derivation. The earlier employer-category weights were set by judgement, and that debt is
what the re-derivation replaced; the judgment list now lives in
`backend/scripts/derive_refutation_weights.py`, which the tests run against the live table.

**Note:** two statements about the weight values disagree across the repo. They are
listed in the contradictions section of `AGENTS.md` rather than resolved here, because
resolving them requires reading the derivation script's output against the live table.
