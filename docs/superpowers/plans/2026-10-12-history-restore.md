# Reopening a Scan from Job History — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every scan in job history an Open button that loads that posting's saved scan back into the Scan tab, marked in the app bar with the date it was taken.

**Architecture:** `ScannedJob.scanResult` already stores the complete `ScanResult`, so this adds no storage work beyond two small fields. A pure `restoreScanResult` maps a stored result into a displayable one; `ScamScanView` takes a `restoredJob` prop keyed on a `token` so re-opening the same job re-applies. `App` owns one piece of state and passes it down plus an `onOpenJob` callback that also flips the tab.

**Tech Stack:** React 19, TypeScript, WXT, Tailwind v4, Vitest + `@testing-library/react` with happy-dom.

**Spec:** `docs/superpowers/specs/2026-10-12-history-restore-design.md`

## Global Constraints

- **Never call OpenRouter or Tavily.** The AI key is shared and a limit hit blocks the developer's own testing for 24 hours. This feature makes no backend changes, but `backend/tests/` must stay fully offline.
- **Screenshots are never persisted.** The manifest requests `storage` but not `unlimitedStorage`, so `chrome.storage.local` caps at 5MB and Chrome fails writes *silently*. A restored scan shows no thumbnails. This is a stated loss, not a bug to fix later.
- **No migration.** Jobs saved before this change reopen without `attributes`. The build is in development; do not add a path for it.
- **Never clear a stored error flag on restore.** `verificationError` is what happened; erasing it hides a real outcome. Only the two `*Loading` flags are cleared, because a stored `true` there means "was in flight when saved" and would otherwise render a spinner that never stops.
- **Copy is for a Filipino job seeker.** No jargon, no registry vocabulary. "Saved from job history" and a date — not "cached scan record".
- **Tactile treatment.** Containers get `tactile-card` and no press; buttons get a `tactile-btn-*` class **and** the press (shadow shortens, element moves `translateY(4px)`). Never give a container `cursor: pointer`, `:active`, or hover state. The Open button is a button.
- **Translucent token variants must be declared by hand** in `@layer components` in `assets/tailwind.css`; a class like `border-outline-variant/30` that is not declared does nothing and fails silently. `borderVariants.test.ts` enforces this.
- **Test names explain why, in a comment above the assertion**, when the behaviour is not obvious. This codebase documents the reason for nearly every non-trivial test and the standard is not to drop.

## Review Focus

Five things the spec implies but no task's happy path exercises. Each is pinned by a named test in the task that owns the code.

1. **The same job opened twice in a row** must re-apply. Keying the effect on the job object fires once and then never again, so the second click does nothing.
2. **A job scanned but never verified** was saved with `verificationLoading: true`. Restored as-is, it shows "Verifying…" forever.
3. **A job whose verification genuinely failed** must still show the failure on reopen. Clearing `verificationError` to make the panel look tidy hides a real outcome.
4. **Open is pressed while the Scan tab is hidden** (`display:none` on its wrapper). Layout is collapsed, so every `getBoundingClientRect()` returns zero — any measured scroll would land somewhere arbitrary. The restore's scroll reset must not depend on measurement.
5. **A history row with no `scanResult`** must render no Open button, not one that opens an empty scan.

---

### Task 1: Persist the posting's own stated claims

`ScanResponse` already carries `attributes` and `search_queries`, and the frontend already forwards them to `/api/verify`. `ScanResult` drops them, so a restored scan would keep its conclusions and lose the claims they were drawn from — a `Channel Match` failure with no record of the channel the posting claimed.

**Files:**
- Modify: `entrypoints/sidepanel/types/index.ts` — `ScanResult` (currently ends at line 203)
- Modify: `entrypoints/sidepanel/views/ScamScanView.tsx` — `buildScanResult`, the object literal ending at line 107
- Test: `entrypoints/sidepanel/views/ScamScanView.attributes.test.tsx` (create)

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `ScanResult.attributes?: Record<string, string>` and `ScanResult.searchQueries?: string[]`. Task 2's `restoreScanResult` carries both through unchanged.

- [ ] **Step 1: Write the failing test**

Create `entrypoints/sidepanel/views/ScamScanView.attributes.test.tsx` modelled on the harness in `entrypoints/sidepanel/views/ScamScanView.test.tsx` (the `vi.hoisted` mock of `../lib/api`, and the pick-then-scan helpers). Drive a real scan whose mocked `scanScreenshotStream` resolves with a response carrying `attributes` and `search_queries`:

