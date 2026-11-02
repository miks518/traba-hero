# Decision record — the assessment speaks in evidence, not verdicts

Date: 2026-10-28
Owner file: `backend/app/services/scanner/assessment.py`; the panel's words live in
`entrypoints/sidepanel/components/report/assessmentCopy.ts` and `assessmentLabel()`
in `mapApiResponse.ts`.

---

## The rule

The assessment tokens are the grid's colours — `green`, `yellow`, `red` — and the
panel's chip words for them are:

| token | chip word | the sentence under it |
|---|---|---|
| `green` | **Nothing found against it** | "What the posting asks for is ordinary, and nothing we found says otherwise." |
| `yellow` | **Caution** | rule-driven: what the ask is, and what the record did and did not settle |
| `red` | **Contradicted** | "A source states something different from what the posting states." |

None of the three is a verdict about the posting, and only `red` is loud — because
`red` requires a contradiction, which is evidence the posting cannot supply about
itself.

## Why the old words went

The old ladder was `clear` / `note` / `caution` / `stop`, rendered as **"Proceed"**,
"Note", **"Caution"**, **"Do not proceed"**. Two of the four were the defect:

- **"Proceed" claimed a clearance the grid never measured.** `clear` fires for
  ordinary requests at *confirmed*, *supported* **and unknown** establishments — and
  on the unknown case "Proceed" tells the reader the posting is safe when the honest
  answer is "nothing we found says otherwise". That is the same lie as rendering
  "0 / Low Risk" for an unverified employer, which `isUnverifiedEmployer` already
  refuses in the gauge.
- **"Do not proceed" was backed but misdirected.** It only fires on contradiction,
  so it had evidence — but the word names the system's ruling, while the fact is
  that a retrieved source *contradicts* the posting. The fact is the defensible
  thing to say.

