# Three Proposals: Framing, Origin Verification, False-Positive Measurement

**Status:** design document, not implemented. Nothing here has been built.
**Date:** 2026-10-07
**Scope:** proposals arising from panel feedback that the "Red Flag" label
attracts attention regardless of severity, that some real postings get flagged
for being merely badly written, and that verification never checks whether a
posting actually comes from the employer it names.

Three separate problems are described here and deliberately kept separate,
because they have different costs, different owners, and different evidence
requirements. Section 3 is measurement work that gates the other two.

---

## 0. Read this first: three distinct problems

| # | Problem | Surface | Wire change | Who decides |
|---|---|---|---|---|
| 1 | Uniform "Red Flags" framing | UI only | No | Frontend |
| 2 | No origin/impersonation check | Prompt + scoring | **Yes** | Methodological |
| 3 | Unmeasured false-positive rate | Test checklist | No | Developer, live |

Proposal 3 is measurement, and it should run first. Proposals 1 and 2 can both
be argued from data once it produces any, and right now they can only be argued
from inspection. Panel feedback is real evidence but it is not a measurement,
and the panel has not seen this code — so what they observed is worth taking
seriously without yet knowing how often it happens.

---

## 1. Proposal 1 — Severity-aware framing

### The defect

`entrypoints/sidepanel/components/scan/RedFlagsList.tsx:19`:

```
Red Flags ({flags.length})
```

rendered as an `<h3>` in `text-error font-bold`, always accompanied by a `flag`
icon (`RedFlagsList.tsx:17`) and, when any flag is `high`, a red `HIGH SEVERITY`
badge (`RedFlagsList.tsx:22-26`). Each card's icon is chosen by severity
(`ScamScanView.tsx:81`), so a `low` flag still renders a flag glyph.

The result: **one low-severity formatting observation and three high-severity
findings are announced with equal force.** The heading asserts "these are red
flags" before the reader has seen a single piece of evidence, and nothing in the
heading's appearance responds to how weak the findings actually were.

`SEVERITY_STYLES` in `RedFlagCard.tsx:9-18` already differentiates per card, so
the information exists in the type. It is the *container* that does not vary.

### Why this matters beyond cosmetics

This is inconsistent with rules the project has already adopted:

- A missing input is not a finding.
- Absence of a result is never red.
- The panel states facts rather than conclusions.

"Red Flag" is a conclusion about the posting, applied as a category label to an
item that may be only an observation. The severity field is doing the honest
work; the heading is overriding it.

### Decision: rename to "Anomaly"

The rename is settled: **`Red Flag` → `Anomaly`.** It is the correct direction
and it is a strict improvement on the current label. Rationale recorded below
so the reasoning survives the change.

"Red Flag" is a conclusion the reader is asked to accept before seeing the
evidence. "Anomaly" is a description: it says this element differs from what is
expected, and stops there. The distinction matters because **an anomaly is not
an accusation.** A posting can be genuinely sloppy — an anomaly — without being
fraudulent, and the label must be capable of holding both.

The rationale, stated for the thesis defence: the system establishes that a
posting *contains something unusual*. It does not establish what that something
*means*. The burden of interpretation stays with the reader, which is the same
allocation the libel guardrail already makes elsewhere — `POSTING ANALYSIS`
states what the posting asks for and is explicitly forbidden from naming it a
scam, and a `red` verification status requires a retrieved source rather than
the model's judgment. "Anomaly" is consistent with those two rules; "Red Flag"
contradicts them.

**Anomaly is the label, not the severity.** These are separate axes and should
not be collapsed. Severity (`low`/`mid`/`high`) still carries the weight in
`risk_calculator.POSTING_SEVERITY_WEIGHTS`, unchanged. Renaming the category
does not change any number the panel displays.

### Where the rename lands, and where it must not

This is a **presentation-layer** change with one wire-format consequence, and
the distinction matters:

**Presentation only — safe to change freely:**

- `RedFlagsList.tsx:19` — the `<h3>` heading text
- `RedFlagsList.tsx:17` — the `flag` icon
- `RedFlagsList.tsx:22-26` — the `HIGH SEVERITY` badge
- `ResumeMatchView.tsx:505` — renders the same heading independently and must
  change with it, or the two panels will disagree about what a finding is

