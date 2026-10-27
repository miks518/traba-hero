# Anomaly evidence assessment

**Status:** built (2026-10-20). Implementation notes at the end.
**Date:** 2026-10-20.
**Owner files:** `backend/VERIFY_PROMPT.md`,
`backend/app/services/scanner/verification_prompt.py`,
`verification_flow.py`, `app/models/schemas.py`,
`entrypoints/sidepanel/components/report/AnomalyCards.tsx`,
`entrypoints/sidepanel/components/report/ReportPanel.tsx`,
`entrypoints/sidepanel/views/ScamScanView.tsx`,
`entrypoints/sidepanel/hooks/useScanSession.ts`,
`entrypoints/sidepanel/lib/api.ts`, `entrypoints/sidepanel/types/index.ts`.

---

## 1. The problem

The scan reads a posting and reports anomalies from that posting alone. A fee
is flagged because the posting asks for one. The report shows the card
immediately, before anything has been compared against the world, so a fee for
a medical examination and a fee with no stated purpose look identical.

The verify stage already retrieves public evidence about the employer. It
deliberately does **not** receive the anomalies today — the prompt says that
invites the model to answer about the posting instead of the employer. That
decision is the one this design reverses, narrowly: the verify stage is asked
to judge each anomaly against the evidence it retrieved, and to say what the
evidence shows.

The reader's request, in their words:

> some anomaly like mandatory fee actually exists in some real job posts, like
> that fee is for medical test and such. But a real anomalous fee does not state
> what is it for, or they state its for something but evidence say that that
> company or employer does not collect fees.

So the anomaly is no longer the finding on its own. The finding is the anomaly
**plus what the evidence says about it**.

---

## 2. What the reader decided

These are decisions, not options for the builder:

- **The card shows as soon as the scan lands.** It does not wait for
  verification. The reader sees what was found immediately.
- **While verification is running, the severity is neutral.** The card does not
  say `Critical`, `Serious`, or `Minor` yet. The scan's severity is input to the
  check, not a conclusion the panel has earned. A neutral `Checking` chip sits
  where the severity chip will be, and a box with a loading ring under the card
  says the finding is being confirmed against public sources.
- **Every detected anomaly stays on the report.** Nothing is silently dropped.
  The card carries the evidence assessment and the final severity once verification
  settles.
- **Grey means a public source about this employer accounts for it, and the
  anomaly is stale.** Example: the posting says the fee is for a medical test and
  the employer's own material supports that. The card stays, its severity becomes
  `Stale` in grey, it says what the source shows, and it links the source. Grey
  is not a success colour and not a severity: it says this finding no longer
  stands.
- **Red means a public source contradicts the posting.** Example: the employer's
  own pages state it does not collect fees from applicants. The card stays, keeps
  the scan's severity, and links the source.
- **Amber means nothing could check it.** No employer was named, the search did
  not complete, or the results did not settle it. Amber is the warning sign of
  unconfirmed, and the card's severity becomes `Unconfirmed`. The card says
  which of those happened.
- **No employer named is still shown.** The card stays with the amber
  `Unconfirmed` warning saying there was no company to search and it is shown so
  the reader notices it. There is no verify call to wait for, so it appears with
  that state as soon as the scan lands.
- **The final severity follows the evidence.** It is not a second model
  judgement: `stale` → `Stale`, `red` → the scan's severity, `yellow` →
  `Unconfirmed`, still checking → `Checking`.
- **The evidence colour follows the evidence, not the severity.** Contradicted
  is red regardless of the anomaly's severity. Amber is for "not checked", not
  for "minor contradiction".

---

## 3. Goals

- The verify model receives the posting's findings and judges each one against
  the retrieved evidence and the posting's own stated details.
- The report shows the finding immediately, with a neutral checking state while
  the evidence is being gathered.
- The report shows one evidence assessment per anomaly, with the source where
  there is one, and a final severity that follows that assessment.
- Failure states are explicit and never read as a clean result.
- Stored history keeps the assessments it had; old scans without assessments do not
  pretend to have them.
- The existing scoring does not gain a new number in the client. The model's
  risk level remains the model's.

## 4. Non-goals

- Changing the anomaly taxonomy or the risk bands.
- Adding searches. The verify stage uses the results it already retrieved.
- A separate "dismissed anomalies" section. Every anomaly stays in one list, and
  its assessment says what happened.
