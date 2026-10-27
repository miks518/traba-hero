# Unfinished Work

> **Deprecated — 2026-10-19.** This file drifted from the code it described and is no
> longer maintained. Open work now lives in `docs/decisions/` and in the contradictions
> list at the end of `AGENTS.md`. Read what follows as history, not as a task list.

Running list of what was left undone, why, and how to verify it. Newest task first.

**Status when this was written.** The developer had manually confirmed the scan
pipeline works end to end with the tightened prompts, the two-stage score, and
`AI_MAX_TOKENS=2048` + `AI_REASONING_EFFORT=low`. What is still open is the
formal output-quality pass below, the outstanding tests, and the deferred
roadmap tasks.

**Do not call the AI provider.** The key is shared and its 24-hour limit blocks
the developer's own testing. Every check in this document is written to run
offline; if something appears to need a live call, it belongs in the checklist
for the developer to run instead.

---

## OPEN — the panel discarded every verification finding, so no verification fix could be evaluated

Found by the developer on 2026-10-18, on the CHED flyer in `jobposts/`. **Defect B is
fixed.** **The two defects it was masking are open and unstarted.**

### The scan of `jobposts/849453314_*.png` got this badly wrong

The flyer is a fake recruitment poster: it carries the **real** CHED Regional
Office VI seal and the real `ched.gov.ph` domain, and it asks applicants for a
mandatory P1,500 application fee, a P800 pre-employment seminar fee, and ID
submission through `recruitment.ched@outlook.com`, an `outlook.com` address
presented as the official one. Brave Search, given the same image, produced six
correct findings in one pass. Trabahero produced a panel that read as a real
employer.

Brave's findings split into two kinds, and only one of them is reachable from
`/api/verify` at all:

| Kind | Brave's finding | Reachable? |
|---|---|---|
| **External** — posting vs. retrieved evidence | `recruitment.ched@outlook.com` and `ched-region6.org` are not CHED's channels | Yes, and `Channel Match` exists for exactly this |
| **Internal** — posting vs. itself | The wordmark reads "COMMISSION FOR **HIGH**ER LEARNING"; the real body is "Commission on Higher **Education**" | **No.** Nothing in the pipeline compares our own extracted fields to each other |

### Three separate defects, not one

| # | Defect | Where | State |
|---|---|---|---|
| **A** | Employer name read off the header wordmark as **`"Commision on High Learning"`** — misspelled, and never reconciled against the real CHED seal and `ched.gov.ph` in the same image | scan `COMPANY NAME:` extraction | **Open** |
| **B** | `VerificationItem.explanation` reached the client and was **never rendered** | `WhatWeChecked.tsx` | **Fixed 2026-10-18** |
| **C** | Whether a correctly-named CHED search catches the `outlook.com` channel | `Channel Match` prompt rules | **Open, and was unknowable while B stood** |

**A is upstream of C.** With a misspelled name, the search is issued for a body that
does not exist, so Brave's "wrong agency name" finding is structurally out of reach.
Company existence was never the question worth asking — the useful question was
whether *this* CHED is the one the results describe.

**C is the hardest case for the prompt's own argument.**
`verification_prompt.py` warns at length that an abundant, reassuring result set reads
as though nothing is wrong. CHED is about as large-and-well-known as an employer gets,
and this posting offers a *second* plausible channel (`hrmo6@ched.gov.ph`) for the
model to hide behind. Whether the existing `Channel Match` rules survive that is a
live question, and it was unanswerable while the panel withheld the sentence.

### Fixed: B, on 2026-10-18

`WhatWeChecked` drew `item.label` and nothing else. `explanation` was parsed,
citation-bound by `_bind_to_retrieved`, weighed by `risk_calculator`, serialised,
typed at `types/index.ts:120` — and dropped by one JSX expression. A `red` Channel
Match rendered as the words "Channel Match" in a red bucket with no sentence on
screen explaining what contradicted what.

- **`FullDetails` now renders each check's explanation**, grouped under the same
  three headings the summary above uses, so a label above lands on its sentence
  below. The grouping is shared via a new `components/report/checkPresentation.ts`
  rather than restated.
- **`shouldShowCheck` runs there too.** Load-bearing: the disclosure is now the
  surface where model-written words about a named employer actually appear, and that
  filter is what keeps the "no scam reports found" restatement off the panel.
  Imported, not reimplemented.
- **The early return now counts explanations**, so a `red` whose citation
  `_bind_to_retrieved` stripped no longer withdraws the disclosure holding the only
  sentence explaining it.
- **The disclosure wears the assessment's tone** via `.tactile-disclosure`, which shares
  the banner's surface rules and adds the 2px press the banner must not have.
- **16 tests** in `FullDetails.test.tsx`, including the one that asserts both slots
  hide the same `yellow` Reputation. No backend change and **no AI call** — the field
  was already on the wire.
- **Everything inside the disclosure is a container**, added the same day after the
  developer opened it. The three blocks ran together as bare text separated only by
  `gap-4`, so where the check findings ended and the search report began was not
  visible — the exact distinction the component exists to keep. Each block now sits in
  a card inside one flat parent, the sources list gained the heading it never had, and
  **each of the three check groups is its own card tinted by its status** (verified
  green, contradicted red, could-not-verify amber) so a contradiction reads as a colour
  before its sentence is read.
