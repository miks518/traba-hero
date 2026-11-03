# The money-direction guard

Date: 2026-11-03
Owner files: `backend/app/services/money_direction.py`,
`backend/app/services/scanner/scan_result.py`,
`backend/app/services/scanner/request_class.py`,
`backend/app/services/scanner/offer_flow.py`

---

## The failure

Field test, 2026-11-03: six postings were scanned, and **two of them came back
with a fee anomaly whose posting mentioned no fee** — its only number was a
salary. A clean posting that asks for nothing reads Caution once an invented
fee prices `prohibited` (or `unclassified`, via the `OTHER` catch-all), so the
wrong finding does not merely add a card: **it is the card that decides the
colour.**

The prompt had the rule already. `SYSTEM_PROMPT.md` said "only a stated amount
that does not fit the role is" flagged, and the fallback copy said the same. The
model read it and reported a fee anyway, which is the lesson
`docs/decisions/search-retrieval.md` records about the conclusion-word filter:
**a prompt sentence is not a control.** A better model does not close this door
either, for the same reason `docs/decisions/absence-guardrail.md` gives — nothing
in the pipeline checked the label against the rule.

## The decision

A money finding is only a finding if its **quotation** shows the applicant being
told to pay. `money_direction.quote_pays_the_applicant` reads the span and
answers one question; three layers consult it.

### `money_direction.quote_pays_the_applicant`

Two directions, named by the posting's own words:

- **Money TO the applicant** — salary, wage, allowance, commission, bonus, a
  rate per day/month, `13th month pay`, `pay rate`. Not a charge.
- **Money FROM the applicant** — a payment verb (`pay`, `remit`, `deposit`,
  `purchase`, `shoulder`, `magbayad`, `ibayad`, …), a send that names a transfer
  target, or a charge noun (`fee`, `payment`, `deposit`, `bond`, `bayad`).

Four boundaries are deliberate and each answers a shape that was measured:

1. **A bare amount is never a charge.** `P18,000-P22,000/month` returns `False`.
   That is the case the guard exists for.
2. **`send` requires a transfer target.** "Send your resume to hr@x.ph" is the
   ordinary application instruction and carries no money; "Send P200 to GCash"
   does. A bare `send` match dropped the most common line in the corpus.
3. **`pay` is also a noun.** `13th month pay` and `pay rate` are pay TO the
   applicant, so the noun forms are checked before the verb branch.
4. **A clause that says there is no charge clears its own span** — "no
   placement fee", "we do not charge any fee", "walang bayad". A bare noun match
   on `fee` would otherwise read the cleanest possible posting as a fee demand.
   The clear is scoped to the clause so "No placement fee. A P1,000 deposit is
   required." keeps the deposit.

**The negation clears a fixed window, not a measured one, and that is a choice.**
Two attempts at "the negated noun and nothing after it" failed in the same way:
a lazy gap stopped one word early on `charge` in "do not charge any fee", and a
boundary lookahead then refused the honest matches ("no placement fee is
required"). The shipped version clears from the operator to the end of its
clause. A wrong clear is the safe direction here: it can only let a fee through
unpriced, and a real fee stated inside a "no fee" clause is vanishingly rare.

### The three gates

| Layer | File | What it does |
|---|---|---|
| Wire | `scan_result._anomalies` | Drops a `FEE_*`/`PURCHASE_REQUIRED`/`DEPOSIT_REQUIRED` finding whose present quote does not show a payment request. Logged at warning, like the absence guardrail. |
| Price | `request_class._class_for` | A fee code whose quote shows pay returns `ordinary`, so it cannot price `prohibited` — or ride the `OTHER` catch-all to `unclassified`. |
| Offer path | `offer_flow._read_offer_output` | The scan's findings come back over HTTP and the offer model adds its own codes; both pass the same test before becoming a request class. |

The price gate repeats what the wire gate does on purpose: the verify stage
receives the scan's findings back over HTTP as `VerifyAnomaly`, and the offer path
merges the model's own codes in. Neither route passes through `scan_result`.

### A blank quote is not a contradiction

**The guard checks direction only when there is a quote to read.** A money
finding with no quote is a different defect — `quote_is_clean` owns the quote, and
the prompt now requires one — and treating "no quote" as "no payment request"
here would classify every unquoted fixture and every stored record as an
`ordinary` posting. Absence is never a contradiction, and a gate must not invent
a reading of a span it was not given.

This was measured: the first draft refused blank quotes and broke 14 tests whose
fixtures predate the quote requirement, each of which was asserting the fee
classifier, not the guard.

## The prompt changed too

`SYSTEM_PROMPT.md` and `prompts.SCAN_FIELD_RULES` both gained a money-rule
paragraph and worked examples, and both changed the quote rule from **"omit the
QUOTE line rather than paraphrasing"** to **"do not report the anomaly at all:
no QUOTE, no ANOMALY."**

That is not cosmetic. The old wording *permitted* an anomaly with no quote, and
the wire accepted it: `clean_quote("")` returns `""`, the finding survives, and
it still priced. The new wording and the prompt's examples are the instruction;
the three gates above are the enforcement.

## What this does not fix

- **`OTHER` still prices `unclassified` → yellow.** A finding the taxonomy cannot
  name, or one whose code the model mistyped, is a caution in every establishment
  state. The second live run produced exactly this: "Informal application via
  messaging" → `OTHER` → `unclassified` → Caution, on a rule the prompt forbids
  outright. The guard above is about *invented fees*; this is about a taxonomy
  that has no weight for a finding it does not recognise. Recorded as open in
  `docs/decisions/assessment-vocabulary.md`.
- **A fee the model reports correctly but prices wrongly.** `fee_recipient` and
  `fee_timing` are still the model's answers. An honest fee with an invented
  recipient still prices as the recipient says.
- **The scan still logs raw model output.** Unchanged, and owned by the
  zero-retention task in `CRITICAL.md`.

## Tests

- `backend/tests/test_money_direction.py` — the reader (32 spans), the wire gate,
  the price gate, and one end-to-end scan response. Mutation-checked in both
  directions: disabling the guard fails 6, an always-true reader fails 23, an
  always-false reader fails 16.
- `backend/scripts/live_money_probe.py` — the manual live instrument. Six
  postings: four salary-only, two real fees. **Not part of the offline suite**;
  it calls the live provider and must be run with permission.