**Wire format — needs care:**

- `ScanApiResponse.red_flags` → `anomalies`, and the parser in
  `scan_result.py` that reads `red_flags` from the model response.

**Prompt — hold for now, with a reason.** `SYSTEM_PROMPT.md:7` and
`prompts.py:33` both use `RED FLAG:` as a *model output line prefix*, and
`prompts.py` refers to "red flags" throughout its field rules. Changing that
prefix is a prompt edit, and prompt edits on this project have a history of
drift between the file and the fallback copy. Two reasons to hold:

1. The label the *reader* sees is what caused the panel feedback. The token
   the *model* emits is invisible to them.
2. The prefix is load-bearing for the parser. `_parse_custom` reads lines
   between `END FLAGS`-style delimiters, and the model has been trained on
   this shape by the prompt itself. Changing it is a behaviour change to
   parsing, not a rename.

If the prompt prefix is renamed later, it is a separate change with its own
tests — not a continuation of the UI rename.

### Still open: does the heading vary by severity?

The rename settles the noun but not the framing defect that motivated
Proposal 1. "Anomalies (3)" in `text-error font-bold` still announces one
low-severity formatting observation with the same force as three
high-severity findings. The severity chip and card border already differ; the
*container* does not.

Options, pending panel input:

**1a. Rename only.** Heading becomes `Anomalies (3)`, appearance unchanged.
Cheapest, fully reversible, addresses the panel's stated complaint.

**1b. Rename plus severity-aware container.** Heading and colour follow the
worst severity present:

| Worst severity present | Heading | Treatment |
|---|---|---|
| `low` | Anomalies (n) | neutral, `text-on-surface` |
| `mid` | Anomalies (n) | amber |
| `high` | Anomalies (n) | error, badge retained |

The noun stays constant — which is the point. The *intensity* varies, so a weak
finding is not announced with the same force as a strong one, without the
label changing meaning. This preserves the severity distinction that
`SEVERITY_STYLES` already encodes per card, at container level.

**1c. Full severity tiering.** Distinct treatments per band. Most work, and
risks the colour-without-reading problem `AGENTS.md` already records: long
blocks of red or amber on a light surface are the hardest thing on the panel to
read.

1b is the recommendation, but it is a judgement call about visual weight rather
than a correctness question, and the panel is better placed to answer it than I
am. **This is the one open question in Proposal 1.**

### Implementation cost

Small. `severity` is already on the `RedFlag` type (`types/index.ts:70`) and
already drives `SEVERITY_STYLES` and `SEVERITY_ICONS`. No scoring change, no
prompt change under the recommended scope.

Two tests reference the concept by name — `ScamScanView.elevate.test.tsx` and
`borderVariants.test.ts` — and would need their assertions checked against the
new label. `borderVariants.test.ts` in particular guards declared colour
variants, so it should not be edited to match whatever class ends up in the
component without checking it still catches the undeclared-variant case.

---

## 2. Proposal 2 — Origin and impersonation

### The gap

The verification prompt asks three questions, all about the **employer**
(`VERIFY_PROMPT.md`):

1. Company Existence
2. Official Registration
3. Reputation

None asks: **does this posting actually come from the employer it names?**

That is the gap a panelist identified, and it is where the most damaging
misfires live. Consider a scammer posting under `"Jollibee Careers"` on a
Facebook page. Verification runs against Jollibee. Jollibee exists, is
registered, has clean reputation. Three green cards render beside a fraudulent
posting.

The checks did not fail. They answered a different question than the reader's.
The reader wants to know whether *this posting* is real. The system is
answering whether *that company* is real, and the two coincide only when the
posting is genuine.

This is the same class of error as verifying an employer for a posting that
names none — a missing input treated as if it were present. Here the input is
present but it is *unverified as an attribution*, and the system proceeds as
though it were established.

### Evidence available without new search providers

The category can be partly answered from signals already retrieved:

**Posting side, no network at all:**

- Does the contact email domain match the employer's own domain? The prompt
  already uses this at `mid` severity — "contact details that do not match the
  named employer" (`prompts.py:55`). It is currently a posting-stage flag, not
  a verification category. A Gmail address for a large named employer is weak
  evidence; for a sole proprietorship it is normal.