- **One rule worth keeping:** *a container that holds containers is not itself a card.*
  Applied to the disclosure body and to the wrapper around the three tinted groups, so
  there is no `tactile-card` inside a `tactile-card` anywhere in the panel. Both cases
  have a test asserting the absence, because it is the kind of thing a later reader
  "fixes" by adding a shadow back.

**Cost of the fix, recorded rather than forgotten:** the security audit's finding on
unvalidated citation hrefs (`docs/security-audit-2026-10-14.md` section 1) had been
narrowed to one disclosure because per-item links were gone. They are back. Still
unfixed; the scheme is still not validated. Two `href={...}` sites in `FullDetails.tsx`
are the complete list in the extension.

### What to do next, in this order

1. **Re-scan the CHED flyer and read the `Channel Match` sentence.** This is now
   possible and is the cheapest thing in this document. It answers C directly and
   costs one scan. Note what the sentence says about `recruitment.ched@outlook.com`
   specifically — not whether a Channel Match card appeared.
2. **A.** Decide whether the scan should report a name that its own extracted fields
   contradict. The internal-consistency check Brave performed has no home in the
   pipeline today, and `SYSTEM_PROMPT.md` is where it would go.
3. **C**, only if step 1 shows the check failing.

Steps 1 and 3 need live provider calls, so they are the developer's to run. Step 2 is
prompt work.

---

## OPEN AND URGENT — the action block keys safety advice to the wrong field

Found by the developer on 2026-10-18, on a live run. **Not fixed.**

**What was seen.** A posting whose only finding was `FEE_MANDATORY` rendered
"What to do now" as *"Keep the conversation on the company's own domain."* — the
**proceed** copy — beside a finding saying the post asks for money up front.

**Why.** `actionsFor()` in `components/report/assessmentCopy.ts` returns the `stop`
copy only when `level === 'high' || level === 'critical'`. So that scan's level
came back `low` or `moderate`. **The advice is keyed to the model-emitted level,
which is the least reliable field on the panel.**

This is the same defect the severity ladder had, and it is documented twice
already: a portal impersonating a government agency while collecting identity
documents scored **4**, because the ladder priced *the category of the ask* and
could not see whether the asker was real. A `low` level alongside `FEE_MANDATORY`
is that failure again, in the UI rather than the arithmetic.

**The fix, once the wording is agreed.** Key the copy to the **code family**,
which is a closed set and therefore comparable across runs:

| Family | Codes | Advice |
|---|---|---|
| M — money | `FEE_MANDATORY`, `FEE_CONDITIONAL`, `PURCHASE_REQUIRED`, `DEPOSIT_REQUIRED`, `PAYMENT_FORWARDING` | Stop; do not send money, refundable or not |
| I — identity | `CREDENTIALS_BEFORE_INTERVIEW`, `DOCUMENTS_VIA_THIRD_PARTY`, `IMPERSONATES_AUTHORITY` | Stop; do not send ID or credentials |
| C — labour | `TASK_FOR_EARNING` | paid per task, not a role |
| O — escape | `OTHER` | say less — we cannot name it |
| *no codes* | — | fall back to the level, so pre-taxonomy history still reads |

**A money or identity code must force the `stop` framing regardless of level.** A
false "proceed" costs a job seeker money; a false "stop" costs one application.
That asymmetry is the argument for inverting the precedence.

This also makes `shareChipsFor()` — currently hardcoded to return `[]` — fall out
for free: bank details under M, ID photos under I. The decision record rejected
generic chips for exactly this reason, so this closes that gap rather than opening
one.

**The wording is the developer's to write.** It is read by someone deciding about
money.

**A second, smaller defect in the same block.** `stop`'s copy currently says *"even
if the request says the fee is refundable"* unconditionally, so a posting with no
fee in it is told to disregard one. That is the panel asserting something about a
posting that is not there. Fixed for free by the code-family keying above.

---

## The report panel — what is built and what is still absent

Shipped 2026-10-18 (`feat(panel)`, merged to `main`). Architecture:
`docs/superpowers/specs/2026-10-17-report-panel-architecture.md`. Component map:
`docs/architecture.md` § The report panel.

**Built:** the slot stack, the authored assessment table, the action block, the
anomaly cards with rule code and quoted span, `WhatWeChecked` split into three
groups, the Full-details disclosure, the footer.

**The 0-100 score and `RiskGauge` are deleted**, along with `describeScoreBasis`
and the ring's dead keyframes. Nothing on the panel prints a figure.

**Still absent, each for a stated reason — do not fill these with placeholders:**

| Absent | Blocked on |
|---|---|
| Provenance line ("posted 2 days ago on a job board") | Nothing. The extension screenshots a region and cannot know where the post came from. **Permanently unavailable**, not deferred |
| Report control | The same reason — there is nothing to report the post *to* |
| "Do not share" chips | Waits on the action-block fix above; the code families exist now |
| Coverage count ("13 of 14 done") | Its denominator must be a constant the backend owns (`checksPlanned`). A count written into the panel drifts with whatever the panel renders |
| Reason why a check could not verify | Needs `unavailable_reason` per verification item |
| Retrieval time per source | Needs `retrieved_at` on evidence. `FullDetails` deliberately drops the design's promise of it rather than faking one |
| Scan id in the footer | Needs `scan_id`. Worth having: it is the join key for a gold set, a feedback rating and a backend log line |
| "Was this accurate?" | No database. See "Reader feedback capture" below |
| Highlighted span inside a quotation | No field says which phrase decided the finding. `.quote-badge` stays commented out with the reason recorded |

