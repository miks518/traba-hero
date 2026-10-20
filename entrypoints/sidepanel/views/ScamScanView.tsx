import React, { useCallback, useEffect, useRef, useState } from 'react';
import { ReportPanel, ReportSkeleton } from '../components/report';
import { ScanActions, PickerButton } from '../components/scan';
import { Icon, ToastContainer, useToastManager } from '../components/common';
import { useScanSession, restoreScanResult } from '../hooks/useScanSession';
import { riskAccent } from '../lib/riskAccent';
import type { ScanProgress, VerifyContext } from '../lib/api';
import type { ScannedJob, ScanResult } from '../types';

export { restoreScanResult };

export interface ScamScanViewProps {
  onScanComplete?: (job: ScannedJob) => void;
  /**
   * Called when a stage that runs after the scan finishes produces a new result.
   * Verification settles the level after the job has already been written to
   * history, so without this the panel and the history entry disagree about the
   * same posting.
   */
  onScanResultUpdate?: (jobId: string, scanResult: ScanResult) => void;
  onScanProgressChange?: (progress: ScanProgress | null) => void;
  isOnline?: boolean;
  /**
   * A scan to display, reopened from history.
   *
   * `token` is what the restore keys on, never the job: opening the same job
   * twice has to re-apply, and an effect keyed on the job object alone fires once
   * and then never again, leaving the panel stale after the second Open.
   */
  restoredJob?: { job: ScannedJob; token: number } | null;
  /**
   * Fired when the reader starts a fresh capture, so a parent holding a "this is
   * a saved scan" marker can clear it. The marker outliving a new capture would
   * claim the panel is showing saved results when it is showing fresh ones.
   */
  onScanStart?: () => void;
}

/**
 * The scan view — capture chrome and the report, composed.
 *
 * **What this file used to be.** It was over a thousand lines in which the report
 * markup, the two abort lifecycles, the screenshot picker state machine, the
 * lightbox, the history callbacks and the risk score were all interleaved, so
 * every question about what the panel shows required reading the code that
 * produced it. It is now three things: this composition, `useScanSession` for the
 * lifecycle, and `components/report/` for the panel itself.
 *
 * **What is gone, and why.** `RiskGauge` and the score it drew are deleted. The
 * 0–100 index asserted a precision no stage could defend, invited "how did you get
 * 80?" with no answer available, and was summed from parts that were not
 * commensurable — parts which no longer exist in that form anyway. What replaces
 * it is a short authored instruction in `verdictCopy.ts` plus, once the backend
 * carries one, a one-line reason. See `docs/decisions/report-panel-redesign.md`.
 *
 * **`PostingAnalysis` and `JobSummary` are gone from the panel too.** Their
 * observational rule and word ban survive in the prompt; only the rendering is
 * retired. `job_summary` stays on the wire because the Match tab consumes it.
 *
 * Nothing was renamed to make the change smaller. `anomalies` is still
 * `anomalies` and the legacy severity ladder is still `low`/`mid`/`high` on the
 * wire — `docs/decisions/anomaly-terminology.md` records that those paths are
 * deliberate.
 */