```ts
const scanResponse = {
  valid: true,
  company_name: 'Acme Trading',
  job_summary: 'Sales associate wanted',
  anomalies: [],
  attributes: { LOCATION: 'Davao City office', CONTACT_METHOD: 'Messenger' },
  search_queries: ['Acme Trading branches Davao'],
  risk_score: 0, risk_level: 'low', score_breakdown: null, email_verifications: [],
};
```

Then two cases:

- **"carries the posting's stated claims into history"** — capture the `ScannedJob` passed to `onScanComplete`, assert `job.scanResult.attributes` deep-equals the response's `attributes`, and `job.scanResult.searchQueries` deep-equals its `search_queries`.
- **"omits the claims field entirely when the scan reports none"** — a response with no `attributes` key yields `scanResult.attributes` `undefined`, not `{}`. An empty object would render as "the posting claimed nothing" rather than "we have nothing to show".

- [ ] **Step 2: Run it to verify it fails**

Run: `npm test -- --run entrypoints/sidepanel/views/ScamScanView.attributes.test.tsx`
Expected: FAIL — both assertions, because `buildScanResult` copies neither field.

- [ ] **Step 3: Add the two fields to the type**

In `entrypoints/sidepanel/types/index.ts`, inside `ScanResult`, after `verificationError?: boolean;`:

```ts
  /**
   * The posting's own stated details, verbatim from the scan response.
   *
   * These are the claims the verification categories test, so a scan restored
   * from history without them keeps its conclusions and loses the ground they
   * were drawn from. Copied straight from the response; never reconstructed.
   */
  attributes?: Record<string, string>;
  /** The searches the scan model proposed, capped at 2 by the backend. */
  searchQueries?: string[];
```

- [ ] **Step 4: Populate them at scan time**

In `buildScanResult`'s returned literal in `ScamScanView.tsx`, after `scoreBreakdown`, add:

```ts
    attributes: data.attributes,
    searchQueries: data.search_queries,
```

No `|| {}` and no `|| []` — see the second test's reason.

- [ ] **Step 5: Run it to verify it passes**

Run: `npm test -- --run entrypoints/sidepanel/views/ScamScanView.attributes.test.tsx`
Expected: PASS, 2 tests.

- [ ] **Step 6: Typecheck and commit**

Run: `npm run compile` — expected clean.
Run: `npm test -- --run` — expected no regressions.

```bash
git add entrypoints/sidepanel/types/index.ts entrypoints/sidepanel/views/ScamScanView.tsx entrypoints/sidepanel/views/ScamScanView.attributes.test.tsx
git commit -m "feat(history): keep the posting's stated claims on the saved scan"
```

---

### Task 2: Restore a stored scan into the panel

**Files:**
- Modify: `entrypoints/sidepanel/views/ScamScanView.tsx` — module scope (add `restoreScanResult` and `findScrollParent` at module level, above `ScamScanViewProps`), `ScamScanViewProps`, the component signature, the restore effect, `handlePickElement`
- Test: `entrypoints/sidepanel/views/ScamScanView.restore.test.tsx` (create)

**Interfaces:**
- Consumes: `ScanResult` from Task 1. `restoreScanResult` must preserve `attributes` and `searchQueries` — the spread does this, but a test pins it.
- Produces:
  - `export function restoreScanResult(result: ScanResult): ScanResult` — pure, no React.
  - `export function findScrollParent(from: HTMLElement): HTMLElement` — module level, so the restore effect and `showEvidence` share one implementation and it is unit-testable.
  - `ScamScanViewProps.restoredJob?: { job: ScannedJob; token: number } | null`
  - `ScamScanViewProps.onScanStart?: () => void`

- [ ] **Step 1: Write the failing tests for the pure helper**

In `entrypoints/sidepanel/views/ScamScanView.restore.test.tsx`, a unit block that imports `restoreScanResult` and passes a stored `ScanResult`:

- **"clears the in-flight flag a saved job can carry"** — a stored result with `verificationLoading: true` comes back `verificationLoading: false`.
  ```ts
  // A job is written to history the moment the scan returns, before
  // verification runs, so `verificationLoading: true` is what an unverified
  // job actually stores. Restored as-is it renders "Verifying…" forever.
  ```
