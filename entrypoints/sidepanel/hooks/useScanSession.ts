import { useCallback, useEffect, useRef, useState } from 'react';
import {
  scanScreenshotStream,
  verifyJobStream,
  analyzeOfferStream,
  ApiRequestError,
  type ScanProgress,
  type VerifyContext,
} from '../lib/api';
import { compressImage } from '../lib/imageUtils';
import { mapApiResponse, verdictLabel } from '../lib/mapApiResponse';
import { shouldElevateEvidence, type VerificationRun } from '../lib/riskDisplay';
import type { Anomaly, AnomalyAssessment, ScanResult, ScannedJob } from '../types';

/** How many screenshots one scan may carry. */
const MAX_SCREENSHOTS = 4;

/**
 * How many findings one verify request may carry.
 *
 * Equal to the backend's `MAX_VERIFY_ANOMALIES`; exceeding it is a 422, so the
 * client has to cap before sending. The cap keeps the highest-severity
 * findings, because losing a serious finding to a low-severity formatting note
 * would understate the reading. The omitted cards stay on screen with their own
 * amber note.
 */
export const MAX_VERIFY_ANOMALIES = 20;

const SEVERITY_RANK: Record<string, number> = { high: 3, mid: 2, low: 1 };

/**
 * The original indices to send, highest severity first, capped.
 *
 * Returned in ascending original order so the numbered findings block reads in
 * the same order as the cards. The verify model's 1-based indices then map
 * through this list back to the original findings.
 */
export function selectVerifiableIndices(anomalies: Anomaly[]): number[] {
  return anomalies
    .map((anomaly, index) => ({
      index,
      rank: SEVERITY_RANK[anomaly.severity ?? 'mid'] ?? 2,
    }))
    .sort((a, b) => b.rank - a.rank || a.index - b.index)
    .slice(0, MAX_VERIFY_ANOMALIES)
    .map((entry) => entry.index)
    .sort((a, b) => a - b);
}

/**
 * Attach the verdicts to the findings they were about.
 *
 * The verify request may carry a capped subset, so `assessment.index` is
 * relative to `selected`, not to the full list. An omitted finding gets an
 * amber "too many findings" verdict only when the check actually ran; if it did
 * not, the card's own honest note is better than inventing a reason. A selected
 * finding without a new verdict has any earlier verdict cleared, so the card
 * renders its amber "no verdict recorded" note rather than an old reading
 * presented as this one's. A check that did not run leaves a stored verdict
 * alone.
 */
export function mergeAnomalyAssessments(
  anomalies: Anomaly[],
  selected: number[],
  assessments: AnomalyAssessment[] | undefined,
  assessmentRun: boolean,
): Anomaly[] {
  const byOriginalIndex = new Map<number, AnomalyAssessment>();
  for (const assessment of assessments ?? []) {
    if (typeof assessment.index !== 'number') continue;
    const originalIndex = selected[assessment.index - 1];
    if (originalIndex === undefined || byOriginalIndex.has(originalIndex)) continue;
    byOriginalIndex.set(originalIndex, assessment);
  }

  const selectedSet = new Set(selected);
  return anomalies.map((anomaly, index) => {
    const assessment = byOriginalIndex.get(index);
    if (assessment) return { ...anomaly, assessment };
    if (assessmentRun) {
      // The current check ran. A selected finding it did not answer must not
      // keep the verdict from an earlier run: that is the previous reading
      // presented as this one's. Clearing it lets the card say "no evidence
      // verdict was recorded". A finding the request did not carry gets the
      // cap note instead, for the same reason.
      return {
        ...anomaly,
        assessment: selectedSet.has(index)
          ? undefined
          : {
              status: 'unknown',
              finding: 'Not checked — there were more findings than one search can check. Shown so you notice it.',
            },
      };
    }
    // The check did not run: keep a stored verdict if this scan already has one.
    return anomaly;
  });
}

