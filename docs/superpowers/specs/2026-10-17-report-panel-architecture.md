# Report Panel — Architecture

**Date:** 2026-10-17
**Status:** architecture only. No component is built. No copy is final.
**Source of the visual design:** `jobposts/Job Post Scan Report (updated1).html`
**Companion:** `2026-10-17-anomaly-code-set.md` (the taxonomy this panel renders)

---

## 0. What this document is

The HTML is the **housing**. The code names, the check names, the employers, the
counts, the quotes in it are **furniture** — placeholders chosen to fill a layout,
carrying none of the context this system has actually accumulated.

This document therefore specifies **slots and contracts**: the section stack, what
each slot binds to, and — the part that matters — **which of those bindings do not
exist yet**. Nothing here is copy. Where a slot needs authored text, it says
"authored" and stops, because the wording is a separate pass.

Every binding is marked:

| Mark | Meaning |
|---|---|
| **EXISTS** | A field is already on the wire. |
| **DERIVED** | Computable from what exists, with no backend change. |
| **NEEDS FIELD** | A new field, or a changed one. Listed in §4. |

---

## 1. The section stack

Fixed order, top to bottom. This ordering *is* the design; the visual treatment of
each slot is already settled in the HTML and is not re-litigated here.

| # | Slot | Purpose | Notes |
|---|---|---|---|
| 0 | App chrome | Trabahero, History, Settings | Exists today |
| 1 | Scan meta | When this was scanned | `ScannedJob.timestamp` |
| 2 | Subject line | Title, employer, where and when it was posted | §2.1 — **the "posted 2 days ago on a job board" half has no source** |
| 3 | **Assessment block** | Tone container: eyebrow, headline, one-line reason | §3 |
| 4 | **Action block** | What to do now + what not to share + report control | §4 |
| 5 | **Anomalies** | Count, then one card per finding | §5 |
| 6 | **Notes** | Non-findings | §6 |
| 7 | **What we checked** | Coverage count, Verified, Could not verify | §7 |
| 8 | Full details | Disclosure holding everything minor, with sources | §8 |
| 9 | Reader feedback | "Was this accurate?" | §9 — **not buildable, see `UNFINISHED-WORK.md`** |
| 10 | Footer | Disclaimer, ruleset version, scan id | §10 |

Slots 5, 6, 7 and 8 are **conditionally rendered** — see §11. Their absence is
meaningful and must not be filled with an empty container.

---

## 2. Contracts, slot by slot

### 2.1 Subject line — title, employer, provenance

| Part | Binds to | Mark |
|---|---|---|
| Job title | derived from `job_summary` / `ScannedJob.title` | **DERIVED** — currently free prose, not a field |
| Employer · `hiring` | `companyName` | **EXISTS** |
| "posted 2 days ago on a job board" | — | **NEEDS FIELD** |

The third part is a **claim about where the posting came from**, which is
something the system genuinely does not know: the extension screenshots a region of
a page and has no idea whether it is a job board, a Facebook group, or a forwarded
message. The HTML infers it from the design of the placeholder. Do not implement
this part until there is a real source — inferring it would be the same move as the
retired score, presenting an unmeasured figure as an observation.

### 3. The assessment block

The most consequential slot, and the one with a real design decision in it.

| Part | Binds to | Mark |
|---|---|---|
| Eyebrow "Assessment" | authored | — |
| Tone container | `riskLevel` → token | **DERIVED** |
| Headline | `riskLevel` → **authored phrase** | **AUTHORED** — see below |
| One-line reason | — | **NEEDS FIELD** |

**The headline is authored, not generated.** `ScanRiskLevel` has exactly four values,
so the panel carries a table of four short imperative phrases and looks the level up.
This is deliberate and load-bearing:

- **It cannot drift between runs.** A generated phrase would be a fresh variance
  source on every scan, and Phase 6.2 measures assessment stability.
- **It makes phrase stability trivially 100%**, so the real measurement is level
  stability. That is a better thing to be measuring — a level is a coarse label, and
  a phrase is not comparable across two postings in any case.
- **It keeps the libel guardrail in code.** Four reviewed strings cannot assert
  something the evidence does not support. A model-written headline can, on any run.