- Does the posting name a domain or URL the employer's own site would use?
- Is the named employer large enough to plausibly hire through a channel the
  posting uses? This one needs care — inferring expected hiring channels is
  exactly the kind of assumption the libel guardrail forbids.

**Search side, over results already fetched:**

- Does the posting's claimed source appear in the retrieved results?
- Do the employer's own pages mention a matching vacancy?

### Design questions that must be answered before building

1. **Category name.** `Posting Origin`? `Attribution`? Something that does not
   assert impersonation occurred — "Origin" states a fact, "Impersonation"
   states a conclusion.
2. **Scoring weight.** This is a fourth category. Its weight changes
   `risk_calculator.py`'s category table, and that table currently normalises
   to 100 across three categories. Adding a fourth re-normalises all three
   existing weights — a live decision with the same tension discussed in
   `SCORING-SOURCES.md` §8, where the existing weights are nearly flat and
   adding a differentiated fourth category would make that visible.
3. **Relationship to the existing `mid` flag.** "Contact details do not match
   the named employer" is *already* a posting-stage flag. Making it also a
   verification category risks counting the same observation twice — once at
   posting stage, once as a verification penalty. The additive model would then
   double-count it. Either it moves, or the overlap has to be documented.
4. **Guardrail interaction.** A `red` here requires a retrieved result that
   states the posting is not from the employer. Inference from "this domain
   isn't theirs" is exactly the reasoning the prompt bans.

Point 3 is the one most likely to be got wrong, and it is the reason this
should not be built before Proposal 3 has run.

### Implementation cost

Substantial. New category in `VERIFY_RESPONSE_SCHEMA`, prompt rules in
`VERIFY_PROMPT.md`, a scoring-weight decision, a frontend card, and the
double-counting question resolved. This is architectural work, not a patch.

---

## 3. Proposal 3 — Measuring the false-positive rate

This is the one that should happen first. It needs no code.

### The gap

Nothing in the repository measures how often the model flags a genuine posting.
`UNFINISHED-WORK.md` carries a seven-row live checklist, but no row covers a
genuine posting that is merely badly written — which is exactly the case the
panel reported. Row 2 covers a legitimate posting using a Gmail address and
expects **zero** flags, which is adjacent but not the same thing: that row is
about a contact-method signal, not about sloppy writing.

Without a measurement, "the flags misfire" is an anecdote. It may well be
correct and frequent; it may be correct and rare. The remedy differs.

### Proposed checklist additions

Additions to the live table in `UNFINISHED-WORK.md`, to be run by the developer
because they require live provider calls. The shared key is **not** calling
OpenRouter or Tavily without explicit permission — the key is shared and
hitting the 24-hour limit blocks the developer's own testing.

**Row 8 — genuine but badly written.** A real employer, real role, real
application channel. Formatting is poor, the description is vague, the title is
generic, there is no logo. This is the panel's case.

- Expected: **zero or at most one `low`.** Not a mid, not a high.
- Note the tension: `SYSTEM_PROMPT.md` currently allows `low` for "generic
  job titles, informal formatting, or minor inconsistencies" — so *some* low
  flags are sanctioned by design. The question is whether one is emitted, and
  whether it reads as an alarm.

**Row 9 — genuine with one low flag present.** For contrast with row 8, to
separate "flags a sloppy posting" from "flags any posting."

- Expected: low-severity flags only, correctly reasoned, framed as weak.

**Row 10 — impersonation.** A posting that claims to be from a real, large,
well-known Philippine employer but whose contact details do not match that
employer's domain.

- Expected today: the employer verification will likely return green/green/green,
  because all three categories are about the real employer.
- Expected after Proposal 2: a distinct finding.
- This row is the *before* measurement for Proposal 2. Run it first.

**Row 11 — genuine, well-written, clean.** The negative control.

- Expected: zero flags. Confirms the detector is not simply flag-strict.

### Also worth recording

For each row, the score and level alongside the flags. Proposal 1's severity
tiers and the 13%-within-3-points-of-a-band-edge figure in
`SCORING-SOURCES.md` §5 interact: a row whose flags land near a band edge is
also a row whose *level* is fragile. Both numbers are needed to tell a
framing problem from a scoring problem.

### What this costs