"Caution" survived the rename deliberately, and the panel question decided it. The
candidate "Uncertain" was rejected because it points the "why" question at the
*system* ("your detector doesn't know?"), where "Caution" points it at the *posting*
("why should I be cautious?" → "because it asks for money and documents, and the
search could not establish who is asking"). A chip word that sends the question
outward is the one a defense wants.

## Why `note` and `caution` merged

They were both uncertainty: `note` was an unclassifiable request (or a prohibited
request at a confirmed employer), `caution` was a prohibited request at an
unestablished one. The product's own user never noticed the difference — the tier
existed in the code and not in the reader's mental model. **The colour now says
"uncertain"; the rule in the breakdown says why** (`unclassified_request`,
`prohibited_at_confirmed_employer`, `prohibited_at_unestablished_employer`), and the
panel renders that rule under the chip. A decision table that drifts by one cell is
still caught cell by cell in `test_code_assessment.py`.

## What each consumer does now

- **Elevation is keyed by the rule, not the colour.** `shouldElevateEvidence` leads
  with the evidence for `red`, and for `yellow` only when the rule is
  `prohibited_at_unestablished_employer` — the scam shape. An unclassified request
  at a confirmed employer is the same colour and deliberately does not lead.
- **The matcher feeds on green only.** Yellow is uncertainty — the reader is told
  to settle the ask before sending anything, so it is not a posting the matcher may
  use. (Under the old ladder, `note` was matchable and `caution` was not; the merge
  takes the safe side.)
- **The task-for-earning override is yellow → red.** A prohibited request with
  `TASK_FOR_EARNING` at an unestablished employer outranks "uncertain" — the rule
  name `task_for_earning_at_unestablished_employer` records it.
- **Stored history is mapped, not rewritten into silence.** A stored
  `clear`/`note`/`caution`/`stop` maps onto the colour whose cell it would have
  been, keeping its recorded strength: a stored `stop` was a contradiction finding
  and renders as "Contradicted". Records mapped from the retired *level* ladder keep
  the `previous-procedure` stamp, and the old `low`/`moderate`/`high`/`critical`
  words render as the recorded meaning ("High risk"), not as a current assessment.
- **The banner copy is authored per colour** (`assessmentCopy.ts`), with legacy
  words aliased so an old stored scan renders the right copy instead of crashing on
  a table key that no longer exists.

## What this does not claim

- That "Caution" is evidence-shaped. It is the one advisory word in the set, and it
  is allowed because its backing is a stated fact about the posting's demand; the
  sentence under it stays pure evidence.
- That the colours are the same axis as the verification checks' statuses. They are
  not — one red check does not make the assessment red; only
  `establishment_contradicted` does. The chip and the check rows are visually
  separate for exactly this reason.

## 2026-11-02 — the unknown column is yellow

This record fixed the *word* on 2026-10-28 ("Proceed" → "Nothing found against
it") and deliberately kept the `(ordinary, unknown)` cell green. Its own
reasoning flagged the lie-shape: "Proceed" on the unknown case told the reader
the posting is safe when the honest answer was "nothing we found says
otherwise". The rename made the sentence true — but the field test of
2026-10-31 showed the *colour* still overclaims comfort: an AI-generated
posting (fictional employer, nothing online) returned green with every check
"Could not verify", and "Nothing found against it" on a lookup that found
nothing at all still reads as reassurance.

Company existence is the heavy evidence. A posting that names an employer the
lookup could not establish is itself the caution, so the cell moves:

- `(ordinary, unknown)` is now **yellow**, rule `ordinary_at_unestablished_employer`
  (parallel to `prohibited_at_unestablished_employer`). The whole `unknown`
  column is yellow: **the record cannot clear the posting by being silent.**
- Green now requires the record to have established something — `supported`
  (an independent result names the employer) or `confirmed` (the channel
  matched). "Nothing found against it" is therefore only ever said about a
  lookup that found the employer.
- The Knollridges regression is unchanged: a real firm whose Company Existence
  check confirms is `supported`, and stays green.

Consumers, per the rules above:

- **The matcher feeds on green only** — a posting whose employer could not be
  established leaves the matchable pool. That is consistent with the recorded
  principle ("yellow is uncertainty ... not a posting the matcher may use").
- **Elevation does not lead for the new rule.** `shouldElevateEvidence` leads
  for `prohibited_at_unestablished_employer` because there is a prohibited ask
  to lead with; at `(ordinary, unknown)` the checks are silent, so there is no
  evidence to elevate — the chip and the statement carry the caution.
- The statement and options needed no change: the generic yellow branch already
  renders "The posting asks for nothing the rules prohibited. Nothing in the
  record establishes who is behind the posting.", and the yellow options are
  the two verification moves.

---

## 2026-11-03 â€” the caution is keyed on retrieval, not establishment

Supersedes the 2026-11-02 addendum above. That addendum moved
`(ordinary, unknown)` to yellow keyed on the establishment state, and the
field regression was immediate: **every** posting whose Company Existence
check did not land exactly `confirmed` read Caution â€” including real
employers with two confirmed checks, because the verify prompt makes
`yellow` the default for Company Existence ("the results do not settle itâ€¦
This is the default") and the establishment derivation honours only exactly
`confirmed`. The establishment-keyed rule priced the model's hedging as
evidence of a fictional employer.

The rule is now keyed on the retrieval fact instead:

- The verify endpoint passes `has_results` (the retrieved result set is
  non-empty) into `code_assessment`. A `green` from an empty lookup floors to
  **yellow**, rule `no_results_found`. Red stands; a yellow the grid chose is
  not demoted.
- The `(ordinary, unknown)` cell returns to **green**: a found company whose
  checks hedged keeps the benefit of the doubt, because the lookup found
  something and nothing contradicts it.
- The 2026-10-31 field report stays fixed by the floor: a fictional employer
  with zero results floors green to yellow â€” and the floor also catches the
  worse variant, a model *claiming* a confirmed existence on an empty result
  set, which the establishment-keyed rule would have missed.

Consumers: no copy changes â€” the chip words are keyed by colour and the
yellow family already says the right thing. The matcher keeps feeding on
green only: a posting whose lookup found nothing leaves the matchable pool,
which is the same decision the 2026-11-02 addendum recorded for the
establishment-keyed rule.

Known open issue, recorded so it is not mistaken for this rule: a posting
with a *recognised finding the classifier cannot subclassify* (an
`OTHER`/empty code, or a fee with no stated recipient) still prices
`unclassified` yellow in every state â€” field report 2026-10-31 (a real
coffee shop with two confirmed checks, flagged for "an address it does not
print", rode the absence-guardrail phrase gap into `unclassified`). The
absence-phrase fix and the catch-all pricing are separate decisions.

