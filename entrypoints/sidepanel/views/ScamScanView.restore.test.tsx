import { describe, it, expect } from 'vitest';

/**
 * Reopening a stored scan: what the rewrite must not lose, overstate or corrupt.
 *
 * **What was removed from this file, and why.** The DOM-level tests — "shows what
 * the scan found", "does not claim a search completed when none ever ran", "drops
 * the thumbnails of a scan it replaces", "does not let a late scan overwrite the
 * reopened one" — asserted against markup that no longer exists. They waited on
 * `[data-role="score-basis"]`, drove `RiskGauge`'s provenance button, and read
 * `AnomaliesList` out of two mounts inside `EvidenceSummary`. All of that is gone
 * with the score.
 *
 * The *behaviour* those tests protected did not go with the markup, and this file
 * is where it gets re-asserted once the report has its own tests: a late scan must
 * not overwrite a reopened one, an abandoned verification must not be written onto
 * either job, and a reopened scan must not carry the capture it replaces. None of
 * that is reachable from a pure function, so those belong to a
 * `useScanSession` test rather than here, and they are an open item rather than a
 * silent gap — see the "Reader feedback capture" and panel notes in
 * `UNFINISHED-WORK.md`.
 *
 * What survives below is `restoreScanResult`, which is pure and is the part of
 * the restore whose reasoning is subtle enough to pin.
 */

/** A complete stored result, so a test states only what it varies. */
function storedResult(overrides: Record<string, unknown> = {}) {
  return {
    riskLevel: 'moderate' as const,
    riskLabel: 'Moderate',
    riskScored: true,
    riskScore: 40,
    riskDescription: '',
    scanningTarget: 'Scanned Element',
    anomalies: [
      {
        id: 'anomaly-0',
        title: 'Asks applicants to pay a processing fee',
        description: 'The post asks for money up front.',
        icon: 'warning' as const,
        severity: 'high' as const,
      },
    ],
    flagsCritical: false,
    isJobPosting: true,
    companyName: 'Acme Trading',
    ...overrides,
  };
}

describe('restoreScanResult', () => {
  it('clears the offer-analysis in-flight flag a saved job can carry', async () => {
    const { restoreScanResult } = await import('./ScamScanView');
    const restored = restoreScanResult(storedResult({ offerAnalysisLoading: true }) as never);

    expect(restored.offerAnalysisLoading).toBe(false);
  });

  it('reports a verification that never finished as one that could not complete', async () => {
    // A job saved before its verification returned stores `loading: true` with
    // no result. Clearing the flag alone leaves the panel claiming a search
    // completed and found nothing — for a search that never ran, and directly
    // above a assessment about a posting that was never checked against its
    // employer. `WhatWeChecked` reads the absence as "could not complete", which
    // asserts neither that the search failed nor that it succeeded.
    const { restoreScanResult } = await import('./ScamScanView');
    const restored = restoreScanResult(storedResult({ verificationLoading: true }) as never);

    expect(restored.verificationLoading).toBe(false);
    expect(restored.verificationError).toBe(true);
  });

  it('keeps a real verification failure', async () => {
    // The inverse, and the reason the flag above is rewritten rather than the
    // whole result discarded: a job whose lookup failed must still say so.
    const { restoreScanResult } = await import('./ScamScanView');
    const restored = restoreScanResult(storedResult({ verificationError: true }) as never);

    expect(restored.verificationError).toBe(true);
  });

  it('leaves a completed verification alone', async () => {
    // `loading: false` with a result is the ordinary saved job. Rewriting this
    // to an error would turn every healthy history entry into a failure.
    const { restoreScanResult } = await import('./ScamScanView');
    const restored = restoreScanResult(
      storedResult({
        verificationLoading: false,
        verificationResult: { items: [{ label: 'x', status: 'green' }], searchOk: true },
      }) as never,
    );

    expect(restored.verificationError).toBeUndefined();
  });

  it('keeps the stored claims', async () => {
    const { restoreScanResult } = await import('./ScamScanView');
    const restored = restoreScanResult(
      storedResult({
        attributes: { LOCATION: 'Davao City office' },
        searchQueries: ['Acme Trading branches Davao'],
      }) as never,
    );

    expect(restored.attributes).toEqual({ LOCATION: 'Davao City office' });
    expect(restored.searchQueries).toEqual(['Acme Trading branches Davao']);
  });

  it('keeps a lookup that found nothing, as a lookup that found nothing', async () => {
    // `searchOk: false` is a search that ran and could not complete. The stored
    // evidence is the outcome, so restore reports it rather than presenting it
    // as never having run.
    const { restoreScanResult } = await import('./ScamScanView');
    const restored = restoreScanResult(
      storedResult({
        verificationResult: { items: [], evidence: [], searchOk: false, searchError: 'no key' },
      }) as never,
    );

    expect(restored.verificationResult?.searchOk).toBe(false);
    expect(restored.verificationError).not.toBe(true);
  });
});