**Three shapes, not four.** The four levels are not four parallel assessments:
`low` and `moderate` are both *"proceed, with something to check"* and should read as
a family, the way `critical` and `high` share a tone container. Designing eight
distinct phrases for four levels would make the panel look more precise than the
evidence is.

**The one-line reason is a genuine gap.** The closest field is
`VerificationResult.report`, which is multi-sentence prose and would fill three lines
of a one-line slot. A short reason needs to be either emitted under its own length
cap by the verification prompt, or composed from the code set. Do not reuse `report`
and let the container grow.

### 4. The action block

| Part | Binds to | Mark |
|---|---|---|
| 2 action lines | **authored**, keyed to assessment family × top code family | — |
| "Do not share" chips | **authored**, keyed to the code families present | — |
| Report control | opens a job board / mailto | **NEEDS** — no target exists |

**The actions are authored, not generated, and must stay that way.** They are
instructions to the reader about their own money and documents. A model writing
"send ₱500 to confirm" is a failure mode with no acceptable frequency.

**The chips are keyed to code family, which is what makes them worth showing.** Under
the money family the gate is bank details and payment; under identity it is ID photos
and credentials. Rendered generically they would be identical for every posting,
which is the same failure as the state-3 "Good habits" list in the HTML — advice that
does not refer to the thing being assessed.

The report control's **target does not exist**: the extension does not know which
board the posting came from (§2.1), so there is nothing to report it *to*. Defer the
control rather than shipping a link to nowhere.

### 5. Anomaly cards

| Part | Binds to | Mark |
|---|---|---|
| "N found" | `anomalies.length` | **EXISTS** |
| Severity chip | `anomalies[].severity` | **EXISTS** |
| Code ID | — | **NEEDS FIELD** |
| Phrase | `anomalies[].flag` | **EXISTS** — but free prose, see below |
| Explanation | `anomalies[].reasoning` | **EXISTS** |
| **Quote block** | — | **NEEDS FIELD** — the big one |

**The quote block is the most load-bearing missing field in the whole panel.** The
credibility of this design rests on quoting the posting and highlighting the span
that decided it. The scan currently returns `flag`, `reasoning` and `severity` — three
free-text fields, none of which is required to be present in the posting. The prompt
has an *observability* rule ("point to it, quoted or closely paraphrased"), but
"closely paraphrased" is exactly what a quote block cannot render.

So the anomaly schema needs a **verbatim span**, and it needs to be enforced: a span
that cannot be found in the posting is not evidence, and the card should degrade to
the explanation alone rather than showing a quotation that was reconstructed. This is
the same shape as `_bind_to_retrieved` on the verification side — a citation bound to
the set it claims to come from.

**`flag` becomes the phrase, and that is a change of job.** It is currently whatever
prose the model chose. Under the code set it becomes a lookup: code → authored phrase.
Authored for the same reason the assessment is authored — the phrase is read by a job
seeker deciding about money, and it must not vary between two runs of the same scan.

### 6. Notes

| Part | Binds to | Mark |
|---|---|---|
| Count | `notes.length` | — |
| Note card | — | **NEEDS** — nothing populates this today |

**Nothing currently produces a note.** The layer is designed and empty.

What belongs here is the class of observation that is real, worth a reader's
attention, and **not a finding** — which resolves a contradiction the project has
been carrying. "The post does not state a salary" and "this is a low pay figure" are
*absence* observations, and absence may never be a finding because it penalises the
posting for a field the poster never intended to be required. They are legitimate
**notes**, provided the label says so — and the note's job is to tell the reader what
is ordinary about it, not to imply it counted against the posting.

This is the correct container for the two items the HTML currently gets wrong
(`PAY_ABOVE_MARKET`, `SALARY_NOT_STATED`), and the reason is not politeness: a
non-finding inside a count of findings makes the count a lie, and the count is what
Phase 6.3 measures.

### 7. What we checked

| Part | Binds to | Mark |
|---|---|---|
| "N of M done" | — | **DERIVED**, see below |
| Verified line | `items[]` where status is supportive | **EXISTS** |
| Could-not-verify line | `items[]` where status is `yellow` | **EXISTS** |
| **Reason it could not verify** | — | **NEEDS FIELD** |