export function ScamScanView({
  onScanComplete,
  onScanResultUpdate,
  onScanProgressChange,
  isOnline = true,
  restoredJob,
  onScanStart,
}: ScamScanViewProps) {
  const { toasts, showToast, removeToast } = useToastManager();

  const session = useScanSession({
    onScanComplete,
    onScanResultUpdate,
    onScanProgressChange,
    isOnline,
    restoredJob,
    onScanStart,
    showToast,
  });

  // Picker and crop are the capture affordances, not the report, so their state
  // stays here rather than in the session hook. They are phase counters rather
  // than booleans because `PickerButton` is driven from the outside — it lives in
  // the content script's page and the panel can only nudge it.
  const [pickerPhase, setPickerPhase] = useState(0);
  const [pickerCancelPhase, setPickerCancelPhase] = useState(0);
  const [pickerActive, setPickerActive] = useState(false);
  const [pickerActivating, setPickerActivating] = useState(false);

  const [cropPhase, setCropPhase] = useState(0);
  const [cropCancelPhase, setCropCancelPhase] = useState(0);
  const [cropActive, setCropActive] = useState(false);
  const [cropActivating, setCropActivating] = useState(false);

  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null);

  /**
   * Mirrors `pickerActive`, readable from the restore effect.
   *
   * `PickerButton` only acts on `forceCancel` when the counter is greater than
   * zero *and has changed*, so bumping it unconditionally would fire a cancel for
   * a picker that was never open. The restore effect keys on `token` alone and
   * must not re-run to pick up a newer value, so it reads this instead.
   */
  const pickerActiveRef = useRef(false);
  pickerActiveRef.current = pickerActive;

  /**
   * This view's own root, so the restore can find the scroller above it.
   *
   * Needed because the reader presses Open from the Match tab, where this whole
   * subtree is `display: none`. A query for a scroll container would still find
   * it, but a query for anything measured would not — and the restore resets the
   * scroll without measuring precisely for that reason.
   */
  const rootRef = useRef<HTMLDivElement | null>(null);

  /**
   * The nearest ancestor of `node` that actually scrolls, or the document if none
   * does.
   *
   * Walked rather than named. A `data-role` marker was the first attempt and it is
   * fragile in the way this project keeps paying for: rename it, or move the
   * layout, and the button silently stops doing anything. Reading `overflow` off
   * each ancestor answers the same question from the structure that is there.
   *
   * The document fallback matters twice over — it is what makes this testable,
   * since the panel is normally inside a scroll container and a unit test renders
   * it inside none, and it is what the restore path falls back to when the reader
   * presses Open from the Match tab.
   *
   * Computed style is unaffected by `display: none`; only the geometry is gone.
   * Callers that need an element must not then measure it.
   */
  const findScrollableAncestor = (node: HTMLElement): HTMLElement => {
    let parent = node.parentElement;
    while (parent) {
      const style = window.getComputedStyle(parent);
      if (/(auto|scroll|overlay)/.test(style.overflowY)) return parent;
      parent = parent.parentElement;
    }
    return document.scrollingElement as HTMLElement;
  };

  /**
   * Reset the scroll when a stored scan is reopened.
   *
   * A separate effect from the session's restore because it needs this view's
   * root, and because it must run *after* the restored result has been committed
   * — scrolling first would land the reader wherever the new content's scroll
   * height then put it.
   */
  useEffect(() => {
    if (!restoredJob) return;
    if (!rootRef.current) return;
    // Not measured. `scrollTop` needs only the element, and this view is
    // `display: none` while the reader is on the Match tab, so anything derived
    // from layout here would read zeros. Computed styles still resolve — it is the
    // *geometry* that is gone, which is all `scrollTop` avoids needing.
    findScrollableAncestor(rootRef.current).scrollTop = 0;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [restoredJob?.token]);

  /**
   * Cancel any overlay the reopen left behind. In the session hook's restore,
   * which cannot see this state; here, where the picker lives.
   */
  useEffect(() => {
    if (!restoredJob) return;
    // A picker or crop left active keeps its on-page overlay and its "Cancel Pick"
    // button, sitting over a saved result.
    setPickerPhase(0);
    setPickerActive(false);
    setPickerActivating(false);
    // Only if one is actually running. Bumped unconditionally, this fires
    // `PickerButton.cancel()` on a panel that never had a picker open, which clears
    // the selection the reader just made.
    if (pickerActiveRef.current) setPickerCancelPhase((p) => p + 1);
    setCropPhase(0);
    setCropActive(false);
    setCropActivating(false);
    setLightboxIndex(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [restoredJob?.token]);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return;
      if (lightboxIndex !== null) {
        setLightboxIndex(null);
        return;
      }
      if (pickerActive) {
        setPickerCancelPhase((p) => p + 1);
      } else if (cropActive) {
        setCropCancelPhase((p) => p + 1);
      }
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [pickerActive, cropActive, lightboxIndex]);

  const handlePickElement = useCallback(() => {
    if (session.isLoading) return;
    // Whatever branch this takes, the reader is starting a fresh capture. A
    // "saved scan" marker left standing across that would claim the panel is
    // showing stored evidence when it is showing new evidence.
    onScanStart?.();
    if (session.hasScanned) {
      session.resetAll();
    } else if (pickerActive) {
      setPickerCancelPhase((p) => p + 1);
    } else {
      setPickerPhase((p) => p + 1);
    }
  }, [session, pickerActive, onScanStart]);

  const {
    screenshots,
    isLoading,
    hasScanned,
    scanResult,
    progressPercent,
    handleScreenshotReady,
    removeScreenshot,
    resetAll,
    handleSelectionChange,
    handleScan,
  } = session;

  const showEmptyState = !hasScanned && screenshots.length === 0;
  const showReport = hasScanned && scanResult !== null;

  return (
    <div ref={rootRef} className="p-container-padding pb-24 bg-background flex flex-col gap-stack-md relative">
      <ToastContainer toasts={toasts} onRemove={removeToast} />

      {isLoading && (
        <div className="absolute top-0 left-0 w-full h-1 bg-surface-container-highest overflow-hidden rounded-full">
          <div className="w-full h-full bg-secondary animate-loading-bar rounded-full" />
        </div>
      )}

      {showEmptyState && (
        <div className="flex flex-col gap-2">
          <h2 className="text-headline-sm font-headline text-on-surface">Job Scan</h2>
          <p className="text-body-sm text-on-surface-variant">
            Pick a job post from the page to check for anomalies.
          </p>
        </div>
      )}

      {/* The report. Everything about a settled reading lives in here; nothing
          above or below this element knows what a finding is. */}
      {showReport && (
        <ReportPanel
          result={scanResult}
          verifying={Boolean(scanResult.verificationLoading) || session.verificationFailed}
          verificationError={Boolean(scanResult.verificationError)}
          currentQuery={session.currentSearchQuery}
          // The reason arrives with the verification result and is held on the
          // result itself, so it survives a later stage patching it — the same
          // reason `applyResult` composes onto the ref rather than replacing.
          verdictReason={scanResult.verificationResult?.verdictReason || undefined}
          // Both come from the session, not from `restoredJob`. Reading them off
          // the history record made the subject line blank on a fresh scan and
          // the date appear only when a job was reopened from the Match tab —
          // so the panel looked different depending on how you arrived at the
          // same reading. The session holds both on every path now.
          timestamp={session.scannedAt ?? undefined}
          title={session.jobTitle ?? undefined}
          needsCompanyName={session.needsCompanyName}
          elevate={session.elevate}
        />
      )}

      {isLoading && !showReport && <ReportSkeleton progressPercent={progressPercent} />}

      {/*
        `order-3`, and it must stay ahead of the capture preview below. This bar is
        `sticky bottom-0` with `mt-auto`, and both only hold it low in the column.
        An element with no order value sorts at 0, so the two report groups on
        order-1/order-2 pushed the bar above them and the "Pick again" control
        floated mid-panel. `order-last` would overcorrect and put it below the
        preview, which is not where it was.
      */}
      <ScanActions
        onPickElement={handlePickElement}
        onCancelPick={() => setPickerCancelPhase((p) => p + 1)}
        isPickerActive={pickerActive}
        isPickerActivating={pickerActivating}
        onManualCrop={() => setCropPhase((p) => p + 1)}
        onCancelCrop={() => setCropCancelPhase((p) => p + 1)}
        isCropActive={cropActive}
        isCropActivating={cropActivating}
        afterScan={hasScanned}
        disabled={isLoading}
        /*
          The primary action takes the level's colour only while that level is
          settled and dangerous. Scoped to the displayed result, which is what makes
          it temporary: picking a new element clears the reading, the accent prop
          goes with it, and the button returns to the accent colour with no timer of
          its own. A button still red after the result was gone would describe the
          *next* scan rather than the one on screen.
        */
        accent={session.elevate ? riskAccent(scanResult?.riskLevel) : undefined}
      />

      {screenshots.length > 0 && !hasScanned && (
        <div className="flex flex-col gap-3 order-4">
          <div className={`grid gap-2 ${screenshots.length > 1 ? 'grid-cols-2' : 'grid-cols-1'}`}>
            {screenshots.map((ss, i) => (
              <div
                key={i}
                className={`relative rounded-lg overflow-hidden border border-outline-variant/20 bg-surface-container cursor-pointer group ${
                  screenshots.length === 1 ? 'max-h-80' : 'aspect-square'
                }`}
                onClick={() => setLightboxIndex(i)}
              >
                <img
                  src={ss}
                  alt={`Selected ${i + 1}`}
                  className={`w-full h-full ${screenshots.length === 1 ? 'object-contain' : 'object-cover'}`}
                />
                <button
                  aria-label={`Remove screenshot ${i + 1}`}
                  onClick={(e) => {
                    e.stopPropagation();
                    removeScreenshot(i);
                  }}
                  className="absolute top-2 right-2 w-7 h-7 flex items-center justify-center rounded-full bg-black/60 text-white hover:bg-black/80 transition-colors"
                >
                  <Icon name="close" className="text-sm" />
                </button>
              </div>
            ))}
          </div>
          <button
            onClick={handleScan}
            disabled={isLoading || !isOnline}
            title={isOnline ? undefined : 'Server unreachable'}
            className="w-full tactile-btn-accent py-3 rounded-lg font-headline text-base flex items-center justify-center gap-2 disabled:opacity-70 disabled:cursor-not-allowed active:translate-y-[1px]"
          >
            <Icon name="security" />
            {isLoading
              ? 'Scanning...'
              : !isOnline
                ? 'Server Unreachable'
                : `Scan (${screenshots.length})`}
          </button>
        </div>
      )}

      {lightboxIndex !== null && screenshots[lightboxIndex] && (
        <div
          className="fixed inset-0 z-50 bg-black/85 flex items-center justify-center"
          onClick={() => setLightboxIndex(null)}
        >
          <button
            aria-label="Close"
            onClick={() => setLightboxIndex(null)}
            className="absolute top-4 right-4 w-8 h-8 flex items-center justify-center rounded-full bg-black/60 text-white hover:bg-black/80 transition-colors z-10"
          >
            <Icon name="close" className="text-lg" />
          </button>

          {screenshots.length > 1 && lightboxIndex > 0 && (
            <button
              aria-label="Previous screenshot"
              onClick={(e) => {
                e.stopPropagation();
                setLightboxIndex(lightboxIndex - 1);
              }}
              className="absolute left-4 top-1/2 -translate-y-1/2 w-10 h-10 flex items-center justify-center rounded-full bg-black/60 text-white hover:bg-black/80 transition-colors z-10"
            >
              <Icon name="chevron_left" className="text-2xl" />
            </button>
          )}

          {screenshots.length > 1 && lightboxIndex < screenshots.length - 1 && (
            <button
              aria-label="Next screenshot"
              onClick={(e) => {
                e.stopPropagation();
                setLightboxIndex(lightboxIndex + 1);
              }}
              className="absolute right-4 top-1/2 -translate-y-1/2 w-10 h-10 flex items-center justify-center rounded-full bg-black/60 text-white hover:bg-black/80 transition-colors z-10"
            >
              <Icon name="chevron_right" className="text-2xl" />
            </button>
          )}

          <img
            src={screenshots[lightboxIndex]}
            alt={`Full size screenshot ${lightboxIndex + 1}`}
            className="max-w-[90vw] max-h-[90vh] object-contain rounded-lg"
            onClick={(e) => e.stopPropagation()}
          />

          <div className="absolute bottom-4 left-1/2 -translate-x-1/2 px-3 py-1 rounded-full bg-black/60 text-white text-label-sm">
            {lightboxIndex + 1} / {screenshots.length}
          </div>
        </div>
      )}

      <PickerButton
        forceActivate={pickerPhase}
        forceCancel={pickerCancelPhase}
        forceManualCrop={cropPhase}
        forceCropCancel={cropCancelPhase}
        onActiveChange={setPickerActive}
        onActivatingChange={setPickerActivating}
        onCropActiveChange={setCropActive}
        onCropActivatingChange={setCropActivating}
        onSelectionChange={handleSelectionChange}
        onScreenshotReady={handleScreenshotReady}
      />
    </div>
  );
}

export default ScamScanView;