- **"clears the offer-analysis in-flight flag the same way"** — `offerAnalysisLoading: true` comes back `false`.
- **"keeps a real verification failure"** — `verificationError: true` comes back `true`. This is the inverse of the two above and is the reason they are cleared individually rather than by dropping the whole result.
  ```ts
  // The inverse, and the reason these are cleared one at a time: a job whose
  // verification genuinely failed must still say so when reopened. Clearing
  // every flag to make the panel look tidy hides a real outcome.
  ```
- **"keeps the stored claims"** — `attributes` and `searchQueries` survive.
- **"keeps a result that found nothing, as a result that found nothing"** — a `verificationResult` with `searchOk: false` comes back unchanged. The stored evidence is the outcome.

- [ ] **Step 2: Write the failing tests for the component**

Driving the real component with `restoredJob` passed as a prop:

- **"shows a reopened scan's findings"** — render with a job whose `scanResult` has one `high` anomaly; assert the anomaly's text is in the document.
- **"re-applies when the same job is opened again"** — render with `{ job, token: 1 }`, rerender with `{ job: { ...job }, token: 2 }` where the new `scanResult` carries a *different* anomaly. Assert the new anomaly appears.
  ```ts
  // Same job, new token. An effect keyed on the job object would fire once and
  // never again, so the second Open does nothing — the user presses it and the
  // panel is stale. The job here is a fresh object so the test cannot pass by
  // accident on reference change.
  ```
- **"shows no thumbnails on a reopened scan"** — assert zero `<img>` elements with a data URL. Screenshots are not persisted; this is the stated loss, and a test is what keeps it from being "fixed" by accident.
- **"reports the start of a fresh capture"** — click the pick button with `onScanStart` supplied; assert it was called once. Covers Review Focus #4's sibling: the app-bar marker must clear when the reader takes a new capture.

- [ ] **Step 3: Run it to verify it fails**

Run: `npm test -- --run entrypoints/sidepanel/views/ScamScanView.restore.test.tsx`
Expected: FAIL — `restoreScanResult` is not exported, and `restoredJob` is not a prop.

- [ ] **Step 4: Add `restoreScanResult` at module level**

Above `ScamScanViewProps` in `ScamScanView.tsx`:

```ts
/**
 * A stored scan, made displayable again.
 *
 * Two flags are cleared and no others. A job is written to history the moment
 * its scan returns — before verification has run — so `verificationLoading:
 * true` is what an unverified job genuinely stores, and restored as-is it
 * renders "Verifying…" forever. `offerAnalysisLoading` has the same shape.
 *
 * `verificationError` is deliberately left alone. It records that a lookup
 * failed, and a reopened scan must still say so: clearing it to make the panel
 * look settled would hide a real outcome.
 */
export function restoreScanResult(result: ScanResult): ScanResult {
  return { ...result, verificationLoading: false, offerAnalysisLoading: false };
}
```

- [ ] **Step 5: Add `findScrollParent` at module level and use it in `showEvidence`**

Move the existing inner `findScrollParent` out of the component body verbatim, and export it. `showEvidence` already calls it — change nothing about how. This is one implementation shared by two callers, not a second way of finding the same element.

- [ ] **Step 6: Add the props**

In `ScamScanViewProps`:

```ts
  /**
   * A scan to display, from history.
   *
   * `token` is what the effect keys on, never the job: opening the same job
   * twice has to re-apply, and a dependency on the job object alone would fire
   * once and then never again.
   */
  restoredJob?: { job: ScannedJob; token: number } | null;
  /** Fired when the reader starts a fresh capture, so a saved-scan marker can clear. */
  onScanStart?: () => void;
```

Destructure both in the component signature.

- [ ] **Step 7: Add the restore effect**

In the component body, after the existing state declarations. It resets the panel to "a scan happened", which is what the picker would otherwise be showing:

```ts
  /**
   * Put a stored scan back on screen.
   *
   * Keyed on `token` alone. React compares the effect's dependencies by
   * reference, so a job reopened twice would otherwise leave the panel stale.
   */
  useEffect(() => {
    if (!restoredJob) return;
    const restored = restoredJob.job.scanResult;
    setScanResult(restoreScanResult(restored));
    setIsValidJob(restored.isJobPosting);
    setHasScanned(true);
    setScreenshots([]);
    setLightboxIndex(null);
    setIsLoading(false);
    setProgress(null);
    setVerificationFailed(false);
    // Not measured. The reader presses Open from the Match tab, where this view
    // is `display: none` and every rect reads zero — anything derived from
    // layout here would land somewhere arbitrary. `scrollTop` needs only the
    // element.
    if (rootRef.current) findScrollParent(rootRef.current).scrollTop = 0;
  }, [restoredJob?.token]);
```