**Still open from the architecture spec §8**, none of it started:

1. Three or four assessment phrases, or two? Currently four (one per level), with
   `low` and `moderate` sharing the caution tone.
2. Does the Notes layer get populated, or ship empty? Nothing produces a note
   today, and an empty designed slot is an invitation to fill it with form.
3. Denominator ownership — a backend `checksPlanned` constant, or the panel
   counting what it rendered. Only the first is honest.
4. Does `WhatWeChecked` still need to know about the promotion reorder? It used to
   carry the anomalies as its leading child when promoted; they have their own
   slot now, so that logic has nothing left to do.

**Not tested.** The new panel has no feature tests beyond the subject line
(`ScamScanView.subjectLine.test.tsx`) and the three reopened slots
(`AnomalyCards.test.tsx`). The tombstone at
`views/report-panel-redesign.tombstone.test.ts` records exactly what is
uncovered — including that the deleted score-line tests were honesty assertions
about code that has no test behind it now.

**Stale docs:** `Documentation.md` still names deleted files in AC-10, FR-08,
FR-11, FR-13 and FR-31. `docs/architecture.md`, `docs/decisions/` and
`docs/gotchas.md` were updated.

**`backup/report-panel-b0f464c` is now safe to delete.** Its two backend commits
(`7bbd1e5`, `bcf48ff`) are on `main`. Only its two UI commits remain unmerged and
they conflict with the built panel.

---

## The scan still reports something for every posting

Measured live on 2026-10-12, after narrowing the severity ladder and adding an
actionability bar (`54e50f8`). Three of five probe postings improved and one held,
but the model still finds a finding in every posting it is shown:

- `clean-specific` (registered nurse, stated salary, corporate domain) came back
  `low` for **"applies in person at a retail mall office rather than a typical
  clinical facility"** - the right place to apply for a Starmills job. The model
  invented a norm and flagged the deviation from it. This is the failure mode the
  actionability bar was meant to catch and did not.
- `facebook-generic` came back `low` for **"informal contact channel"** even
  though Messenger application was added to the exclusion list in the same
  commit. The model is not consulting the list, and the actionability bar appears
  to give it a second justification: "would a reader act differently?" reads as
  yes for almost anything.

**The next lever is to drop `low` from the severity ladder entirely**, so the
model must report at `mid` (now only paid-tasks-not-a-role) or `high` or stay
silent. `POSTING_SEVERITY_WEIGHTS` keeps `low: 4` for stored results, so this is
a prompt-only change with no scoring migration.

**It is not done because it cannot be verified.** The probe budget is spent, and
this is precisely the change where being wrong is costly: if the model promotes
everything to `mid` instead of going quiet, every posting scores 12 for noise
and the product looks broken. It needs live runs on the same five-posting
corpus to be worth doing.

**To verify when quota is available**, re-run the same corpus and compare:

| posting | before `54e50f8` | after | expected after removing `low` |
|---|---|---|---|
| clean-specific | mid, 12 | low, 4 | none |
| facebook-generic | mid+mid, 24 | low+low, 8 | none, or one low-equivalent |
| task-earning-dm | mid, 12 | mid, 12 | **mid, 12 - must not be lost** |
| advance-fee-scam | high+high+mid | untested | **high+high - must not be lost** |
| date-two-days-out | mid, 12 | untested | none |

The two bolded rows are the regression guards. A change that silences them has
failed even if every other cell improves.

---

## Task 2.3 — Defamation-Safe AI Output

Code is integrated, the offline gates pass, and the developer has confirmed the
live path works. What remains is the formal output-quality pass below and the
outstanding tests.

### A assessment always exists now

Gating the assessment on the employer check was the wrong model: the product
analyses **offers**, and an employer name is only a secondary input. Scanning is
now also wider than formatted job adverts — chat messages, forwarded paragraphs,
and "earn by doing X" pitches are in scope, with `VALID: false` reserved for
content that offers no work or income at all.

- **Two-stage score.** `_posting_risk_from_flags` counts the indicators the scan
  reported (high 40, mid 12, low 4, capped at 100) and always returns a number.
  `_refutation_score_from_verify` adds the employer check — a penalty only `red`
  contributes to, because `red` means a retrieved source contradicts a claim the
  posting made — and `_combine_scores` takes `max(posting, posting + refutation)`
  capped at 100. The 60/40 blend is gone. A stage that did not run is absent, not
  zero: an unlookable posting keeps its own score instead of being penalised.
  **`REFUTATION_WEIGHTS` are a judgement call, not a measurement** — see the
  Known risks below and `SCORING-SOURCES.md` §11.
- **`POST /api/analyze-offer`** (SSE, 5/min) is the no-employer path. One AI call,
  no search. It returns `KIND` / `ASSESSMENT` / `WHAT IT ASKS` / `WHAT IT OFFERS` /
  `WHAT TO CHECK`, parsed by a new `offer_parser.py`. Rendered by
  `OfferAnalysisCard`.
