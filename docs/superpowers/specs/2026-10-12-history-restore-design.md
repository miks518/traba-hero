# Reopening a scan from job history

**Date:** 2026-10-12
**Status:** approved, ready for planning

## What it does

Every scan in job history gets an **Open** button. Clicking it loads that
posting's saved scan back into the Scan tab, rendered by the same components
that rendered it the first time, with the app bar stating that it is a saved
result and when it was taken.

## Why it is smaller than it sounds

`ScannedJob.scanResult` already stores the complete `ScanResult` — score, level,
anomalies, offer analysis, the verification result with its sources, email
checks, job summary, posting analysis, score breakdown, company name. The schema
was not the problem; the UI simply had no way to read it back.

Two fields are genuinely absent, and both are ones a reopened scan is worse
without.

### `attributes` — the posting's own stated claims

`LOCATION`, `CONTACT_METHOD`, `MEETING_SPOT`, `REGISTERED_AS`, `PAY`, and the
rest. `ScanResponse` already carries them (`entrypoints/sidepanel/lib/api.ts:523`)
and the frontend already forwards them to `/api/verify`, because the backend
quotes them back to the model as the claims its categories test. Without them on
`ScanResult`, a restored scan keeps its conclusions and loses the things those
conclusions were drawn from — a `Channel Match` failure with no record of the
channel the posting claimed.

`attributes` and `search_queries` move onto `ScanResult` and are populated in
`buildScanResult`. Cost is on the order of 1KB per scan.

### Screenshots — deliberately not stored

The manifest requests `storage` but not `unlimitedStorage`, so
`chrome.storage.local` caps at **5MB for everything**. Up to four screenshots at
1280px JPEG q0.8 is roughly 0.4–1MB per scan, which puts "save the images" at
five to ten scans before writes begin to fail. Chrome fails those silently,
which is this project's most reliable way to lose data quietly.

A restored scan therefore shows no thumbnails. That is a real, stated loss: the
posting's image is not recoverable from the saved scan. It was the trade for
staying inside the budget, and the alternative — requesting `unlimitedStorage` —
removes Chrome's cap with no eviction backstop, so history would grow unbounded
with nothing trimming it.

## Restore path

`ScamScanView` owns its scan state internally. Rather than lift it into `App`,
it takes the restored job as a prop:

```ts
restoredJob?: { job: ScannedJob; token: number } | null;
```

A `useEffect` keyed on **`token`**, never on the job. Opening the same job twice
has to re-apply, and a dependency on the job object alone would fire once and
then never again — the same class of bug as a `document.querySelector` reaching a
stale node.

On restore it sets:

| State | To | Why |
|---|---|---|
| `scanResult` | `job.scanResult` | |
| `hasScanned` | `true` | otherwise the panel renders the empty picker |
| `isValidJob` | `scanResult.isJobPosting` | |
| `screenshots` | `[]` | not stored |
| `verificationLoading` | `false` | stored results carry no in-flight flag, but a restored job must never render as "Verification Unavailable" for a verification that succeeded |
| `verificationError` | `false` | same |
| `offerAnalysisLoading` | `false` | same |
| `lightboxIndex` | `null` | |
| scroller `scrollTop` | `0` | otherwise you land mid-panel wherever you were scrolled last |

It also calls `onScanStart` when the user picks a new element, which is what
clears the app-bar marker — otherwise a fresh capture starts under a banner
still claiming to be saved.

## The app bar marker

`TopAppBar` takes `savedScan?: { title: string; timestamp: string } | null` and,
when set, shows the title and a formatted date beside the brand. The date is
what makes it a *saved* result rather than a re-scan: a reader who reopened a
posting three days ago is looking at evidence retrieved three days ago, and the
number in the ring was true on that date.

Staleness is inherent to caching evidence and is not something this path can
fix. The marker states when the retrieval happened; it does not claim the result
is current.

## The Open button

It goes in the **expanded** dropdown of each history row
(`entrypoints/sidepanel/views/ResumeMatchView.tsx:431`) — the rows already expand
on click and already show `formatTimestamp(job.timestamp)`.

It does **not** go on `JobMatchList`. That component renders `matches`, so it
only covers jobs that have been run through resume matching; a job that was
scanned and never matched would have no Open button at all.

The button carries the tactile treatment — `tactile-btn-*`, with the press. The
history rows already violate the container/button split by looking operable
(`cursor-pointer`, hover state, `role="button"`) while being containers, and a
button inside one of those needs the press or it reads as a shaded label.

## Wiring

`App` holds one piece of state and passes two things down:

- `restoredJob` to `ScamScanView`
- `onOpenJob(job)` to `ResumeMatchView`, which sets the state **and** flips
  `activeView` to `'scan'`

`token` is a monotonic counter in `App`, not `Date.now()`. Two clicks in the same
millisecond are not a thing a person does, but a counter costs one line and
removes the question.

## No migration

The project is still in development, so stored jobs that predate the
`attributes` field are not converted. A job saved before this change reopens
without its claims detail. Adding `migrateScannedJobs` for it would be
maintaining a path that only matters to a build nobody is running.

## Tests

`ScamScanView`:
- restore populates the scan state and clears screenshots
- the same job twice re-applies (token changes; the job object does not)
- a restored result renders no verification spinner and no error notice
- restore scrolls the scroller to the top
- `onScanStart` fires when a new element is picked

`ResumeMatchView`:
- the expanded row has an Open button that reports the right job
- a row with no `scanResult` renders no Open button

`TopAppBar`:
- the marker shows the date when set, and nothing when null

`App` (new file):
- Open flips `activeView` to `'scan'` and sets the restored job
- `onScanStart` clears the marker

`App` has no test file today, and the tab flip is the one behaviour in this
feature with no other guard on it — every other piece is covered at the component
that owns it.

happy-dom performs no layout, so nothing here asserts a rendered position. The
scroll assertion covers the `scrollTop` written, which is what the component
controls.

## Accepted losses

- **No screenshots on reopen.** The posting's image is not recoverable. Stated
  here because it is a capability, not a bug.
- **Sources can go stale** between scanning and reopening.
- **Jobs saved before this change reopen without `attributes`.** No migration, by
  decision.