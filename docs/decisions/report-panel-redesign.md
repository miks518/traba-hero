# Decision record — the report panel redesign

`jobposts/Job Post Scan Report (updated1).html` is the **architectural foundation** for
the panel that replaces the score-and-gauge UI.

**Treat it as structure, not content.** The layout, the section order, the tone
treatment and the token usage are the design. The copy and the specific items in it are
placeholders.

> **Current state lives in `docs/architecture.md`.** The "settled" list below records
> what the redesign settled at the time. Several pieces of the visual source — the
> coverage count, the highlighted span inside a quotation, the "Do not share" chips and
> the report control — were later rejected as unsupportable and are listed as absent
> there. Do not treat this list as a build checklist.

The slot-by-slot contract, the migration map, the state matrix and the build sequence
are in `docs/superpowers/specs/2026-10-17-report-panel-architecture.md`. **Read that
before building any of this.** This record holds only the decisions.

---

## What is settled and must be preserved

- **The assessment is a short instruction to the reader plus a one-line reason**, not a
  number or a level word.
- **Evidence sits in a "Why we think so" block that quotes the posting** and highlights
  the quoted span.
- **Checks are split into *Verified* and *Could not verify***, and the second carries its
  reason.
- **A coverage count ("13 of 14 done") is a first-class figure.**
- **"Do not share" / "Hold back until verified" gates the reader's next action.**
- **Findings sit in a disclosure that says minor ones are inside.**

## The design system was read properly

Semantic tokens, `tactile-card` for containers, `tactile-btn-accent` compound selectors
for buttons, zero-blur hard shadows with the 6px→2px press, Hanken Grotesk + Inter.

**Severity comes from tone containers rather than a saturated banner, so a clean result
looks calm.** Keep all of that.

---

## Assessment phrases are authored, not generated

Four `ScanRiskLevel` values, four reviewed strings, looked up — never written by the
model. Three reasons:

1. **It cannot drift between runs.** A generated phrase would be a fresh variance source
   on every scan, and Phase 6.2 measures assessment stability.
2. **It makes phrase stability trivially 100%**, so the measured quantity is level
   stability — a better thing to measure, since a phrase is not comparable across two
   postings in any case.
3. **It keeps the libel guardrail in code**, where a model-written headline has no
   acceptable failure rate.

**Three shapes, not four.** `low` and `moderate` are both "proceed, with something to
check" and should read as a family. Designing eight distinct phrases for four levels
would make the panel look more precise than the evidence is.

---

## Its furniture is not its architecture

The codes in the HTML (`EMAIL_MISMATCH`, `PAY_ABOVE_MARKET`, `NEW_DOMAIN`,
`CHAT_ONLY_INTERVIEW`) are a generic job-scam checklist, **not** the taxonomy in
`docs/superpowers/specs/2026-10-17-anomaly-code-set.md`.

- `EMAIL_MISMATCH` is the free-email-domain finding this project has fixed three times and
  has a dedicated test against.
- `PAY_ABOVE_MARKET` is a non-finding that the prompt forbids.
- `NEW_DOMAIN` is a verification item, not a posting anomaly.

**A non-finding inside a count of findings makes the count a lie**, and the count is what
Phase 6.3 measures.

"What we checked" also lists checks that were never built — scam watchlists, employee
reviews, text-copy detection, WHOIS domain age. **A line in that list has to be a check
that actually ran**, or the coverage count is a false claim.

---

## Two slots have no possible source and must not be built yet

- **"posted 2 days ago on a job board"** — the extension screenshots a region of a page
  and cannot know where the posting came from. Inferring it would be the same move as
  synthesising a score the system never measured.
- **The report control's target** — for the same reason there is nothing to report the
  post *to*.

---

## A control in the design has no implementation

**"Was this accurate?" is retained by decision but cannot ship without somewhere to put
the answer; there is no database. Do not ship it as a live button.**

Full reasoning, the three compatible options, and the three things to get right when it
is built survive only in the "Reader feedback capture" entry of the deprecated
`UNFINISHED-WORK.md` — that file is not maintained, so treat it as an archive.

---

## Anomaly assessments are not severities, and the cards do not wait

The finding card is present from the moment the scan lands and is never hidden while
verification runs. The scan's severity is input to the evidence check, not the chip the
reader sees first.

| Card state | When | What the reader sees |
|---|---|---|
| Checking | The verify request is in flight | Neutral `Checking` chip, no severity colour, a confirming box with a ring |
| Stale | A retrieved source about this employer accounts for the finding | Grey `Stale` chip and grey strip, the source linked |
| Contradicted | A retrieved source states something different | Red strip, the scan's severity chip, the source linked |
| Unconfirmed | No employer, a failed lookup, no assessment, or results that did not settle it | Amber `Unconfirmed` chip and amber strip |

`Stale` is grey, not green. A retired finding is not a clean employer record, and green
is the six category checks' pass colour. The verify model does not emit a second
severity: the client derives the chip from the assessment, so the chip and the strip cannot
disagree.

**No finding is dropped.** The omitted cards from the 20-finding request cap stay on
screen with an amber note, and the section heading still says **Anomalies detected** and
counts the cards shown. A saved scan from before the check, a scan with no employer, and a
failed lookup each get their own amber sentence rather than a spinner or an invented
`Stale`.

The initial-scan loader is a report skeleton, not the old circular pulse. It mirrors the
panel's slot order with grey `animate-pulse` shapes, uses no assessment colour, and yields to
the real panel as soon as the scan lands. It does not draw the unbuilt controls.

---

## Promotion is restated, not deleted

The current scheme reorders a **pair of sibling groups** on a high or critical score. The
new design has a **single fixed order** with the assessment and actions already on top, so
there is nothing above them to promote.

**Promotion now means the neutral context drops below the findings.** On a dangerous
result, Notes / What we checked / Full details sit under the anomalies rather than above
them. A reader who has just been told not to send money does not need the coverage count
in their first viewport.
