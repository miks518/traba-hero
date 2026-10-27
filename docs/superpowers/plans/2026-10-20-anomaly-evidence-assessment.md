# Anomaly Evidence Assessment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The verify stage assesses each scan anomaly against retrieved evidence, and the report shows the finding immediately with a neutral checking state, then a grey `Stale`, red `Contradicted`, or amber `Unconfirmed` assessment.

**Architecture:** Extend `VerifyAnomaly` with `code`/`quote`, add a numbered findings block and eight-key output to the verify prompt, parse `anomaly_assessments` in `_read_verify_output`, and return it on the verify SSE result. On the client, merge assessments into `ScanResult.anomalies`, derive the display chip from the assessment, render a confirming box while `verificationLoading`, and replace the old loader with a grey pulsing report skeleton.

**Tech Stack:** FastAPI/Pydantic backend, React 19 + TypeScript + Tailwind/WXT extension, Vitest + pytest.

**Spec:** `docs/superpowers/specs/2026-10-20-anomaly-evidence-assessment-design.md`

## Global Constraints

- Default test suite stays fully offline. Never call OpenRouter/Tavily without permission.
- Assessment statuses on the anomaly wire are `stale`, `yellow`, `red`. Do not use `green` for anomaly assessments; the six check categories still use green/yellow/red.
- `stale` and `red` require a bound retrieved source. Missing/unbound becomes `yellow`.
- No severity is shown while verification is in flight; `Checking` is not a severity.
- Display severity mapping: `stale → Stale`, `red → scan severity`, `yellow → Unconfirmed`, checking → `Checking`.
- Every anomaly stays visible. No silent drops; >20 anomalies get amber "too many findings" notes on the omitted cards.
- `checking` reads `verificationLoading`, never `verificationFailed`.
- Skeleton uses semantic tokens, grey/pulsing, report order, no fake content.

## Review Focus

- A live scan with no employer: cards must show amber `Unconfirmed` immediately, never a spinner.
- A verification that fails: cards must stop spinning and show amber; do not reuse the sticky `verifying` prop.
- A saved scan from before this feature: no invented `stale`; show amber with an honest "no assessment recorded" note.
- A source URL outside the retrieved set: `stale`/`red` must demote to `yellow`, not render an unbound citation.
- More than 20 anomalies: the verify request must not 422; omitted cards must still render with amber.

---

### Task 1: Backend schema and prompt

**Files:**
- Modify: `backend/app/models/schemas.py`
- Modify: `backend/app/services/scanner/verification_prompt.py`
- Modify: `backend/VERIFY_PROMPT.md`

**Interfaces:**
- Produces: `AnomalyAssessment` Pydantic model with `index`, `status`, `finding`, `source_title`, `source_url`.
- Produces: `VerifyAnomaly.code: str`, `VerifyAnomaly.quote: str`.
- Produces: `MAX_VERIFY_ANOMALY_CODE = 100`.
- Produces: `_build_verify_prompt(req, search_context)` includes the numbered findings block, a bounded `job_summary` excerpt, and the eight-key rule.

- [x] **Step 1: Add the schema**

```python
class AnomalyAssessment(BaseModel):
    index: int
    status: str  # "stale" | "yellow" | "red"
    finding: str = ""
    source_title: str = ""
    source_url: str = ""
```

- [x] **Step 2: Extend `VerifyAnomaly`**

```python
code: str = Field(default="", max_length=MAX_VERIFY_ANOMALY_CODE)
quote: str = Field(default="", max_length=MAX_VERIFY_ANOMALY_TEXT)
```

- [x] **Step 3: Extend `VERIFY_RESPONSE_SCHEMA`**

Add `anomaly_assessments` as an array of objects with `index` (integer), `status` (`stale`/`yellow`/`red`), `finding`, `source_title`, `source_url`, all required, no extras. Add it to the top-level `required`.

- [x] **Step 4: Add the findings block to `_build_verify_prompt`**

Number the anomalies 1-based, include flag, reasoning, severity, code, quote. Label the block as untrusted posting claims, not facts about the employer, and tell the model not to let it decide the six categories. Add a `job_summary` excerpt capped at 4,000 characters.

- [x] **Step 5: Update both prompts**

`VERIFY_PROMPT.md` and `_FALLBACK_VERIFY_PROMPT`: eight keys; `anomaly_assessments` shape; the stale/red/yellow rules; employer-specific stale; general page is amber; absence never red; source required for stale/red; one assessment per number; categories stay evidence-only; stale may lower the level only when employer-specific, amber never lowers.