- A client-side judgement of whether an anomaly is real. The assessment comes from
  the backend; the client only maps the assessment to the chip.
- Replacing the section heading. It stays "Anomalies detected" and counts the
  cards shown, because every card is an anomaly the scan detected. The evidence
  strip is what says whether it held up.

---

## 5. The assessment model

Three values, reused from the existing verification vocabulary:

| Wire | Panel label | Meaning | Source required |
|---|---|---|---|
| `stale` | **Stale** (grey) | A retrieved source about this employer accounts for what the posting states. The finding no longer stands. | Yes |
| `red` | **Contradicted** | A retrieved source states something different from what the posting states. | Yes |
| `yellow` | **Not confirmed** | No source settled it, no employer was named, the search failed, or no assessment was returned. | No |

The panel sentence under the label is the model's `finding`, in one plain
sentence, naming what the source states. The source link is the source the
sentence is about.

**A yellow sentence may stand without a source.** It is a statement about what
the results did not establish ("The results do not mention a fee collection
policy for this employer"), which is the one kind of sentence that has no
source by construction. A stale or red sentence is shown only with the source
it is about.

`stale` and `red` are not statements that the employer is safe or dangerous.
They describe the relationship between one posting detail and one retrieved
source. The assessment is about one posting detail, not a clean record for the
employer.

### The severity chip follows the assessment

The scan's severity is input to the check, not the chip the reader sees first.
The chip moves through four states:

| State | Chip | When |
|---|---|---|
| Waiting | **Checking** (neutral, outline) | Verification is in flight for this anomaly. |
| Stale | **Stale** (grey) | The assessment is `stale`. The evidence accounted for it and the finding no longer stands. |
| Red | The scan's severity — **Critical** / **Serious** / **Minor** | The assessment is `red`. The finding stands, with the scan's weight. |
| Amber | **Unconfirmed** (amber) | No employer, a failed search, no assessment, or an unreadable one. |

`Checking` is not a severity. It says the severity is not known yet. The card
must not tint its border, chip, or accent with the scan's severity while in that
state, or the reader reads `Critical` from the colour even though the word is
gone.

`Stale` is not a severity either. It says the finding no longer stands, which is
why it is grey rather than a green success colour: the card is not praising the
employer, it is retiring the finding.

The mapping is derived, not model output. `stale → Stale`, `yellow →
Unconfirmed`, `red → scan severity` are three deterministic rules in the client,
so the chip cannot disagree with the strip above it. The verify model is not
asked for a second severity judgement.

### Why a stale card is still shown

The anomaly was detected. Hiding it would erase the fact that the system looked
at it and found an ordinary explanation. Keeping it with a grey `Stale` assessment
tells the reader what was considered and why it did not end the reading. It also
keeps the count honest: what the scan detected is what the scan detected.

### The default is amber, never stale

A missing assessment, an unreadable one, an out-of-range index, or a `stale`/`red`
without a source all become amber. Absence is never evidence in the reader's
favour. This is the same rule the rest of the verification stage already obeys.

---

## 6. Wire contract

### Request

`VerifyRequest.anomalies` already exists and is already sent by the extension.
Extend `VerifyAnomaly` with the two fields the scan already carries but the
verify request currently drops:

- `code` — the taxonomy id, bounded like the other anomaly text.
- `quote` — the verbatim span from the posting, bounded like the other anomaly
  text.

The index of each anomaly in the list is its identity for this request. No new
id is invented. The list is small and bounded by `MAX_VERIFY_ANOMALIES`.

### Response

The verify result gains one key:

```json
"anomaly_assessments": [
  {
    "index": 1,
    "status": "stale",
    "finding": "The employer's careers page states that a 500 peso medical examination is paid before deployment.",
    "source_title": "Example Logistics - Careers",
    "source_url": "https://example.ph/careers"
  }
]
```

- `index` is 1-based, matching the numbered list in the prompt. The client
  resolves it against the list it sent.
- `status` is `stale`, `yellow`, or `red`.
- `finding` is one plain sentence. It does not repeat the anomaly.
- `source_title` / `source_url` are copied from the results. A URL outside the
  retrieved set is dropped, and a `stale`/`red` left without a source is
  demoted to amber.
- One assessment per anomaly is expected. Missing assessments become amber with
  an authored "not checked" sentence. Extra or out-of-range indices are dropped
  and logged.
- The no-company early return includes an empty `anomaly_assessments` list. The
  client supplies the no-employer amber note.

### Client shape

`Anomaly` gains an optional field:

```ts
assessment?: {
  status: 'stale' | 'yellow' | 'red';
  finding: string;
  sourceTitle?: string;
  sourceUrl?: string;
};
```

It is optional on read because stored history predates it. When it is absent,
the card still renders, with the appropriate amber note derived from why it is
absent.

### Telling "ran and missed this one" from "never ran at all"

These are different facts and must not collapse into one note. The client keeps
one extra marker on `ScanResult`:

```ts
/** The verify response carried an `anomaly_assessments` key, even if empty. */
anomalyAssessmentRun?: boolean;
```

`api.ts` must preserve absence versus emptiness: `undefined` when the wire key is
missing (an old backend), `[]` when the key is present and empty (a new backend
that returned no assessments). The hook sets the marker from that distinction.
Without it, a pre-feature scan would claim a assessment was sought and not recorded,
which is false for those scans.

### More anomalies than the request can carry

The verify request refuses more than `MAX_VERIFY_ANOMALIES` (20) in one call.
Nothing on the scan side caps the list, so a 21st anomaly would 422 the whole
verification and leave every card amber with no risk level.

The client sorts by severity (`high`, then `mid`, then `low`, preserving order
within a severity), sends the first 20, and leaves the rest without a request
slot. The omitted cards still render, with the amber note in §8. This is a
client-side selection, not a backend cap change: the request boundary stays as
strict as it is today.


---

## 7. Prompt and parser

### The prompt

`VERIFY_PROMPT.md` and `_FALLBACK_VERIFY_PROMPT` both gain:

- An eight-key output format, adding `anomaly_assessments` to the seven.
- A numbered block of the posting's findings, each with its flag, reasoning,
  severity, code and quote, clearly marked as the posting's claims rather than
  facts about the employer.
- The rules for the three assessments, mirroring the claim-check rules already in
  the prompt:
  - `stale` only when a result **about this employer** supports the posting's
    stated explanation. A general page about the practice — a clinic's standard
    exam fee, an advisory saying such fees are common — is not evidence about
    this employer and leaves the finding amber. A result that only confirms the
    employer charges *some* fee, without accounting for the purpose the posting
    states, is not stale either: the purpose is the claim under test.
  - `red` only when a result **about this employer** states something different
    from what the posting states. "Nothing was found" is amber, never red.
  - `yellow` when the results do not settle it, or when the only support is a
    general page rather than one about this employer.
  - A `stale` or `red` must name the result it relies on.
  - The finding states what the source says, in one plain sentence. No
    conclusion words, no hedges, no absolutes.
  - Do not add, remove, merge, or renumber findings. One assessment per number.
- The posting's own stated claims (`attributes`) are already in the prompt.
- A short excerpt of `job_summary` is added as context for judging the
  findings. It is labelled as context, not as a claim about the employer, and
  is bounded in the prompt builder so the request's 50,000-character cap cannot
  become 50,000 characters of prompt. The existing prompt comment that says
  `job_summary` is "actively harmful" is replaced with the narrower rule: it is
  harmful as a thing to report on, and necessary as the context a finding is
  judged against.

**The six category checks stay evidence-only.** The findings block is context
for `anomaly_assessments`, not a second source of evidence for `checks`. The
prompt says so explicitly: a fee demand must not push `Reputation` red, and a
finding the results account for must not push `Similar Offers` green. A category
status is still decided only by what a retrieved result says about the employer.
Without this rule, adding the findings to the same prompt would reopen exactly
the failure the original exclusion was written to prevent.

The model is told to weigh the assessed findings in its `risk_level`:

- A finding an employer-specific source accounts for may **lower** the level. A
  medical-test fee the employer's own material names is not the same posting as
  a fee with no account, and the level should say so.
- A finding a source contradicts is a strong signal and may raise the level.
- A finding that is amber — no source, a failed search, a general page, or no
  assessment — never lowers the level. Absence is not evidence in the reader's
  favour, and a general practice page is not evidence about this employer.
- A stale assessment lowers only by accounting for the finding it is attached to.
  It is not a clean record for the employer and must not be read as one.

This is a deliberate difference from the arithmetic asymmetry in
`docs/decisions/scoring-model.md`: that rule kept a clean employer record from
subtracting from a posting score. Here the stale assessment is about the posting's
own finding, confirmed by the employer, so it is allowed to move the level. The
decision record needs an amendment saying so.

### The parser

`_read_verify_output` gains validation for the new array:

- Reject non-objects, missing/blank `finding`, and unknown `status`.
- Keep the first assessment for an index; log and drop duplicates.
- Drop indices outside `1..len(req.anomalies)`.
- Bind `source_url` to the retrieved set, reusing `_bind_to_retrieved`'s
  canonicalisation rule.
- Demote `stale`/`red` without a bound source to `yellow`.
- Log how many assessments were expected and how many survived, in the same
  spirit as the existing missing-categories warning.

The labeled-text fallback cannot carry this array. It returns no assessments,
so every anomaly becomes amber "not checked". That is a declared degradation,
not a silent empty result, and it matches how the fallback already returns no
`risk_level` and no `assessment_reason`.

---

## 8. States and failure states

The card is rendered whenever the scan has at least one anomaly. There is no
waiting condition that hides it. The assessment comes from the first applicable
source:

| Situation | Card state |
|---|---|
| Verification is in flight for this anomaly | `Checking` chip, neutral card, and a confirming box under the quote with a loading ring. |
| Verification returned an assessment for this anomaly | That assessment: stale/red/amber strip and the severity from §5. |
| No employer was named, so verification never ran | amber "Not checked — this post names no employer, so there was nothing to search. Shown so you notice it." |
| Verification failed or the request aborted | amber "Not checked — the employer search did not finish." |
| Verification ran, but this anomaly got no assessment | amber "Not checked — no evidence assessment was recorded for this finding." |
| There were more findings than one verification can carry | amber "Not checked — there were more findings than one search can check. Shown so you notice it." |
| A stored scan from before this feature | amber "Not checked — this reading was saved before findings were checked against evidence." |

No waiting state asserts a severity. No failure state is stale, and no failure
state says the anomaly is disproven.

**The confirming box is a claim that a check is running, so it appears only
when one is.** It is tied to the verify request for that anomaly, not to a
timer. If verification is not going to run — no employer, no company name, a
previous failure restored from history — the card shows the amber note without
ever showing the ring.

The count in the section heading is the number of detected anomalies. It is true
while the checks run and does not claim they were confirmed.

---

## 9. UI

### The anomaly card

`AnomalyCards` keeps its current card structure: severity chip, rule code,
title, description, quote well. The chip is now a display state from §5, not
`anomaly.severity` directly. `Checking` uses a neutral outline chip; `Stale`
uses a grey chip; `Unconfirmed` uses the caution chip; red keeps the existing
severity chip. A stale card stays fully readable but its chip and evidence strip
are grey; the card body is not faded, because the quote and the source are still
what the reader checks.

#### While checking

```
[ Checking ]  FEE-01
Asks applicants to pay a processing fee
The post asks for a 500 peso fee before work.
┌──────────────────────────────────────────┐
│ "a refundable 500 peso processing fee"   │
└──────────────────────────────────────────┘
┌──────────────────────────────────────────┐
│ (ring) Confirming this finding against   │
│        public sources…                   │
└──────────────────────────────────────────┘
```

- The chip is neutral, with no severity colour anywhere on the card.
- The box sits where the evidence strip will sit. It is a container, not a
  second `tactile-card`; the card already has the hard shadow.
- The ring is a small circular spinner, `aria-hidden`. The box has
  `role="status"` and `aria-busy="true"`, so a screen reader hears that the
  check is running without hearing a severity.
- The sentence is plain: "Confirming this finding against public sources…". It
  does not name a query, a source, or a probability. It says only what is
  happening.
- The quote well stays, because it is the posting's own words and needs no
  verification.

#### After it settles

```
[ Stale ]  FEE-01
Asks applicants to pay a processing fee
The post asks for a 500 peso fee before work.
┌──────────────────────────────────────────┐
│ "a refundable 500 peso processing fee"   │
└──────────────────────────────────────────┘
[icon] No longer a concern
The employer's careers page states that a 500 peso medical
examination is paid before deployment.
↗ Example Logistics - Careers
```

- Grey strip: `chip-stale` / `status-card-stale` vocabulary, built from
  `--color-surface-container-high` and `--color-on-surface-variant`.
- Red strip: `chip-critical` / `status-card-critical`.
- Amber strip: `chip-caution` / `status-card-caution`.
- The strip is a container inside the card, not a second hard shadow.
- The icon follows the strip: a grey check for stale, a red warning for
  contradicted, an amber warning for unconfirmed. The red and amber icons use
  the same shapes as `WhatWeChecked`; the stale icon is grey so it cannot read
  as a green pass.
- Source link markup mirrors `CheckDetail`: `open_in_new`, title or URL, opens
  in a new tab with `rel="noreferrer"`.
- `AnomalyCards` returns `null` when there are no anomalies, as it does today.
  It does not render a zero count.

`ReportPanel` always passes the cards when there are anomalies, with a
`checking` flag derived from `scanResult.verificationLoading`. It must not use
`verificationFailed` as a hiding condition; a failed verification is a reason to
show an amber card, not a reason to hide it. **`checking` must read
`result.verificationLoading`, not the panel's `verifying` prop:** `verifying`
stays true after a failure (it is `loading || verificationFailed`), so reusing
it would leave every card spinning forever on a request that already ended.

### The report skeleton loader

The existing loader around `ScamScanView.tsx:281-299` is replaced. It is a
circular pulse, three lines and "Scanning… N%", and it no longer resembles the
report. The new skeleton copies the order and proportions of the new report in
`jobposts/stitch/01-do-not-proceed.html`, with every content block rendered as a
gray pulsing shape:

1. **Job metadata** — two short bars (timestamp and title) and one longer bar
   (employer). The scanning progress text can sit in the timestamp slot, since
   that is the same line and weight.
2. **Assessment banner** — one tall rounded block with a short headline bar and a
   longer reason bar, matching the banner's padding and radius.
3. **What to do now** — a card with a short heading bar and two or three
   checkbox-and-line rows.
4. **Anomalies** — a heading bar, then two card shapes. Each has a small chip
   bar, a title bar, two body bars, and a quote-well block.
5. **What we checked** — a heading bar and a card with two grouped rows of short
   bars.
6. **Full details** — one button-shaped bar.

Rules:

- Every shape is `bg-surface-container-high` (or the nearest semantic
  container token) with `animate-pulse` and `rounded-md`/`rounded-lg` matching
  the real element. No raw hex, no text placeholders like "Lorem", no invented
  findings, no fake employer name.
- The skeleton says "Scanning…" only in the metadata slot and relies on the
  existing top progress bar for the percentage. It does not repeat a percentage
  inside every block.
- The skeleton is `aria-busy="true"` with an accessible label such as "Reading
  the job post", so it is not a wall of silent shapes.
- The shapes do not use the assessment or severity colours. A gray banner must not
  read as a assessment, and a gray anomaly chip must not read as `Checking` on a
  real card.
- The skeleton yields to the real report as soon as the scan result lands. It is
  only for the initial scan; verification uses the per-card confirming box and
  the existing `WhatWeChecked` loading state, not a second full-page skeleton.
- If the scan fails, the skeleton is replaced by the existing error state. It
  does not pulse forever.

---

## 10. History

- `ScanResult.anomalies` is where the assessments live after verification.
  `applyResult` merges the assessed list and writes it to history, so a reopened
  scan shows the same assessments.
- `restoreScanResult` keeps assessments and `anomalyAssessmentRun` untouched.
- A stored scan without assessments shows the amber "saved before this was
  checked" note. It does not invent a assessment.
- The existing `verificationLoading` / `verificationError` promotion in
  `restoreScanResult` is unchanged. A job saved mid-verification still restores
  as "could not be completed", and its anomalies show amber.

---

## 11. Guardrails

- **The assessment cannot outrun the source.** Stale and red require a URL that was
  actually retrieved. An unbound citation demotes the assessment to amber, exactly
  as an unbacked `red` check is demoted today.
- **No employer named means no assessment, and the card says so.** It does not
  reuse the absence of a company as a finding about the posting.
- **A stale or red sentence is shown only with its source.** The source is the
  reader's check on the sentence. A yellow sentence may stand alone because it
  describes what the results did not establish, which has no source by
  construction.
- **The model does not rewrite the anomaly.** The card's title, description and
  quote remain the scan's. The assessment is a separate sentence, so the scan's
  wording cannot be quietly upgraded by the verify stage.
- **No severity before the assessment.** `Checking` is the only state the card may
  show while the check is in flight. The scan's severity is sent to the backend
  as context and is not painted on the card until the check settles.
- **No new score in the client.** The risk level and score remain what the
  verify model emitted. The assessment does not compute or adjust a number. The
  chip mapping is presentation, not scoring.
- **The section is present from the start, but it does not assert a result.**
  The heading and the cards appear with the scan, because detection is done. The
  assessment and severity wait for the check.

---

## 12. What is left to the builder

- Exact Tailwind composition for the strip and the confirming box, using the
  existing semantic tokens and the container/button split. No raw hex, no second
  hard shadow.
- The `Checking` / `Stale` / `Unconfirmed` chip variants, and the helper that
  derives the display state from `verificationLoading` and the assessment.
- Exact prompt wording, so long as it carries the rules in §7 and stays in step
  with the fallback.
- Whether the job-summary excerpt cap is a new constant or reuses an existing
  one; the cap itself is required.
- The parser's internal shape (a small dataclass rather than an ever-growing
  tuple is reasonable, but not required).