- It runs **only** when no employer was found. When one was found the existing
  scan + verify data is combined instead, so the common path costs no extra call.
- Unparseable analysis degrades to a generic failsafe, never an error. The score
  never depends on this pass, so a failure costs the explanation, not the assessment.
- `InvalidContentError` is now "Nothing To Assess" and names the content it
  accepts, so a rejected chat message reads as a scope note rather than a bug.

Verified offline: 20 scoring cases and 10 extraction cases, all correct. Both
scratch scripts were deleted; the cases should become permanent tests.

### Earlier fixes in this task

Applied after hands-on testing surfaced them. All offline, all verified by the
existing suites plus a throwaway extraction script that was removed afterwards.

- **`risk_calculator.py` no longer scores absence.** When every verification item
  came back `yellow` — meaning the search confirmed nothing either way — the old
  weighting summed to 49 and reported "Moderate Risk". That is a number derived
  from what we failed to find, presented as a measurement. It now returns
  `(None, None)` so the panel shows "Not scored". Same reason an empty item list
  scores nothing.
- **`extract_company_name` over-captured.** Its character class also matches
  sentence punctuation, so "Acme Corp. We are hiring for a cook" produced the
  company name **"Acme Corp. We are hiring"**. Verification then searched for
  garbage, found nothing, and produced the all-yellow score above — the two bugs
  fed each other. Candidates are now cut at the first clause boundary, stripped
  of parentheticals and of the trailing verb in "X is hiring".
- **All candidates are evaluated, not just the first.** "We are looking for
  staff. Jollibee is hiring servers" matched from "We", and that rejected capture
  hid the real employer behind it. Matches are zero-width so overlapping
  candidates are no longer skipped. Verified against 10 sample strings, including
  three that must still return nothing.
- **`"company"` added to `INVALID_COMPANY_NAMES`.** A bare "Company" was passing
  validation once overlapping candidates were evaluated.
- **Logo instruction added to the scan prompt.** When a posting names no employer
  in its text, the model is now told to check for a logo, wordmark, letterhead, or
  sender name in the image before concluding there is none.
- **Post-only flow in the panel.** With no employer named, the gauge explains that
  there was nothing to look up, the posting analysis sits under it, and the
  verification card tells the user to pick the part of the page carrying the
  employer's name if there is one. No score, no accusation.

### Still not done

| Item | Where | Why |
|---|---|---|
| Prompt-contract tests | new `backend/tests/test_prompt_contracts.py` | Asserts all four prompts contain the observational rules and none of the banned patterns. Cheap and fully offline. |
| `risk_calculator` unit tests | `backend/tests/` | The new all-yellow → `(None, None)` rule deserves a test of its own. Pure function. |
| `extract_company_name` regression tests | `backend/tests/test_search.py` | The 10 sample strings I checked were ad hoc and are now lost. They should be permanent. |
| Scan-mapping tests | extract `mapApiResponse` out of `ScamScanView.tsx` | Module-private today, so "no synthesised score" cannot be asserted. |
| History-migration test | `migrateScannedJobs` in `lib/scanHistory.ts` | Extracted and exported for exactly this. |
| UI copy review | `EvidenceSummary`, `VerificationCard`, `ResumeMatchView` | Reworded from code, not from reading the rendered panel. |

### Live output-quality pass — the developer runs this

The developer has confirmed the pipeline works: scans complete, the employer
name is extracted from the `COMPANY NAME` field, verification runs, and a score
appears. What has **not** been done is the systematic check below, which
validates that the tightened prompts produce the *right* output rather than
merely some output. It needs live provider calls, so it is the developer's to
run — it is roughly ten requests.

Note the prompt was hand-shortened by the developer mid-task. The "do not flag
on their own" list was reduced to a single Gmail line, so missing office
addresses, generic job titles, and "no experience needed" are no longer
explicitly excluded. Watch for false positives there.

| # | Posting | Expected red flags | Expected verification | Expected gauge |
|---|---|---|---|---|
| 1 | Obvious fee scam ("pay a 500 peso processing fee to start") | Exactly one `high`: names the fee request. No claim about the employer. | Reputation `red` only if a result actually describes a report; `yellow` otherwise | Score from posting + employer |
| 2 | Legitimate posting using a Gmail address | **Zero** flags. Gmail is explicitly not a flag. | Green where results support it | Score from posting + employer |
| 3 | Real posting that names no employer | Exactly one `low`: "Company name not stated" | `/api/analyze-offer` runs instead; assessment from the offer itself | Score from the posting alone |
| 3b | Same posting, but the name is only in the logo | Employer name pulled from the logo, no company-name flag | Verification runs normally | Score from posting + employer |
| 4 | A restaurant menu or an article | `VALID: false` and nothing else | n/a | n/a |
| 5 | Deliberately ambiguous posting with a vague employer | At most a `mid`, or zero | Yellow-heavy | Score from posting + employer |
| 6 | A chat message: "Earn 5k/day, pay 500 fee to register" | `VALID: true` plus the fee flag | `/api/analyze-offer`; assessment must name the requested payment | Score from the posting alone |
| 7 | A forwarded recruitment paragraph naming no employer | `VALID: true` | `/api/analyze-offer` | Score from the posting alone |

Also confirm:

- Row 6 must **not** return `VALID: false`. A chat message offering work is in
  scope; that was the original point of widening the gate.
- `KIND` on row 6 should read something like "Chat message" or "Earnings scheme".
- A posting with a real employer and a working search does **not** return an
  all-yellow result. If it does, the extracted name is still dirty — check the
  server log for `company_name='…'`.
- `/api/analyze-offer` output parses. If the card shows the failsafe text, the
  parser missed the labels.
- No red-flag reasoning contains *likely, appears, suggests, probably, seemingly, may be, might be, could indicate, often, typically, we think*.
- No red-flag reasoning contains *always, never, definitely, guaranteed, 100%*.
- Nothing anywhere states or implies that a named company is a scam, fraud, or criminal.
- No verification `DETAIL` claims a website or registry was checked when it was not in the provided results.
- `REPORT` and `RECOMMENDATION` both survive parsing. `/api/verify` is capped at
  `max_tokens=2048` and `/api/analyze-offer` at 1536; if either comes back empty,
  the model truncated.

### Known risks

- **Recall may have dropped.** Fewer hedged flags is the intent, but "less
  ambiguity" and "fewer findings" trade against each other. The table above is
  the only way to find out. If obvious scams in rows 1 and 6 are now missed, the
  severity table in `SYSTEM_PROMPT.md` is too narrow.
- **A new endpoint is barely exercised.** `/api/analyze-offer` was written
  against a stubbed search and a hand-written model response. Its parser is
  deliberately small and has a failsafe, but the shape of real model output is
  an assumption. Rows 3, 6, and 7 above are the test.
- **The refutation weights are a judgement call**, not a measurement. The 60/40
  blend they replaced is gone; `REFUTATION_WEIGHTS` (25/15/10/8/6/6) are the
  current un-derived numbers, carrying the same debt `SCORING-SOURCES.md` §8
  describes for the old employer category weights. They must be re-derived by the
  Saaty method with the consistency ratio reported before this is defended to a
  panel. The breakdown travels with the response, so they can be retuned once
  real data exists.
- **Widening `VALID` means more content is analysed**, including borderline text
  that merely mentions earning. Rows 4 and 6 bracket that; watch for content in
  between being scored when it should not be.
- **Banned-word rules are weaker in Tagalog.** `_language_instruction` asks for
  Tagalog output, and the rules are written as constraints rather than a word
  list for that reason. English word lists will not catch a Tagalog hedge.
- **`_parse_custom` is fragile about section order.** `END FLAGS` resets the
  parser's `matched_any` flag, so it only works because the prompt puts
  `JOB SUMMARY` after it. The prompt now states the order explicitly, but a
  model that reorders sections will produce an unreadable-response error. Worth
  a parser fix, left alone here to avoid changing the wire contract.
- **Old history is unrecoverable.** Migrated jobs are cleared to "Not scored"
  and cannot be re-scored without a new scan. There is no backfill path.

---

## Reader feedback capture ("Was this accurate?") — deferred by decision

The redesigned report panel carries a **"Was this accurate? Yes / No, it was wrong"**
control in its architecture (`jobposts/Job Post Scan Report (updated1).html`, all
three states). It is **kept in the design and not built**, because there is no
database. The developer reviewed this and chose to keep the affordance rather than
cut it.

**Why it cannot ship now.** A click with nowhere to go is worse than no control: it
reads as a working feature and silently discards the only signal that would tell us
the assessment taxonomy is wrong. This is the same failure as the score — presenting a
measurement that was never taken.

**What is missing, concretely.** There is no persistence layer of any kind.
`chrome.storage.local` holds scan history and nothing else; the backend is
stateless and holds no user records by design (Task 2.2, zero-retention). So a
rating has no destination, and a captured rating that cannot be read by anyone is
not data.

**The constraint is the developer's, and it is a sound one** — a thesis project
should not accumulate a database of what real job seekers were shown. Recorded so a
later session does not read the absence as an oversight.

**Options when it is picked up, best first:**

1. **Local capture plus manual export.** Append `(scanId, codes[], level, rating,
   timestamp)` to a `chrome.storage.local` list, and give the reader an "Export
   feedback" control producing a JSON file the user sends to the team. No backend, no
   database, nothing retained server-side. **This is the only option consistent with
   zero-retention**, and it is the one that fits a gold set built by hand anyway.
2. **A mailto or form post to an address the team controls.** No database either, but
   it puts applicant-relevant content — a posting's employer name and findings — in
   an inbox, which is the retention Task 2.2 exists to avoid. Needs a decision first.
3. **A backend endpoint writing to a datastore.** Out of scope while there is no
   database.

**Three things to get right when it is built, each of which is a way the obvious
implementation is wrong:**

- **A three-way control, not two.** "Yes / No" forces every uncertain reader into a
  bucket and biases any rate we publish toward confirmation. It needs a third
  "Partly" or "Not sure". The design as drawn has two options and should change.
- **The rating is only interpretable against the codes, not the assessment.** Store the
  anomaly code set alongside it. A bare "this was wrong" cannot say which code was
  wrong, and the per-code false-negative rate in `§6.3` is the number worth having.
  The retired numeric score made this impossible to reconstruct; codes are what make
  a rating re-analysable later.