function toVerifyFinding(anomaly: Anomaly) {
  return {
    flag: anomaly.title,
    reasoning: anomaly.description,
    severity: anomaly.severity ?? '',
    code: anomaly.code,
    quote: anomaly.quote,
  };
}

function generateJobId(): string {
  return `job-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function friendlyError(e: unknown): string {
  if (e instanceof DOMException && e.name === 'AbortError')
    return 'The scan took too long. Check that the backend is running and try again.';
  if (e instanceof TypeError)
    return 'Could not connect to the AI service. Make sure the backend is running.';
  if (e instanceof ApiRequestError) {
    if (e.status === 502) return "Hmm, I can't scan at the moment. Please try again.";
    if (e.status === 504) return 'The scan took too long. Check that the AI service is running.';
    if (e.status === 429) return 'Too many requests. Please wait a moment and try again.';
    if (e.status === 422) return 'The image could not be processed. Try selecting a different area.';
    if (e.status >= 500) return 'The AI service encountered an error. Please try again later.';
  }
  return 'Something went wrong during the scan. Please try again later.';
}

export interface UseScanSessionOptions {
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
  /** A scan to display, reopened from history. */
  restoredJob?: { job: ScannedJob; token: number } | null;
  /** Fired when the reader starts a fresh capture. */
  onScanStart?: () => void;
  /** Toasts, so error copy stays in one place. */
  showToast: (message: string, kind: 'error' | 'success' | 'info') => void;
}

/**
 * Everything about a scan except how it looks.
 *
 * The lifecycle lives here rather than in the view for one reason: `ScamScanView`
 * had grown past a thousand lines in which the state machine, the two abort
 * lifecycles, the history callback plumbing and the render were interleaved, so
 * every question about *what the panel shows* required reading the code that
 * *produced* it. Splitting them means the view is a composition of the report and
 * the capture affordances, and this is the part that can be reasoned about — and
 * tested — on its own.
 *
 * The render also no longer knows about the score. It never had a use for it
 * beyond passing it to a gauge that no longer exists.
 */
export function useScanSession({
  onScanComplete,
  onScanResultUpdate,
  onScanProgressChange,
  isOnline = true,
  restoredJob,
  onScanStart,
  showToast,
}: UseScanSessionOptions) {
  const [screenshots, setScreenshots] = useState<string[]>([]);
  const [hasSelection, setHasSelection] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [hasScanned, setHasScanned] = useState(false);
  const [progress, setProgress] = useState<ScanProgress | null>(null);
  const [scanResult, setScanResult] = useState<ScanResult | null>(null);
  const [currentSearchQuery, setCurrentSearchQuery] = useState('');
  const [verificationFailed, setVerificationFailed] = useState(false);

  /**
   * When this reading was taken, and what the posting is called.
   *
   * **Both used to live only on the history record**, which is why the report's
   * subject line was blank on a fresh scan and showed a date only when the reader
   * reopened the job from the Match tab. The panel states two facts about the
   * reading itself — when it was taken, and what it is a reading *of* — and
   * neither is a property of the history entry. They belong to the result on
   * screen, so they are held here and survive the result being replaced.
   *
   * `jobTitle` is the same string `onScanComplete` writes to history, derived the
   * same way, so the panel and the history entry cannot disagree about what the
   * posting is called.
   */
  const [scannedAt, setScannedAt] = useState<string | null>(null);
  const [jobTitle, setJobTitle] = useState<string | null>(null);

  const abortRef = useRef<AbortController | null>(null);
  const verifyAbortRef = useRef<AbortController | null>(null);

  /**
   * Written at the two points that matter — when a scan lands, and when a later
   * stage patches it — so the verification callback can read the current result
   * synchronously. Deliberately not mirrored from render state: a render between
   * the scan and verification would restore a stale value, and verification can
   * fail before the first render commits. Calling a parent callback from inside a
   * state updater would also fire twice under StrictMode.
   */
  const scanResultRef = useRef<ScanResult | null>(null);

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
      verifyAbortRef.current?.abort();
    };
  }, []);

  /** Apply a patch and tell the parent, so history shows what the panel shows. */
  const applyResult = useCallback(
    (patch: Partial<ScanResult>, jobId?: string) => {
      setScanResult((prev) => (prev ? { ...prev, ...patch } : null));
      if (!jobId) return;
      const current = scanResultRef.current;
      if (!current) return;
      // Compose onto the ref as well, so a later patch builds on this one rather
      // than on the value from before it.
      const merged = { ...current, ...patch };
      scanResultRef.current = merged;
      onScanResultUpdate?.(jobId, merged);
    },
    [onScanResultUpdate],
  );

  const startOfferAnalysis = useCallback(async (text: string, companyName: string) => {
    verifyAbortRef.current?.abort();
    const controller = new AbortController();
    verifyAbortRef.current = controller;

    setScanResult((prev) => (prev ? { ...prev, offerAnalysisLoading: true } : null));

    try {
      const result = await analyzeOfferStream(
        text,
        companyName,
        controller.signal,
        (p) => setProgress(p),
      );

      if (result.data) {
        const raw = result.data;
        setScanResult((prev) =>
          prev
            ? {
                ...prev,
                offerAnalysisLoading: false,
                offerAnalysis: {
                  kind: raw.kind,
                  verdict: raw.verdict,
                  whatItAsks: raw.what_it_asks,
                  whatItOffers: raw.what_it_offers,
                  whatToCheck: raw.what_to_check,
                  isOffer: raw.is_offer,
                },
              }
            : null,
        );
      } else {
        setScanResult((prev) => (prev ? { ...prev, offerAnalysisLoading: false } : null));
      }
    } catch (e) {
      // The verdict comes from the indicators already found in the scan, so a
      // failed analysis pass costs the explanation, not the reading.
      console.error('[analyze-offer] Error:', e);
      setScanResult((prev) => (prev ? { ...prev, offerAnalysisLoading: false } : null));
    }
  }, []);

  const startVerification = useCallback(
    async (context: VerifyContext, jobId?: string) => {
      verifyAbortRef.current?.abort();
      const controller = new AbortController();
      verifyAbortRef.current = controller;

      setScanResult((prev) =>
        prev ? { ...prev, verificationLoading: true, verificationError: false } : null,
      );
      setCurrentSearchQuery('');
      setVerificationFailed(false);

      // Send the findings in the order the cards show them, capped at the
      // backend's limit. Rebuilt from the current result rather than from
      // `context.anomalies` so the model's 1-based indices and the merge below
      // describe the same list even if the caller handed over a different one.
      const currentAnomalies = scanResultRef.current?.anomalies ?? [];
      const selected = selectVerifiableIndices(currentAnomalies);
      const requestContext = {
        ...context,
        anomalies: selected.map((index) => toVerifyFinding(currentAnomalies[index])),
      };

      try {
        const verifyResult = await verifyJobStream(
          requestContext,
          controller.signal,
          (p) => setProgress(p),
          (query) => setCurrentSearchQuery(query),
        );

        if (verifyResult.result) {
          const result = verifyResult.result;
          // Verdict and score are adopted independently, and deliberately. Gating
          // both on the score meant a response carrying a level but no score had
          // its level silently discarded and fell back to whatever was on screen —
          // and the colour, the headline and the elevation test all key off the
          // level, so losing it loses the whole reading.
          //
          // The other half: falling back to the previous result when the response
          // has neither would keep a stale level on screen after a verification
          // that failed. A missing value means missing.
          const prev = scanResultRef.current;
          const nextVerdict = result.verdict ?? null;
          const assessmentRun = result.anomalyAssessmentRun === true;
          const mergedAnomalies = mergeAnomalyAssessments(
            prev?.anomalies ?? [],
            selected,
            result.anomalyAssessments,
            assessmentRun,
          );
          setVerificationFailed(false);
          applyResult(
            {
              verificationResult: result,
              verificationLoading: false,
              // The cards' final severity lives on the findings, not in the
              // verification result. `stale` retires a finding, `red` keeps the
              // scan's severity, and the card derives the chip from this.
              anomalies: mergedAnomalies,
              anomalyAssessmentRun: assessmentRun,
              verdicted: nextVerdict !== null,
              verdict: nextVerdict,
              verdictLabel: verdictLabel(nextVerdict),
              verdictBreakdown: result.verdictBreakdown,
            },
            jobId,
          );
        } else {
          setVerificationFailed(true);
          applyResult({ verificationLoading: false, verificationError: true }, jobId);
        }
      } catch (e) {
        if (controller.signal.aborted) {
          // Discarded, not failed. An abort here is either the reader reopening a
          // saved scan or the panel closing — in both cases this request's answer
          // was thrown away on purpose. Falling through would record
          // `verificationError: true` for a job whose verification nobody saw
          // fail, and `applyResult` would write it to history under a `jobId`
          // that after a reopen is a *different* job than the one on screen.
          return;
        }
        console.error('[verify] Error:', e);
        setVerificationFailed(true);
        // The posting-stage reading still stands, so history keeps a real result
        // rather than being left showing a verification that never resolved.
        applyResult({ verificationLoading: false, verificationError: true }, jobId);
      }
    },
    [applyResult],
  );

  const handleScreenshotReady = useCallback(
    async (dataUrl: string) => {
      const compressed = await compressImage(dataUrl);
      setScreenshots((prev) => {
        if (prev.length >= MAX_SCREENSHOTS) {
          showToast(
            `You can select up to ${MAX_SCREENSHOTS} images only. Remove one to add another.`,
            'error',
          );
          return prev;
        }
        return [...prev, compressed];
      });
    },
    [showToast],
  );

  const removeScreenshot = useCallback(
    (index: number) => {
      setScreenshots((prev) => {
        const next = prev.filter((_, i) => i !== index);
        if (next.length === 0) {
          setHasSelection(false);
          setHasScanned(false);
          setScanResult(null);
          setProgress(null);
          onScanProgressChange?.(null);
        }
        return next;
      });
    },
    [onScanProgressChange],
  );

  const resetAll = useCallback(() => {
    setScreenshots([]);
    setHasScanned(false);
    setIsLoading(false);
    setHasSelection(false);
    setScanResult(null);
    // Cleared with the result. A subject line left over from the previous reading
    // would sit above a fresh capture with nothing under it, which reads as a
    // title for a scan that has not happened.
    setScannedAt(null);
    setJobTitle(null);
    setProgress(null);
    setVerificationFailed(false);
    onScanProgressChange?.(null);
  }, [onScanProgressChange]);

  const handleSelectionChange = useCallback(
    (selected: boolean) => {
      if (screenshots.length === 0) setHasSelection(selected);
      if (!selected) {
        setHasScanned(false);
        setIsLoading(false);
        setScanResult(null);
        setProgress(null);
        setVerificationFailed(false);
        onScanProgressChange?.(null);
      }
    },
    [screenshots.length, onScanProgressChange],
  );

  const handleScan = useCallback(async () => {
    if (screenshots.length === 0) return;
    if (!isOnline) {
      showToast('Server unreachable. Check your connection and try again.', 'error');
      return;
    }
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setIsLoading(true);
    setProgress({ percent: 5, stage: 'Preparing request' });
    onScanProgressChange?.({ percent: 5, stage: 'Preparing request' });

    try {
      const result = await scanScreenshotStream(
        screenshots.map((s) => s.split(',')[1]),
        controller.signal,
        (p) => {
          setProgress(p);
          onScanProgressChange?.(p);
        },
      );

      if (result.timedOut) {
        showToast('The scan took too long. Check that the AI service is running.', 'error');
        setProgress(null);
        onScanProgressChange?.(null);
        return;
      }
      if (!result.response) {
        showToast('Scan ended before returning a result. Please try again.', 'error');
        setProgress(null);
        onScanProgressChange?.(null);
        return;
      }

      const data = result.response;
      const mapped = mapApiResponse(data);
      setScanResult(mapped);
      // Set before the early return below, so a posting with no employer still
      // gets a subject line. It is a fact about the capture, not about the
      // verification.
      setScannedAt(new Date().toISOString());
      // Set synchronously, not by mirroring render state. Verification can
      // reject before React commits the render above — a backend that is down
      // fails on the first attempt — and a ref that tracks state would still be
      // null at that point, leaving history stranded on the posting-only reading.
      scanResultRef.current = mapped;
      setHasScanned(true);
      setProgress(null);
      onScanProgressChange?.(null);

      if (mapped.isJobPosting) {
        const jobTitle = data.job_summary
          ? data.job_summary.slice(0, 60).replace(/\s+\S*$/, '')
          : mapped.scanningTarget;
        const jobId = generateJobId();
        // The same string the history entry carries, so the subject line and the
        // Match tab cannot disagree about what this posting is.
        setJobTitle(jobTitle);
        onScanComplete?.({
          id: jobId,
          title: jobTitle,
          summary: data.job_summary,
          timestamp: new Date().toISOString(),
          scanResult: mapped,
        });

        // One of two follow-up paths. With a named employer we can look it up;
        // without one there is nothing to look up, so the offer is assessed on its
        // own terms instead. Either way the reader gets a reading.
        const verifyCtx = data.verification_context;
        if (verifyCtx?.company_name && verifyCtx.company_name.trim()) {
          startVerification(
            {
              company_name: verifyCtx.company_name.trim(),
              job_summary: verifyCtx.job_summary || data.job_summary || '',
              anomalies: data.anomalies,
              // The posting's own stated details, forwarded verbatim. The backend
              // quotes them back to the model as the claims its categories test,
              // so omitting this left Channel Match — the one check that can detect
              // an impersonation — structurally unable to fire.
              attributes: data.attributes,
              // The searches the scan model proposed. Forwarding these is what
              // makes the second and third query happen; dropping them leaves every
              // verification on the employer query alone, reported as an ordinary
              // lookup with nothing anywhere reporting the shortfall.
              search_queries: data.search_queries,
            },
            jobId,
          );
        } else if (data.job_summary) {
          startOfferAnalysis(data.job_summary, data.company_name || '');
        }
      }
    } catch (e) {
      if (e instanceof DOMException && e.name === 'AbortError') return;
      setProgress(null);
      onScanProgressChange?.(null);
      showToast(friendlyError(e), 'error');
    } finally {
      setIsLoading(false);
    }
  }, [screenshots, showToast, onScanComplete, onScanProgressChange, isOnline, startVerification, startOfferAnalysis]);

  /**
   * Put a stored scan back on screen.
   *
   * Keyed on `token` alone. React compares effect dependencies by reference, so
   * the same job opened twice would otherwise leave the panel showing the
   * previous result while the reader believes they just loaded the other one.
   */
  useEffect(() => {
    if (!restoredJob) return;
    const restored = restoreScanResult(restoredJob.job.scanResult);

    // Cancel whatever is still running before touching state. Reachable in one
    // click: a scan takes up to 240 seconds, the Match tab is always present, and
    // its Open buttons are live throughout. Left running, the pending request
    // resolves against a panel that no longer belongs to it — replacing the
    // restored result, appending a history entry for a posting the reader never
    // chose, and (for verification) merging one job's content into another job's
    // stored record.
    abortRef.current?.abort();
    verifyAbortRef.current?.abort();
    abortRef.current = null;
    verifyAbortRef.current = null;

    setScanResult(restored);
    // The same value, not the raw stored one. `applyResult` composes onto this
    // ref and hands the composition to `onScanResultUpdate`, so the two holding
    // different values would write a mix of the pre-restore and post-restore
    // result into history.
    scanResultRef.current = restored;
    // A reopened scan has its own subject line, from the record rather than from
    // a capture that is no longer happening. Restoring these is what makes the
    // date show here as well as on a fresh scan — the two paths must not differ.
    setScannedAt(restoredJob.job.timestamp ?? null);
    setJobTitle(restoredJob.job.title ?? null);
    setHasScanned(true);
    setHasSelection(false);
    setScreenshots([]);
    setProgress(null);
    setCurrentSearchQuery('');
    setVerificationFailed(false);
    onScanProgressChange?.(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [restoredJob?.token]);

  const isValidJob = scanResult?.isJobPosting ?? false;

  /**
   * A posting that names no employer cannot be verified, so the panel asks for
   * the name instead of showing a checks section that will never fill. Scans are
   * always screenshots, so this is never about a missing image — it is about the
   * captured region not containing a logo, letterhead or sender.
   */
  const needsCompanyName = Boolean(
    isValidJob && scanResult && !scanResult.companyName && !scanResult.verificationLoading,
  );

  /**
   * Whether the employer lookup *ran*, as distinct from whether it changed the
   * reading.
   *
   * Read off the wire rather than off the score breakdown: the breakdown reports
   * which stages contributed a value, and the refutation stage contributes nothing
   * when it refutes nothing, so a lookup that ran and confirmed every claim is
   * indistinguishable there from one that never ran. That is the whole point of
   * returning `null` rather than 0, and reading it the other way round once told
   * readers their employer had not been checked when it had been.
   */
  const verificationRun: VerificationRun = (() => {
    const result = scanResult?.verificationResult;
    if (scanResult?.verificationError) return 'failed';
    if (!result) return 'never';
    if (result.searchOk === false) return 'failed';
    return result.items.some((item) => item.status === 'contradicted')
      ? 'refuted'
      : 'confirmed';
  })();

  /**
   * A settled stop or caution verdict drops the neutral context below the
   * findings. Derived from the same decision the panel's colour comes from, so
   * the emphasis and the tone can never disagree about whether this is dangerous.
   */
  const elevate = shouldElevateEvidence({
    verdict: scanResult?.verdict ?? null,
    verificationLoading: scanResult?.verificationLoading,
    offerAnalysisLoading: scanResult?.offerAnalysisLoading,
  });

  return {
    screenshots,
    hasSelection,
    isLoading,
    hasScanned,
    isValidJob,
    progress,
    progressPercent: progress?.percent ?? 0,
    scanResult,
    scannedAt,
    jobTitle,
    currentSearchQuery,
    verificationFailed,
    verificationRun,
    needsCompanyName,
    elevate,
    handleScreenshotReady,
    removeScreenshot,
    resetAll,
    handleSelectionChange,
    handleScan,
  };
}

/**
 * A stored scan, made displayable again.
 *
 * Two things change, and the reasons point opposite ways.
 *
 * The `*Loading` flags go. A job is written to history the moment its scan
 * returns — before verification has run — so `verificationLoading: true` is what
 * an unverified job genuinely stores, and restored as-is it renders "Verifying…"
 * forever.
 *
 * `verificationLoading` on a job with no result becomes `verificationError`, and
 * this is the subtle one. Clearing the flag alone leaves the panel with a company
 * name, no result and no error, which the checks section reads as "Search
 * completed and returned no results for this employer" — a claim about a search
 * that never ran, contradicting the reading directly above it. `error` renders as
 * "Verification could not be completed", whose body deliberately asserts neither
 * that the search failed nor that it succeeded. That is what happened.
 *
 * A `verificationError` that is already set is left alone: it records a lookup
 * that failed, and a reopened scan must still say so. Only a job whose
 * verification had not finished when it was saved is promoted into that state.
 */
export function restoreScanResult(result: ScanResult): ScanResult {
  const neverFinished = result.verificationLoading === true && !result.verificationResult;
  return {
    ...result,
    verificationLoading: false,
    offerAnalysisLoading: false,
    ...(neverFinished ? { verificationError: true } : {}),
  };
}