**Three structural points, and the third is the one that matters.**

*First, the mapping is not `green` → Verified.* The six categories have three
statuses. "Contradicted" is not a failed check — it is the check *succeeding* and
finding the opposite of what the posting claimed. Collapsing it into either column
loses the single most important thing verification can produce. Three columns, or
the contradicted ones do not fit.

*Second, the coverage count is derivable.* Numerator is the number of checks that
ran. Denominator must be a **constant the backend owns**, not a number written into
the panel — otherwise the count drifts with whatever the panel happens to render,
which is the failure mode where a "14 checks" claim quietly becomes 6.

*Third, the per-line failure reason has no channel.* `items[].explanation` is the
model's *finding* text — what it concluded, not why it could not conclude anything.
The HTML's "The careers page did not load" / "the registry lookup timed out" are
**retrieval-level** facts, and the only place they can currently live is the
top-level `searchOk` / `searchPartial` / `searchError` triple, which describes the
search as a whole and cannot say which category was thin.

**This slot is also where a false claim is easiest to make.** A line here asserts
that a check was performed. A check that was never built, listed as "could not
verify", is a lie about coverage wearing the honest hat. **The rule: every line in
this list is a check that exists in the backend.** If a check does not exist, it is
not on the list, and the denominator does not include it.

### 8. Full details and sources

Holds what the top-level sections omitted — the minor findings, and the retrieved
evidence with its URLs and retrieval times.

| Part | Binds to | Mark |
|---|---|---|
| Evidence list with links | `VerificationResult.evidence[]` | **EXISTS** |
| Retrieval time per source | — | **NEEDS FIELD** |
| Minor findings | `anomalies[]` below the fold | **DERIVED** |
| Full detail text | `items[].explanation` | **EXISTS** |

The disclosure's own copy in the HTML promises "every finding with its source link
and **retrieval time**". Nothing records a retrieval time — search results carry
`score` and content, not a timestamp. Either emit one or drop the promise; a
disclosure that overstates its own contents is worse than no disclosure.

### 9. Reader feedback

Designed, retained by decision, **not buildable**. No database, no destination for
the answer. Full reasoning and the three things to get right when it is built are in
`UNFINISHED-WORK.md` under "Reader feedback capture".

Architecturally it is one slot with no binding. It must not render as a live control.

### 10. Footer

| Part | Binds to | Mark |
|---|---|---|
| Assessment limitation | authored | — |
| "Ruleset 2026.10.2" | — | **dropped 2026-10-27** — the build constant named something a reader cannot act on or compare; the footer keeps only the reading's own limits |
| "Scan a2f91c" | — | **NEEDS FIELD** — a short id on the response |

The scan id is worth having for a different reason than provenance: it is what lets a
gold-set label, a feedback rating, and a backend log line refer to the same scan. If
feedback is ever captured (§9), it is the join key, and without it a rating cannot be
traced back to what was actually shown.

---

## 4. What has to be added to the backend

Collected, because these are the whole of the gap between this architecture and a
buildable panel. Four new fields on existing objects, no new endpoints.

| # | Field | Object | Why |
|---|---|---|---|
| 1 | `code` | anomaly | The taxonomy ID. The gold set is labeled with it, `§6.3` measures per-code false negatives, and the authored phrase is a lookup on it. |
| 2 | `quote` | anomaly | A verbatim span from the posting. **Enforced** — an unlocatable span degrades the card rather than being rendered as a quotation. |
| 3 | `unavailable_reason` | verification item | Distinguishes "checked, found nothing" from "could not check", per category. |
| 4 | `retrieved_at` | evidence | Makes the disclosure's promise true. |
| 5 | `scan_id` | scan response | Join key for gold set, feedback, and logs. |
| 6 | short assessment reason | verify + offer responses | The one-line slot has no source today. |

**On the anomaly `severity` field.** Under the code set the design in
`2026-10-17-anomaly-code-set.md` §5 removes it, because per-instance severity is
model-judged and therefore a per-run variance source. It survives in the schema only
until that change lands. The severity **chip** in slot 5 is not severity per instance
though — it is the **family**, which is authored and stable. That is a different
field wearing the same name, and it should be renamed rather than reused.