- **Self-selection is a real bias and must be stated wherever the rate is quoted.**
  Readers click when they were burned, not at random. An 80% "yes" rate from a
  convenience sample is not an 80% accuracy figure, and a thesis panel will ask.

**Related:** `docs/superpowers/specs/2026-10-17-anomaly-code-set.md` §6 lists what
the codes make measurable; the feedback capture is the only route to measuring drift
in the field rather than against the gold set alone.

---

## Task 2.1 — Data Privacy Consent Modal

Not started. Resume upload currently goes straight to `/api/analyze-resume`
with a confirm dialog but no NPC consent gate. See `CRITICAL.md`.

## Task 2.2 — Backend In-Memory Processing & Zero-Retention

Not started. Relevant to the work above: `scan_flow.py` and `verification_flow.py`
both log AI output at INFO, including job summaries and company names. That is
posting data, not applicant PII, but it is not zero-retention either.

## Task 3.2 — Resilient Registration Lookups

**Done, in a different shape than the task asked for.** There is no `sec_api.py`
in the codebase and no official-registry client to harden. Tavily became the only
retrieval path, so the question of a failing registry API no longer arises; the
"fall back to a Tavily query" branch is the only branch. `CRITICAL.md` was
updated to say this rather than leaving a task pointing at a file that does not
exist.

What carries over from the original intent: one call, one outcome, reported
honestly. `SearchOutcome.ok` and `.results` are independent, a missing API key
is a failure rather than an empty success, and an unusable `results` payload is
a failure rather than a finding. All offline-tested.

## Task 4.1 — Misclassification Reporting

Not started.

---

## Housekeeping found along the way

### Verification output is now JSON

The labeled-text format is gone from the primary path. `/api/verify` and
`/api/analyze-offer` now request `response_format` with a JSON Schema, because
the original reason for the custom format — the native model web search breaking
on curly braces — no longer applies: searches run in the backend and the model
only reads the results.

Key implementation points:

- `provider.require_parameters: true` is set on every structured request. Without
  it a `:free` model can route to an endpoint that does not support structured
  outputs and return prose instead of JSON.
- Strict schemas list every property in `required` and set
  `additionalProperties: false`, including nested array items.
- The guardrail prose is unchanged. A schema constrains shape, not wording, so
  every rule about what may be claimed still has to be said in the prompt.
- **Both text parsers are kept as fallbacks**, not deleted. `_read_verify_output`
  prefers JSON and falls back to the block-wise labeled-text parser if the
  response is not JSON; the offer flow does the same. So a provider that ignores
  structured outputs still produces a result rather than an error.
- `_create_completion` now drops `reasoning` and `structured` independently when
  a provider rejects either, and records both in the one-time
  `[lm] Generation config in use:` line as `structured_output` and
  `dropped_params`.

**Not yet exercised against the live model.** If `:free` endpoints for this model
do not support structured outputs, the rejection fallback will fire and the flow
will quietly use the text parser — which is why the config line matters. Grep for
it after the first run.

**Still not converted:** `/api/scan`, `/api/scan-text`, `/api/analyze-resume`, and
`/api/match-resume` still use labeled text. They stream, and the scan path relies
on `_VALID_LINE_RE` finding `VALID: false` mid-stream to stop early and save
tokens. Switching them to JSON would require buffering the whole response,
giving that up. Worth doing only if the text-parser brittleness bites there too.

### Resolved: the web search was rebuilt on Tavily

The DuckDuckGo module produced results for the wrong query. A search for
`Cleanfuel Philippines company` returned YouTube TV Help pages; `Vikings`
returned Knowunity; `Caishen` returned Wikipedia articles about the Chinese god
of wealth and Philippine senate impeachment news. Every response was
**successful** � HTTP 200, results present, no throttling flag � so nothing in
the code or the logs indicated a fault. Two intermediate diagnoses (a "/" in a
joined company name, and a throttling window) were both wrong.

Four defects compounded:

1. **Category headings asserted facts retrieval never established.** A result
   found by a `"<company> scam fraud complaint"` query was printed under a
   `[SCAM REPORTS]` heading. A regulator's complaint form appeared there as if
   it were a scam report. This was the most serious of the four.
2. **Snippets were silently dropped** by reading the library's `body` key where
   the normalised result used `snippet` (twice, in two different formatters). The
   model was shown titles only and correctly reported that no result mentioned SEC
   registration.
3. **Empty results were indistinguishable from failures** � `[]` for both a
   rate-limited query and a company with no footprint, so a retrieval failure
   read as a clean company.
4. **Engine selection was a coin flip.** The `ddgs` library picks an engine at
   random when none is named; most engines returned nothing from this machine, so
   an unpinned call frequently hit an engine serving a stale cached page.

`app/services/search.py` replaces the 620-line module. `SearchOutcome.ok` and
`.results` are independent fields, so a caller cannot read "retrieval failed" as
"nothing found". One query replaces four, with no category headings — the model
sorts results into the three categories itself. The query strips a trailing
corporate suffix and appends `Philippines`. The scan no longer searches at all, so `/api/verify` is the only consumer of online
evidence. `ai_tools.py` and `chat_with_tools` were dead tool-calling code and are
gone.