Add `const rootRef = useRef<HTMLDivElement | null>(null);` beside the other refs, and put `ref={rootRef}` on the outermost element `ScamScanView` returns.

- [ ] **Step 8: Fire `onScanStart` from `handlePickElement`**

`handlePickElement` (line 277) is the reader starting a fresh capture. Call `onScanStart?.()` at its top, after the `if (isLoading) return;` guard. Add `onScanStart` to its dependency array.

- [ ] **Step 9: Run it to verify it passes**

Run: `npm test -- --run entrypoints/sidepanel/views/ScamScanView.restore.test.tsx`
Expected: PASS.

- [ ] **Step 10: Mutation-check both directions**

Break `restoreScanResult` by returning `result` unchanged, and confirm a test fails. Then break it by clearing `verificationError: false` as well, and confirm the "keeps a real verification failure" test fails. The first is the overcorrection — clearing nothing — and the second is the one this codebase's failure mode actually takes.

- [ ] **Step 11: Typecheck and commit**

Run: `npm run compile` — expected clean. Run: `npm test -- --run` — expected no regressions.

```bash
git add entrypoints/sidepanel/views/ScamScanView.tsx entrypoints/sidepanel/views/ScamScanView.restore.test.tsx
git commit -m "feat(scan): restore a stored scan into the panel"
```

---

### Task 3: Say in the app bar that the scan is saved

**Files:**
- Modify: `entrypoints/sidepanel/components/shell/TopAppBar.tsx` — `TopAppBarProps` (line 14) and the render body
- Test: `entrypoints/sidepanel/components/shell/TopAppBar.savedScan.test.tsx` (create)

**Interfaces:**
- Consumes: nothing.
- Produces: `TopAppBarProps.savedScan?: { title: string; timestamp: string } | null`. Task 5 passes it from `App` and clears it on `onScanStart`.

- [ ] **Step 1: Write the failing tests**

- **"names the saved scan and the day it was taken"** — render with `savedScan={{ title: 'Sales associate wanted', timestamp: '2026-10-09T08:30:00.000Z' }}`. Assert the document contains `Saved from job history` and the formatted date. The date is the point of the marker: evidence retrieved four days ago was retrieved four days ago.
- **"shows nothing extra when no scan is open"** — render with no `savedScan`; assert `Saved from job history` is absent.

Format the timestamp with the same helper the history rows use, `formatTimestamp` — find it with `grep -rn "formatTimestamp" entrypoints/sidepanel` and import it from wherever it lives. One formatter, so a row and the marker cannot disagree about the same timestamp.

- [ ] **Step 2: Run it to verify it fails**

Run: `npm test -- --run entrypoints/sidepanel/components/shell/TopAppBar.savedScan.test.tsx`
Expected: FAIL — the marker is not rendered.

- [ ] **Step 3: Add the prop and render it**

```ts
  /**
   * Set while the panel shows a scan reopened from history.
   *
   * The date is load-bearing. A reopened score was measured on that date, so a
   * reader deciding today is looking at evidence retrieved then — the marker
   * states when, and does not claim the result is still current, because the
   * app cannot know that.
   */
  savedScan?: { title: string; timestamp: string } | null;
```

Destructure with a `null` default. Render below the brand text, inside the existing bar container, only when set: the title truncated, the word `Saved from job history`, and the formatted timestamp. Give the wrapper `data-role="saved-scan-marker"` so a test names what it is looking at rather than guessing at a tag.

- [ ] **Step 4: Run it to verify it passes**

Run: `npm test -- --run entrypoints/sidepanel/components/shell/TopAppBar.savedScan.test.tsx`
Expected: PASS, 2 tests.

- [ ] **Step 5: Mutation-check**

Delete the `{savedScan && ...}` guard so the marker renders unconditionally; confirm the "shows nothing extra" test fails. A marker that always shows is worse than none — it would claim every fresh scan was saved.

- [ ] **Step 6: Typecheck and commit**