---

## 5. The state matrix

The HTML draws three states. The panel has **eight**, and all eight exist in code
today. A slot that is undefined in a state must be **absent**, not empty.

| State | Assessment | Anomalies | Checks | Special |
|---|---|---|---|---|
| Critical / high, employer verified | instruction | populated | populated | — |
| Moderate | instruction | populated | populated | — |
| Low, checks ran | instruction | usually empty | populated | — |
| **No employer named** | *no assessment* | populated or empty | **absent** | `CompanyNameNeeded`. Dashed border. States what was *not* checked and that it is not a warning about the post. |
| **Verification failed** | posting-only, stated as such | populated | **absent** | Must say the employer was not looked up, not that the employer is clean. |
| **Search partial** | as above | populated | populated, with `queriesFailed` of `queriesIssued` | Coverage is genuinely thinner. Say so. |
| **`VALID: false`** | *no assessment* | **absent** | **absent** | "Nothing To Assess" — names what the product accepts. |
| **Offline** | no call made | **absent** | **absent** | `OfflineBanner`, outside the report. |

Two of these are load-bearing for honesty rather than layout:

**No-employer-named is not a low-risk result.** The posting stage scores 0 when a
posting raises no indicators, and the employer was never checked. Rendering that as
"nothing found" would claim the posting was cleared. The panel must show no assessment
at all, which is what `CompanyNameNeeded` already does.

**A failed verification still promotes.** `shouldElevateEvidence()` gates on
`verificationLoading`, not on verification succeeding — the posting stage's own
findings are real regardless of whether the lookup ran.

---

## 6. Ordering, and how it interacts with evidence promotion

The stack in §1 is fixed, and it is *not* the current `order-*` promotion scheme.
The difference is worth stating because the two will collide.

The current scheme reorders a **pair of sibling groups** — evidence up, analysis down
— on a high or critical score. This design has a **single fixed order**, and the
assessment plus actions already occupy the top. There is nothing above them to promote.

What promotion should mean here instead: **the neutral context drops below the
findings.** On a high or critical result, slots 6, 7 and 8 (Notes, What we checked,
Full details) sit below slot 5 rather than above it. The reader's first question is
"why is this dangerous", and on a clean result the context *is* the answer.

So the existing rule is not deleted, it is restated: **promotion moves context down,
not evidence up.** A reader who has just been told not to send money does not need
the coverage count in their first viewport.

---

## 7. Migration map — what the new architecture replaces

The developer has confirmed the correspondence with the existing panel. **Most of the
new design is the old panel rearranged**, which is the useful finding: this is a layout
and copy change over a working pipeline, not a rebuild. Two slots are genuinely new.

| Old component | Lines | New slot | Action |
|---|---|---|---|
| `RiskGauge.tsx` | 321 | **§3 assessment block** | **Replaced.** The magnitude arc is gone — no number is shown. The gauge's `onShowEvidence` behaviour folds into slot 8's disclosure. |
| — | — | **§3 one-line reason** | **NEW. The only genuinely new content in the panel.** |
| `ScanActions.tsx` | 116 | §4 action block | Regrouped. Rescan / re-capture stay; the "what to share" chips are new and are keyed to code family. |
| `AnomaliesList.tsx` + `AnomalyCard.tsx` | 106 | §5 anomalies | **Same content, new layout** — per-card quote block added. |
| `EvidenceSummary.tsx` | 319 | **§7 what we checked** + **§8 full details** | **Split in two.** See below. |
| `VerificationCard.tsx` | 104 | folded into §7 | The per-category cards become the *Verified* / *Could not verify* lines. |
| `OfferAnalysisCard.tsx` | 57 | §3 + §4, offer variant | The no-employer path keeps its own assessment, action, and check framing. |
| `PostingAnalysis.tsx` | 49 | — | **Removed from the panel.** Its observational rule and word ban survive in the prompt; only the rendering goes. |
| `JobSummary.tsx` | 41 | — | **Removed from the panel, kept in the backend.** `job_summary` stays on the wire because the match tab consumes it. The panel simply stops rendering it. |
| `CompanyNameNeeded.tsx` | 36 | §11 no-employer state | Unchanged. Dashed border, states what was not checked. |
| `InvalidContentError.tsx` | 27 | §11 `VALID: false` state | Unchanged. |