**Validated end to end.** A real run confirmed the SEC card turns green with a
registration number in its detail. The ranking fix that resolved the wrong-entity
results is the `country="philippines"` boost plus a trailing-suffix strip in
`build_query()`; both are now env-configurable via `TAVILY_COUNTRY` and
`TAVILY_SEARCH_DEPTH`. The search debug tab has served its purpose and was
removed along with `/api/debug/search`, `SearchRawPanel`, and
`SearchOutcome.raw_response`.

### Under investigation: only one verification card rendered

**Status: no longer reproducing; the cause was never confirmed.** This section
is kept so the log lines it names are the ones to check if it returns.

Reported as: the panel showed only **Company Existence** even though the log
showed values for the other categories. The frontend was ruled out — it maps
`result.items` with no filter — and the parser passed every well-formed shape
tested, so the cause was a deviation in the model's actual output. The parser
was made block-wise and a partial parse now logs
`[verify] Parsed N of 3 expected categories; missing: ...`, so if it returns,
that line plus `[verify] Raw AI response` will identify it. The search
rebuild may also have removed the trigger: retrieval no longer stamps results
with category headings.

### Remaining levers on reasoning volume


The model is a native reasoning model and the developer is rate-limited on other
free multimodal options, so switching models is not available. Scans complete at
`AI_MAX_TOKENS=2048` + `AI_REASONING_EFFORT=low`, so this is optimisation, not a
blocker. The remaining levers are all input size, and none of them can be
verified without a live call:

- **Reasoning can now be switched off outright.** `AI_REASONING_ENABLED=false`
  sends `{"reasoning": {"enabled": false}}`, which is the documented OpenRouter
  way to turn thinking off rather than fund it. It overrides the other two
  controls, because a provider returns 400 for a disabled reasoning combined
  with a high effort level. Not yet tried against the live model — the
  `AI_REASONING_ENABLED` tri-state (`None` unset, `True` force on, `False` off)
  and the override are verified offline. If it is rejected, the existing
  fallback logs `[lm] Provider rejected the reasoning parameter` and the app
  continues on `effort: low`, which is the setting already confirmed working.
  Note `exclude: true` is not the same thing — it only hides reasoning from the
  response while still paying for it.
- **Image dimensions — done.** `MAX_DIMENSION` lowered 1920px → 1280px, so one
  image is 44% of the pixels and a 4-image scan goes from ~8.3M to ~3.7M pixels.
  If dense small print starts scanning badly, raise it and expect reasoning cost
  to rise with it.
- **Screenshot count — not done.** `MAX_SCREENSHOTS` is 4, so a full scan can
  still send four images. Halving it to 2 is the largest remaining lever on
  deliberation, at the cost of requiring two scans for a long posting. The
  developer chose to leave it.
- **Temperature — not done.** `AI_TEMPERATURE` is 0.2. For structured extraction
  0 is the conventional choice and is free, but it will not shorten reasoning
  much and was not selected.
- **Unverified assumption.** Lowering pixel count reduces *vision* cost
  measurably; that it also reduces *reasoning length* is unproven here. Treat any
  improvement as unconfirmed until the developer measures it.

### Resolved: the reasoning model exhausted the token budget

This cost most of a session. **Resolved — the developer confirmed scans complete
at `AI_MAX_TOKENS=2048` with `AI_REASONING_EFFORT=low` and
`AI_REASONING_MAX_TOKENS=0`.** Recorded so it is not re-diagnosed.

- **Symptom.** `[lm] Stream produced no content ... finish_reason=length` with a
  reasoning-only character count. The model spent the whole budget thinking and
  was cut off before answering, so the parser saw an empty string.
- **The prompt was only half the problem.** `OUTPUT_RULES` and `SCAN_FIELD_RULES`
  (3,541 chars) were sent twice — once in the system prompt, once in the user
  message via `SCAN_OUTPUT_FORMAT` — making the request 9,236 chars of which
  ~3.9k was duplication. `SCAN_OUTPUT_FORMAT` is now the bare skeleton, 5,367
  chars total, no information lost. Shortening `SYSTEM_PROMPT.md` by hand did
  **not** fix it, because the failure was budget exhaustion, not input size.
- **What actually fixed it** was `AI_REASONING_EFFORT=low`, which reduces
  deliberation at the source. `AI_REASONING_MAX_TOKENS` only truncates it and a
  truncated reasoning phase can make a provider re-attempt, so set one or the
  other, not both.
- **Lowering `AI_MAX_TOKENS` guarantees the failure.** 2048 cannot hold a long
  think plus an answer. Keep the cap above the reasoning budget.
- **Two instrumentation bugs made the diagnosis harder than it needed to be.**
  The reasoning counter summed `reasoning` and `reasoning_content` on every
  chunk, so a provider mirroring the same text into both fields counted every
  character twice — a failure reported 16949 chars where the model had emitted
  8681. The counter now counts an identical pair once and reports per-field
  totals. Separately, an early probe of mine failed for the wrong reason and a
  second gap let a `ValueError` reach production; the lesson recorded in
  `AGENTS.md` is to exercise the consumer of a function, not just the function.
- **The diagnostics are the durable win.** `EmptyModelResponse` names which of
  the three causes occurred, and `[lm] Generation config in use:` logs the config
  actually in force once per process. Grep for that line when anything fails.

  `AI_MAX_TOKENS=4096` in `backend/.env`; the developer has since confirmed
  2048 works with `AI_REASONING_EFFORT=low`.