Roughly ten to fifteen live requests. Developer-run only. No code, no test
changes, no CI impact.

---

## 4. Recommended order

1. **Run Proposal 3.** Rows 8–11. No code. Produces the first real measurement
   of the misfire rate and a before-picture for impersonation.
2. **Decide Proposal 1** on that evidence. The rename to `Anomaly` is settled
   and needs no further data. What the checklist informs is only whether the
   container varies by severity (1a) or not (1b) — a judgement about visual
   weight, not correctness.
3. **Design Proposal 2** with the double-counting question answered first. Only
   then write anything.

Proposal 2 should not be built before Proposal 3 runs, because the
double-counting interaction with the existing `mid` flag cannot be resolved
without knowing how often that flag actually fires.

---

## 5. Not included

- **Empirical refitting of severity weights.** Settled separately: the AHP
  derivation in `SCORING-SOURCES.md` §1 stands, and fitting to labelled data
  would reverse the asymmetry rule deliberately chosen in
  `risk_calculator._combine_scores`.
- **Constrained follow-up search.** Discussed separately and still unbuilt.
  The documented costs are in the conversation history: 3–7× credit
  consumption and a new prompt-injection surface where a hostile page can
  influence the model's next query.
- **Any backend or frontend code.** This document proposes; it does not build.

---

## 6. The burden-of-proof principle behind the rename

The rename was decided on reasoning that belongs in the thesis defence, so it is
recorded here rather than left implicit.

**The principle.** A finding must be preceded by evidence for that finding, and
the finding must not assert more than the evidence supports. Stated as a
constraint on this system: the panel is entitled to distinguish *what the posting
contains* from *what that means*, and the second is the reader's to draw, not
the tool's.

This is not a metaphor borrowed from outside the project. It is already the rule
the rest of the system runs on, in four places arrived at independently:

| Rule | Where | Form |
|---|---|---|
| A check that did not happen is reported as such | `SearchOutcome.ok` / `.results` independence | `ok=False` and "no results" are different states |
| Absence is never `red` | `VERIFY_PROMPT.md` STATUS RULES | `red` requires a retrieved source that states the negative |
| State facts, not conclusions | `POSTING ANALYSIS` field rule | bans `scam`, `legitimate`, `suspicious`, `genuine`, `fraudulent`, `honest` |
| A missing input is not a finding | `CompanyNameNeeded` | dashed border, not a result container |

**Where "Red Flag" broke it.** The word is a conclusion, delivered as a category
label, before the reader reaches any evidence. Every item in the section is
announced as damning by the heading alone — including a `low`-severity
observation about formatting that would be unremarkable in isolation. The
evidence was there; the label asserted a conclusion the evidence might not
support.

**Where "Anomaly" fixes it.** An anomaly is a *description of divergence from
expectation*. It carries no claim about cause, intent, or consequence. A posting
with informal formatting is anomalous and entirely legitimate. Both readings
remain available to the reader, and the tool has taken a position on neither.

**The line this draws.** The system may report that a posting asks the applicant
for a processing fee, because that is a fact about the text. It may not report
that the posting is a scam, because that is a conclusion requiring a standard of
proof this panel does not meet. `Anomaly` names the first kind of statement.

**One honest limit.** A neutral label reduces priming; it does not correct a
wrong finding. If the model flags a genuine posting for being sloppy, the
heading made that error louder, but the error is upstream in detection.
Proposal 3 measures whether it happens and how often. **The rename is not a fix
for over-flagging and should not be presented to the panel as one** — it fixes
the label asserting more than the evidence carries.

---

## 7. Open items for the panel

1. Does the container vary by severity, or only the noun? The rename settles the
   noun; this decides between 1a and 1b. A judgement about visual weight, not a
   correctness question.
2. Should the panel show a posting's origin check even when the employer checks
   all pass? (Proposal 2's most likely panel objection: three green cards create
   a confidence that an origin check is meant to qualify.)
3. Is the 7-row checklist extended, or replaced? The existing rows cover scam
   detection; Proposal 3's rows cover false positives — a different axis that
   may warrant its own table.
4. Should `Anomaly` replace `red_flags` on the wire, or stay presentation-only
   for now? The recommended split is in §1: rename the presentation layer,
   hold the prompt prefix.