- [x] **Step 6: Check the prompt tests fail for the right reason**

Run: `python -m pytest tests/test_verify.py tests/test_verify_unschemaed.py -q`
Expected: the old "excludes anomalies" tests fail, and the schema/prompt key test passes once the key is named.

---

### Task 2: Backend parser and stream

**Files:**
- Modify: `backend/app/services/scanner/verification_flow.py`
- Test: `backend/tests/test_anomaly_assessment.py`

**Interfaces:**
- Produces: `_read_verify_output(text, allowed_urls=frozenset(), anomaly_count=0)` returns a 9-tuple ending in `list[AnomalyAssessment]`.
- Produces: every verify result event carries `anomaly_assessments`, including `[]` on the no-company and labeled-text paths.

- [x] **Step 1: Write failing tests**

Cover: a stale assessment with a bound URL survives; a stale without a URL becomes yellow; an out-of-range index is dropped; a duplicate index keeps the first; a missing key returns `[]`; the no-company event has `anomaly_assessments: []`; the text fallback returns `[]`.

- [x] **Step 2: Implement `_read_anomaly_assessments(payload, anomaly_count, allowed_urls)`**

Validate index, status, finding; drop duplicates and out-of-range; bind URLs with `_canonical_url`; demote unbacked stale/red to yellow; clear source on unbound URLs.

- [x] **Step 3: Append the assessments to `_read_verify_output`**

JSON path parses them; text path returns `[]`.

- [x] **Step 4: Pass `len(req.anomalies)` and return `anomaly_assessments`**

In `verification_event_stream`, pass the count and add `"anomaly_assessments": [a.model_dump() for a in assessments]` to both result events.

- [x] **Step 5: Run**

`python -m pytest tests/test_anomaly_assessment.py tests/test_verify.py tests/test_verify_fallback.py tests/test_verify_unschemaed.py tests/test_citation_binding.py -q`

---

### Task 3: Frontend types and session merge

**Files:**
- Modify: `entrypoints/sidepanel/types/index.ts`
- Modify: `entrypoints/sidepanel/lib/api.ts`
- Modify: `entrypoints/sidepanel/hooks/useScanSession.ts`

**Interfaces:**
- Produces: `AnomalyAssessment` and `Anomaly.assessment`.
- Produces: `ScanResult.anomalyAssessmentRun?: boolean`.
- Produces: `VerifyContext.anomalies` entries carry `code` and `quote`.
- Produces: `startVerification` sends at most 20 anomalies by severity and maps assessments back to the original list.

- [x] **Step 1: Add types**

```ts
export interface AnomalyAssessment {
  status: 'stale' | 'yellow' | 'red';
  finding: string;
  sourceTitle?: string;
  sourceUrl?: string;
}
```

Add `assessment?: AnomalyAssessment` to `Anomaly`, `anomalyAssessments?: AnomalyAssessment[]` and `anomalyAssessmentRun?: boolean` to `VerificationResult`, and `anomalyAssessmentRun?: boolean` to `ScanResult`.

- [x] **Step 2: Map the verify result**

Read `anomaly_assessments`, map snake_case to camelCase, and set `anomalyAssessmentRun` only when the key is an array. Preserve absence versus empty.

- [x] **Step 3: Pass `code`/`quote` into the verify request**

Update `VerifyContext.anomalies` and the `handleScan` call.

- [x] **Step 4: Cap and merge**

In `startVerification`, stable-sort original indices by severity (high, mid, low), take 20, send that sublist, and on the result map `assessment.index - 1` through the selected indices. Omitted indices get a yellow "too many findings" assessment. Set `anomalyAssessmentRun` from the result.

- [x] **Step 5: Run**

`npm run compile`

---

### Task 4: Anomaly card states

**Files:**
- Modify: `entrypoints/sidepanel/components/report/AnomalyCards.tsx`
- Modify: `assets/tailwind.css`
- Modify: `entrypoints/sidepanel/components/report/ReportPanel.tsx`

**Interfaces:**
- Produces: optional props `checking`, `needsCompanyName`, `verificationError`, `assessmentRun`.
- Produces: `.chip-stale` and `.status-card-stale` semantic classes.

- [x] **Step 1: Add the stale classes**