- **Deliberation can now be capped separately from the answer.**  `AI_REASONING_MAX_TOKENS` and `AI_REASONING_EFFORT` map to OpenRouter's
  normalized `reasoning` parameter, sent via `extra_body` on both the streaming
  and non-streaming paths. Both default to off, so nothing is sent until they
  are set in `backend/.env`. `AI_REASONING_EFFORT=low` is the setting the
  developer validated live.
- **A provider that rejects the parameter degrades instead of breaking.** A 400
  that names the parameter triggers one retry without it, sets a process-level
  flag so it is never sent again, and logs a warning. A 429, 500, or an
  unrelated 400 propagates untouched. Verified offline across all of those.
- **`chat()` now also reports an empty response.** The reasoning-only failure was
  previously only detected on the streaming path; `chat()` returned `""` to the
  verification and offer-analysis flows, which then fell into their parse
  failsafes with no explanation. It now raises `EmptyModelResponse` naming the
  model and the reasoning character count. The `max_tokens` on those two
  non-streaming calls was also very tight for a reasoning model — 512 for
  `/api/analyze-offer` and 1536 for `/api/verify` — now 1536 and 2048.
- **`[verify] ValueError: not enough values to unpack (expected 3, got 2)`.**
  `format_verification_context` iterated `_VERIFY_QUERIES` with
  `for k, _, _ in ...` while its entries are 2-tuples, so every verify request
  that reached that function raised and fell into the generic handler, which
  reported a verification failure instead of a crash. It slipped through because
  the earlier probe only counted searches and never called the formatter that
  consumes their output. Fixed, and the path is now covered end to end with a
  stubbed search: populated results, zero results, and a placeholder company
  name.
- **`is_valid_company_name("Not stated")` returned True.** The value the model is
  now instructed to emit when a posting names no employer was not in the
  rejection set, so a direct `POST /api/verify` with that value would have
  searched for the literal string. The `NOT_STATED_MARKERS` check now lives in
  `is_valid_company_name` itself, so every caller rejects those values rather
  than only the scan path. The probe above found this one.
- **The employer name was being guessed by regex over prose.** The scan asked the
  model to work the name into a natural-language summary and then tried to
  fish a company name out of that sentence, which is how verification ended up
  searching for an unrelated phrase and returning all-yellow. The scan now
  outputs a dedicated `COMPANY NAME:` field, parsed by `_parse_custom` and used
  ahead of the regex (which stays as a fallback for older output).
  `clean_company_name()` rejects "Not stated" and the other placeholders the
  model writes when it has nothing, and drops a leading article so "The company"
  is judged on the word after it.
- **Verification asked about six things using eight searches.** Two categories
  were redundant — the endpoint cannot run without a company name, and "Online
  Presence" restated "Company Existence" — and "Scam Reports" plus "Social
  Reputation"   were the two most prone to invention. Now three categories
  (Company Existence 40, SEC Registration 25, Reputation 35, summing to 100)
  behind four searches. The prompt forbids inventing another category. Separately,
  `search_company()` is now memoised per company name, because a single text scan
  called it twice and paid for eight searches twice.
  *Superseded:* the three-category, four-search design was replaced by six claim
  categories behind 2-5 searches. See `AGENTS.md` § Key Architecture.
- **Empty AI responses were unloggable (`[scan-image] tokens=0, chars=0`).** The
  streaming client read only `delta.content` and did `if not chunk.choices:
  continue`, so three different failures all became "empty string" and surfaced
  as a misleading "unreadable response":
  1. a mid-stream provider error frame — OpenRouter reports upstream failures,
     including rate limits on the routed provider, as a data frame inside an
     otherwise successful 200 stream, so no HTTP error is ever raised;
  2. a model refusal, which arrives in `delta.refusal` and was never read;
  3. reasoning-only output, which goes to a provider-specific `reasoning` field
     the SDK does not declare.

  `chat_stream_pieces` now collects all three, logs the model,
  `finish_reason`, and the counts, and raises `EmptyModelResponse` with the
  reason. The scan, resume, and match flows handle it separately from their
  generic handler, so the log line and the user-facing message are both
  accurate instead of saying the AI returned garbage. Verified offline against
  real SDK chunk objects built with `.construct()` for all four cases plus the
  healthy path. The probe script was deleted; it should become a permanent
  test.

  This was **not** caused by the prompt work. Zero tokens means no text came
  back to parse, and a bad prompt yields wrong text rather than no text. The
  likely trigger is the configured model,
  `dots-studio/dots-3-note-preview:free` — a free route with no availability
  guarantee, on a key that had already hit a 24-hour limit. Worth confirming the
  chosen model accepts image input as well; a non-vision model given
  `image_url` content can return empty on every request.
- **DEFENSE-CH1-3-QA.md** still claims a local Gemma 4 LLM at `localhost:1234`
  and a "fine-tuned XLM-RoBERTa classifier" that does not exist in the codebase.
  It needs rewriting, not word-swapping.
- **`lmstudio.md`** is a 200-line LM Studio changelog with no inbound references.
  Probably delete.
- **`GET /health` is rate limited to 30/min per IP** and the extension now polls
  it every 4s (15/min). Fine for one user, but a shared NAT address with two or
  more open panels will 429. Raise the limit or back off to 6s if seen.