- Test names and fixture layout.
- Whether the amber note for a missing assessment is derived in the hook or in
  the card, so long as all seven rows in §8 have exactly one source of truth.
- The exact skeleton shapes and spacing, within the rules in §9. The structure
  is fixed; the pixel values are not.

---

## 13. Decisions

### 13.1 What kind of source can mark a finding stale? — employer-specific

Resolved: `stale` requires a result **about this employer**. A general page
about the practice is not enough, and the finding stays amber.

The same-entity rule the verification categories already use applies here. A
general page can make a fee look ordinary in the abstract; it cannot say that
this employer charges it, and a stale card next to a named employer would read
as the second claim. The prompt says so explicitly, and the fixture set needs a
case where the only support is a general page and the assessment is amber.

### 13.2 May a stale finding lower the risk level? — yes

Resolved: yes, when the source accounts for the finding and the source is about
this employer. A fee the employer's own material names as a medical-test fee can
stop reading as high risk. Amber never lowers, and a stale assessment does not
amount to a clean record for the employer.

This is recorded in §7 as a deliberate difference from the arithmetic asymmetry
in `docs/decisions/scoring-model.md`, and that decision record gets an
amendment when the change ships.

### 13.3 May the card be visible before the assessment? — yes, with no severity

Resolved: the card shows immediately with a neutral `Checking` chip and a
confirming box. The alternative — hide the cards until verification settles —
left the panel empty and then popping, and hid that the scan had found anything
at all. The severity is what waits, not the finding.