Run: `npm run compile` — expected clean.

```bash
git add entrypoints/sidepanel/components/shell/TopAppBar.tsx entrypoints/sidepanel/components/shell/TopAppBar.savedScan.test.tsx
git commit -m "feat(shell): mark a reopened scan and its date in the app bar"
```

---

### Task 4: An Open button on each history row

The button belongs in the **expanded** dropdown of a history row (`ResumeMatchView.tsx:431`), not in `JobMatchList`. That component renders `matches`, so it only covers jobs already run through resume matching — a job scanned and never matched would have no Open button at all.

**Files:**
- Modify: `entrypoints/sidepanel/views/ResumeMatchView.tsx` — `ResumeMatchViewProps`, the expanded row (line 431)
- Test: `entrypoints/sidepanel/views/ResumeMatchView.openJob.test.tsx` (create)

**Interfaces:**
- Consumes: nothing.
- Produces: `ResumeMatchViewProps.onOpenJob?: (job: ScannedJob) => void`. Task 5 wires it.

- [ ] **Step 1: Write the failing tests**

Reuse the render harness from `entrypoints/sidepanel/views/ResumeMatchView.riskMessage.test.tsx`.

- **"opens the scan behind a history row"** — render two jobs, expand the first row, click its Open button, assert `onOpenJob` was called once with that job.
- **"does not offer to open a job that was never scanned"** — render a job whose `scanResult` is missing. The expanded block is already guarded by `isExpanded && sr`, so assert no `[data-role="open-job"]` is present. Covers Review Focus #5.
- **"only offers the button on the row the reader opened"** — with two jobs expanded-by-index checks, assert exactly one Open button exists. A button that appears on every row at once would read as a bulk action.

- [ ] **Step 2: Run it to verify it fails**

Run: `npm test -- --run entrypoints/sidepanel/views/ResumeMatchView.openJob.test.tsx`
Expected: FAIL — no `onOpenJob` prop, no button.

- [ ] **Step 3: Add the prop and the button**

```ts
  /** Open a scan from history. The panel it restores into lives elsewhere. */
  onOpenJob?: (job: ScannedJob) => void;
```

Destructure with a `null` default. At the top of the expanded block, render `onOpenJob &&` a `<button data-role="open-job" type="button" onClick={() => onOpenJob(job)}>` reading `Open scan`.

Style it `tactile-btn-accent` with `px-3 py-1.5 rounded-lg text-label-md` — the tactile class supplies the press, so it satisfies the container/button rule without anything extra. If you use any `/NN` opacity variant on a custom token, declare it in `assets/tailwind.css` first; `borderVariants.test.ts` will fail otherwise.

- [ ] **Step 4: Run it to verify it passes**

Run: `npm test -- --run entrypoints/sidepanel/views/ResumeMatchView.openJob.test.tsx`
Expected: PASS, 3 tests.

- [ ] **Step 5: Mutation-check**

Pass `job.id` instead of `job` to `onOpenJob`; confirm the first test fails. An id would look correct in the test's `toHaveBeenCalledWith` if that assertion used an id too — which is why it uses the whole job.

- [ ] **Step 6: Typecheck and commit**

Run: `npm run compile` — expected clean.

```bash
git add entrypoints/sidepanel/views/ResumeMatchView.tsx entrypoints/sidepanel/views/ResumeMatchView.openJob.test.tsx
git commit -m "feat(match): an Open button on every history row"
```

---

### Task 5: Wire it together

**Files:**
- Modify: `entrypoints/sidepanel/App.tsx` — state near line 17, `TopAppBar` (line 114), `ScamScanView` (line 128), `ResumeMatchView` (line 138)
- Test: `entrypoints/sidepanel/App.test.tsx` (create)

**Interfaces:**
- Consumes: `restoredJob` and `onScanStart` (Task 2), `savedScan` (Task 3), `onOpenJob` (Task 4).

- [ ] **Step 1: Write the failing test**

`App` has no test file today and the tab flip is the one behaviour in this feature no component owns. Stub the two views — this is a wiring test, so replacing the children is the point, not a shortcut:

```ts
vi.mock('./views/ScamScanView', () => ({
  ScamScanView: (props: any) => (
    <div data-role="scan-view" data-restored-token={props.restoredJob?.token ?? ''} />
  ),
}));
vi.mock('./views/ResumeMatchView', () => ({
  ResumeMatchView: (props: any) => (
    <button data-role="open-job" onClick={() => props.onOpenJob?.(storedJob)} />
  ),
}));
```