Use `--color-surface-container-high`, `--color-on-surface-variant`, and `--color-outline-variant` in both light and dark blocks.

- [x] **Step 2: Derive the display state**

`checking` first, then the assessment, then the amber fallback reason. `stale → Stale`, `red → scan severity`, `yellow → Unconfirmed`.

- [x] **Step 3: Render the confirming box**

When `checking`: neutral chip, `role="status"`, `aria-busy="true"`, a small `animate-spin` ring, "Confirming this finding against public sources…".

- [x] **Step 4: Render the evidence strip**

Stale: grey check, "No longer a concern", finding, source link. Red: red warning, "Contradicted by a public source", finding, source link. Yellow: amber warning, "Not confirmed", finding, optional source link. Use `rel="noreferrer"` and `open_in_new`.

- [x] **Step 5: Wire `ReportPanel`**

Pass `checking={Boolean(result.verificationLoading)}`, `needsCompanyName`, `verificationError`, `assessmentRun={Boolean(result.anomalyAssessmentRun)}`.

- [x] **Step 6: Run**

`npm run compile`

---

### Task 5: Report skeleton

**Files:**
- Create: `entrypoints/sidepanel/components/report/ReportSkeleton.tsx`
- Modify: `entrypoints/sidepanel/components/report/index.ts`
- Modify: `entrypoints/sidepanel/views/ScamScanView.tsx`

- [x] **Step 1: Build the skeleton**

Mirror the report order: metadata, assessment banner, action card, two anomaly cards, checks card, full-details button. Use `bg-surface-container-high animate-pulse`, semantic spacing, `aria-busy="true"`, and `aria-label="Reading the job post"`. Show "Scanning… N%" in the metadata slot.

- [x] **Step 2: Replace the old loader**

Delete the circular pulse block in `ScamScanView.tsx` and render `<ReportSkeleton progressPercent={progressPercent} />`.

- [x] **Step 3: Run**

`npm run compile`

---

### Task 6: Tests, docs, verification

**Files:**
- Modify: `entrypoints/sidepanel/components/report/AnomalyCards.test.tsx`
- Create: `entrypoints/sidepanel/components/report/ReportSkeleton.test.tsx`
- Modify: `docs/decisions/verification-design.md`
- Modify: `docs/decisions/scoring-model.md`
- Modify: `docs/architecture.md`
- Modify: `docs/decisions/report-panel-redesign.md`

- [x] **Step 1: Add frontend tests**

Checking state shows `Checking` and the ring, no `Critical`; stale shows `Stale` and the source; red shows the scan severity; amber shows `Unconfirmed`; no employer shows amber without a ring; failed verification shows amber without a ring; old scan shows amber; skeleton renders the six regions and no assessment colours.

- [x] **Step 2: Update docs**

Verification design: anomalies now go to verify, and the six checks stay evidence-only. Scoring: stale may lower only with an employer-specific source; amber never lowers. Architecture: the new wire field and display states. Report panel: the checking/stale states and the skeleton.

- [x] **Step 3: Run the full suites**

`cd backend && python -m pytest tests/ -q`
`npm run compile`
`npm test -- --run`

- [ ] **Step 4: Fix failures and re-run**

Do not weaken the offline guards or delete a failing assertion to make the suite green.

**Left open against the scan-prompt findings, not this work.** The full backend suite is
698 passed, 1 skipped, 9 failed. All nine are pre-existing `SYSTEM_PROMPT.md` drift in
`test_anomaly_codes.py` (4) and `test_scan_prompt_file.py` (5); neither the prompt file nor
`prompts.py` was touched here. See the status note at the end.

---

## Status (2026-10-20)

Implemented. `npm run compile` passes; the frontend suite is 32 files / 239 tests; the
targeted backend suite (anomaly assessment, verify, fallback, citation binding, assessment
reason, prompt file) is 192 passed. The full backend suite's only failures are the nine
pre-existing scan-prompt drift findings above. No live provider calls were made and the
default suite stayed offline.

---

## Self-review

- Spec §2/§5/§8/§9/§13 are covered by Tasks 1, 2, 4, 5.
- The "no severity before assessment" rule is Task 4 Step 2/3.
- The "source required" rule is Task 2 Step 2.
- The >20 cap is Task 3 Step 4.
- The failure/no-employer/old-scan states are Task 4 Step 2/5 and Task 6 Step 1.
- The skeleton rules are Task 5.