### 13.4 Does the severity come from the evidence? — yes

Resolved: `stale → Stale` (grey), `red → the scan's severity`, `amber →
Unconfirmed`, waiting → `Checking`. The mapping is derived in the client from
the assessment, so it cannot disagree with the strip. The verify model does not
emit a second severity.

"Amber is the warning sign of unconfirmed" is the rule behind `Unconfirmed`; it
is not a soft `Critical`, and it does not reuse the scan's colour. Grey is the
rule behind `Stale`: the finding is retired, not praised.

### 13.5 The skeleton loader — mirror the new report

Resolved: replace the old circular-pulse-and-lines loader in `ScamScanView` with
a gray pulsing skeleton that copies the order and proportions of the new report
in `jobposts/stitch/01-do-not-proceed.html`. Details in §9. It is the initial
scan's loader only; verification keeps the per-card confirming box and the
existing `WhatWeChecked` loading state.

---

## 14. Implementation notes (2026-10-20)

- `AnomalyAssessment.index` is kept as an optional field on the client type.
  It is only meaningful at the API boundary, where `useScanSession` maps it
  through the capped selection back to the original finding. An assessment
  attached to an `Anomaly` no longer relies on it as identity.
- The backend drops an assessment with a blank `finding`, as §7 requires, and
  logs the missing indices when the model returns fewer assessments than
  findings. The card supplies its own amber note for a missing one.
- The card repeats the unbacked-`stale`/`red` demotion as a last guard. The
  backend is the control; the card is the last place a retired finding could be
  rendered without the source that retires it.
- The skeleton puts the progress line in the metadata slot, where the scan time
  would sit, and keeps it out of the `aria-hidden` shapes so the percentage is
  announced.
- The "too many findings" amber note is only synthesized when the verify check
  actually ran (`anomalyAssessmentRun`). A failed lookup or a pre-feature scan
  gets its own note instead of a false claim about the cap.
- The six category checks were not touched. `WhatWeChecked` and `FullDetails`
  still read only `verificationResult.items`.


