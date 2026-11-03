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
- **The matcher feeds on green and yellow.** Superseded 2026-11-04 — see the
  addendum at the end of this record. This entry originally read "green only",
  on the reasoning that yellow is uncertainty the reader is told to settle first.
  That reasoning was sound when yellow was rare; `ordinary_at_unestablished_employer`
  made it the normal outcome, and the rule starved the matcher.
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

- **The matcher fed on green only** at the time — a posting whose employer could
  not be established left the matchable pool. Superseded 2026-11-04, for the
  reason this addendum was itself a field regression: a rule that excludes the
  common case leaves nothing to match. See the addendum at the end.
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
yellow family already says the right thing. The matcher fed on green only at
the time; superseded 2026-11-04 — see the addendum at the end.

Known open issue, recorded so it is not mistaken for this rule: a posting
with a *recognised finding the classifier cannot subclassify* (an
`OTHER`/empty code, or a fee with no stated recipient) still prices
`unclassified` yellow in every state â€” field report 2026-10-31 (a real
coffee shop with two confirmed checks, flagged for "an address it does not
print", rode the absence-guardrail phrase gap into `unclassified`). The
absence-phrase fix and the catch-all pricing are separate decisions.


---

## 2026-11-03 â€” the establishment-keyed caution, with the bound-source guard

Supersedes both earlier attempts recorded above. Three designs have now met
the same field report (an AI-generated posting â€” a fictional employer,
nothing online â€” must read Caution, while a real employer whose Company
Existence check confirms must read green):

1. **2026-10-28, the word fix.** "Proceed" became "Nothing found against it"
   and the `(ordinary, unknown)` cell stayed green. The fictional posting
   still read green â€” the word claimed only that nothing was found, which
   was technically true and practically reassuring.
2. **2026-11-02, the establishment-keyed rule.** The cell moved to yellow.
   The field regression: *every* posting whose Company Existence check did
   not land exactly `confirmed` read Caution â€” because the verify prompt
   makes `yellow` the default ("the results do not settle it") and the
   establishment derivation honoured only exactly `confirmed`. A confirmed
   existence on a real employer read Caution only through a different door
   (an `OTHER`-coded finding pricing `unclassified`) â€” recorded below as an
   open issue, not this rule.
3. **2026-11-02/03, the retrieval-keyed floor.** `code_assessment` took
   `has_results` (the retrieved set non-empty) and floored green to yellow.
   Failed in the field within a day: keenable returns *some* results for
   almost any query, so "the lookup found something" is nearly always true
   and never distinguished a fictional employer from a real one. The
   fictional posting read green again. Reverted.

The rule that ships:

- The `(ordinary, unknown)` cell is **yellow**, rule
  `ordinary_at_unestablished_employer` â€” the establishment-keyed rule from
  design 2, restored.
- **The hallucination guard moves to its right layer.** The 2026-11-02 rule
  had one genuine catch: a model *claiming* a confirmed existence on an
  empty result set read green through the derivation. That is now guarded
  in `establishment_from_record`: a Company Existence check counts as
  `supported` only when it is `confirmed` **and carries a bound
  `source_url`**. A "confirmed" with no bound result is the model's bare
  word â€” the binding strips an unbacked URL â€” and the model's word alone
  does not establish the employer. A real confirmation always carries its
  source (the prompt requires citing on green, and binding keeps retrieved
  citations).

Consumers: no copy changes (keyed by colour; the yellow family already
says the right thing). The matcher fed on green only at the time; superseded
2026-11-04 — see the addendum at the end.

Known open issue, unchanged: a posting with a recognised finding the
classifier cannot subclassify (an `OTHER`/empty code â€” field report: a
sex-limited-hiring observation on a real coffee shop, and an "address it
does not print" absence phrasing that slipped the guardrail's list) still
prices `unclassified` yellow in every state. The taxonomy/coverage decision
remains open; it is the actual driver of the "everything is Caution"
impression and is not addressed by any of the three designs above.

---

## 2026-11-04 — the matcher includes caution, and the banner stops naming a cause

Two changes, both forced by the grid moving rather than by a defect.

### The matcher feeds on green *and* yellow

**The old rule starved the matcher.** "Green only" was written when yellow was
the exception. The 2026-11-03 restoration made `ordinary_at_unestablished_employer`
yellow, and because the verify prompt makes `yellow` the *default* Company
Existence status, a posting whose existence check lands anywhere but exactly
`confirmed` is yellow. In the field that is most postings — and the Match tab
was excluding almost everything it was built to match.

Every addendum above recorded "the matcher feeds on green only", and a rule that
was right three times became wrong the moment the distribution moved. **A
consumer rule keyed on a colour inherits the colour's frequency; when the
frequency changes, the consumer rule is what breaks.**

What replaces it:

- `isMatchableJob` is `green || yellow`, still gated on `isJobPosting`.
- `isExcludedJob` is `red` alone.
- A yellow row says **"Included in resume matching. Read the caution before
  applying."** in the caution tone. Being matched is not a reassurance, and the
  row has to say both things: this fits your profile, and the posting still
  carries an open question.

**Red stays excluded.** It is the one state where the record contradicted who is
asking; matching a reader's resume to it would be recommending they engage.

The old `isMatchableJob` docstring already said yellow should not be withheld —
it said *"Neither is a reason to withhold the matching; `red` is"* — while the
body returned `=== 'green'`. The prose and the code had disagreed since the
function was written, and no test covered the docstring.

### The banner words name the evidence, not a cause

| Token | Was | Now |
|---|---|---|
| `green` | "Nothing found against it" | **"Nothing stands out"** |
| `yellow` | "Caution" | **"Caution"** — unchanged |
| `red` | "Contradicted" | **"Something is not right"** |

**Green's old word claimed the search came up empty.** Green fires at
`confirmed` (a comparison matched) and at `supported` (a record named the
employer and no comparison was made). In the first case the search found plenty.
The new word claims resemblance to the ordinary case and nothing more.

**Red's old word named one of its two causes.** `red` is reached by a
contradicted channel *and* by `task_for_earning_at_unestablished_employer`, which
involves no contradiction at all. "Contradicted" was false for the second, and it
also collided with the anomaly cards' per-finding status, which is a different
claim — so a card reading "Contradicted" could sit above a banner reading
"Nothing found against it". "Something is not right" is true on every path to red
and does not claim a source.

**"Caution" survives** for the reason the original entry gives: it points the
"why" question at the posting rather than at the system.

**The rename is the banner only.** `checkPresentation.ts` keeps "Contradicted"
for a check row, `AnomalyCards` keeps it for a per-finding status, and
`mapApiResponse.assessmentLabel()` keeps the old words for the history list. The
three surfaces answer different questions and are deliberately allowed to differ;
what is not allowed is one word for three claims.

### Still open after this

A contradicted **anomaly** still does not move the assessment: at a confirmed
employer it reads `green`, so "Something is not right" on a card can sit above
"Nothing stands out" on the banner. The card's status is a claim about one
finding; the banner's is about who is asking. Renaming made the collision
less likely to read as a contradiction, and did not resolve it.