### 7.1 `EvidenceSummary` splits across two slots

This is the one mapping that is not one-to-one, so it is worth being precise.

**§7 "What we checked"** takes the *check* half — the per-category statuses, the search
health, the coverage count. Today `EvidenceSummary` renders those statuses together
with the source list under one heading whose text is derived from state.

**§8 "Full details and sources"** takes the *retrieval* half — the Tavily results, as
the sources list, behind a disclosure.

The reason they must separate is that **they answer different questions and have
opposite honesty requirements.** §7 asserts that checks were performed; §8 shows what
retrieval actually returned. A line in §7 that cannot be backed by a check is a false
claim about coverage, whereas a source list is just what came back.

`EvidenceSummary`'s existing work carries over intact and should not be rewritten:
its heading is **derived from state, never constant** (a search that ran and found
nothing, one that could not run, and one where some queries failed each get their own
heading), and it carries the anomalies as its first child when there is one to lead.
That last point is the FLIP promotion mechanism and it moves with it.

**`search_ok` / `search_partial` / `search_error` map directly onto §7**, and the
partial state is what makes §7's coverage count meaningful rather than decorative.

### 7.2 What actually has to be built

Against the map above, the honest tally:

- **Replaced:** one component (`RiskGauge`, 321 lines) — the largest deletion in the change.
- **Removed from the panel:** two (`PostingAnalysis`, `JobSummary`), 90 lines, both
  still live in the backend.
- **Regrouped:** four.
- **Split:** one.
- **New:** the one-line reason (§3) and the family-keyed share chips (§4).

So the panel work is mostly rearrangement. **The backend work in §4 is the real
critical path**, and none of it is optional — without `code` and `quote` the new
anomaly card and the new assessment line cannot render at all.

---

## 8. Open decisions


1. **Where does the one-line reason come from** — a new capped field from the
   verification prompt, or composed from the code set? The second is reproducible and
   costs no tokens; the first reads better and drifts. This is the one decision that
   most shapes slot 3.
2. **Three or four assessment phrases** — or two, given §3's argument that `low` and
   `moderate` are one family?
3. **Does the Notes layer get populated at all** in the first build, or does it ship
   empty and stay empty until there is something honest to put in it? An empty
   designed slot is a standing invitation to fill it with something form-based.
4. **Denominator ownership** — the backend exposes a `checksPlanned` constant, or the
   panel counts what it rendered? Only the first is honest, per §7.
5. **Does §7 need to know about the promotion reorder?** `EvidenceSummary` currently
   carries the anomalies as its leading child when it is promoted, which is the FLIP
   mechanism. Once the anomalies have their own slot (§5), that leading-child logic has
   nothing to do — the promotion is now a `order-*` value on two sections. Whether the
   child-carrying behaviour is deleted or kept is unresolved.

---

## 9. Build sequence

Ordered by dependency, not by size. Steps 1–3 are backend and can land before any
panel work; step 4 is the panel and is blocked on steps 1–2.

1. **Anomaly `code` + `quote`** (§4 items 1–2). The prompt gains the code enum and a
   verbatim-span requirement; the parser reads both; `Anomaly` gains `code?` and
   `quote?`. *Both optional on read* so stored history keeps rendering.
2. **Short assessment reason** (§4 item 6). Capped field on the verify and offer
   schemas, plus the authored phrase table in the panel.
3. **`unavailable_reason`, `retrieved_at`, `scan_id`** (§4 items 3–5). Independent of
   each other and of 1–2; batch them because each is small.
4. **Panel restructure** — delete `RiskGauge` / `PostingAnalysis` / `JobSummary`,
   reorder, split `EvidenceSummary`, build the assessment block.
5. **Promote restatement** (§6) — context drops below findings.
6. **The four undrawn states** (§11).

Steps 1 and 3 touch the same files, so they will conflict if run in parallel by
different people. Sequenced deliberately.