Mock `chrome.storage.local.get`/`set` with a callback that calls back immediately, and mock `./hooks/useBackendHealth` to return `{ isOnline: true, isChecking: false, checkNow: vi.fn() }`.

Cases:
- **"opens a history scan and shows it"** — click `[data-role="open-job"]`; assert the scan view is visible (its wrapper is not `hidden`) and carries token `1`.
- **"clears the marker when the reader takes a new capture"** — after opening, click the scan view stub to fire `onScanStart`; assert the marker is gone.
- **"gives a second open a new token"** — click Open twice; assert the token changed. A token stuck at `1` means the second Open re-applies nothing — Review Focus #1, at the layer that actually mints the token.

- [ ] **Step 2: Run it to verify it fails**

Run: `npm test -- --run entrypoints/sidepanel/App.test.tsx`
Expected: FAIL — nothing passes a token or a marker yet.

- [ ] **Step 3: Hold the state**

Beside `scannedJobs` (line 17):

```ts
  const [restored, setRestored] = useState<{ job: ScannedJob; token: number } | null>(null);
  const restoreToken = useRef(0);
```

A monotonic counter, not `Date.now()`. Two clicks inside one millisecond is not something a person does, but the counter costs a line and removes the question.

- [ ] **Step 4: Wire the four props**

- `TopAppBar`: `savedScan={restored ? { title: restored.job.title, timestamp: restored.job.timestamp } : null}`
- `ScamScanView`: `restoredJob={restored}` and `onScanStart={() => setRestored(null)}`
- `ResumeMatchView`: `onOpenJob={handleOpenJob}`

```ts
  const handleOpenJob = useCallback((job: ScannedJob) => {
    restoreToken.current += 1;
    setRestored({ job, token: restoreToken.current });
    setActiveView('scan');
  }, []);
```

Flip the tab inside the same callback — if the two were separate, a failure between them would leave the reader in Match with a scan loaded and nothing to look at.

- [ ] **Step 5: Run it to verify it passes**

Run: `npm test -- --run entrypoints/sidepanel/App.test.tsx`
Expected: PASS, 3 tests.

- [ ] **Step 6: Verify the whole feature end to end**

Run: `npm run compile` — expected clean.
Run: `npm test -- --run` — expected no regressions.
Run: `cd backend && python -m pytest tests/ -q` — expected unchanged, and **still fully offline**. This feature touches no backend code; a jump from ~1.5s to tens of seconds means something reached the network.

- [ ] **Step 7: Check it by hand**

happy-dom performs no layout, so the suite cannot show that the marker looks right in the bar or that Open reads as a button next to a container that already looks operable. Run `npm run dev`, load the extension, scan a posting, then open it back from the Match tab and confirm: the marker sits cleanly in the app bar, the findings match the original scan, there are no thumbnails, and the Open button visibly presses.

- [ ] **Step 8: Commit**

```bash
git add entrypoints/sidepanel/App.tsx entrypoints/sidepanel/App.test.tsx
git commit -m "feat: open a saved scan from history into the scan tab"
```

---

## Self-review

**Spec coverage.** Every section of the spec maps to a task: the `attributes`/`search_queries` addition and the no-screenshots decision → Task 1; the restore table, the token keying, the scroll reset, and the marker-clearing `onScanStart` → Task 2; the app-bar marker and the date → Task 3; the Open button's placement in the expanded row rather than `JobMatchList`, and the tactile treatment → Task 4; the state, the counter, and the tab flip → Task 5. No migration anywhere, as decided.

**One correction to the spec.** It said restore clears `verificationError` as well as the loading flags. That is wrong: `verificationError` records a lookup that genuinely failed, and the restored panel would hide a real outcome. Task 2 clears only the two `*Loading` flags and pins that with a test named for the inverse case. The spec's own "Accepted losses" would have been quietly untrue.

**Review Focus coverage.** #1 and #3 → Task 2, #2 → Task 2, #4 → Task 2's effect comment plus Task 5's stubbed click, #5 → Task 4. All five are pinned.

**Proportion.** Five tasks, each ending in a runnable, green deliverable. Test bodies are given only where the assertion text matters; component bodies are left to the implementer.