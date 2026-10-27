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
