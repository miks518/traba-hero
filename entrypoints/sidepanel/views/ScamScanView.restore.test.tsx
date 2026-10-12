import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, fireEvent, act, cleanup } from '@testing-library/react';
import React from 'react';

/**
 * Reopening a saved scan, and what it must not lose, overstate, or corrupt.
 *
 * Two `*Loading` flags are cleared and one is rewritten. A job is written to
 * history the moment its scan returns — before verification has run — so a
 * stored `true` means "was in flight when saved" and renders a spinner that
 * never stops. And `verificationLoading` on a job with no result becomes
 * `verificationError`, because clearing it alone leaves the panel claiming a
 * search completed and found nothing, for a search that never ran.
 *
 * A stored `verificationError` is left alone: it records a lookup that failed,
 * and a reopened scan must still say so.
 *
 * happy-dom performs no layout, so nothing here asserts a rendered position.
 */

const mocks = vi.hoisted(() => ({
  scanScreenshotStream: vi.fn(),
  verifyJobStream: vi.fn(),
  analyzeOfferStream: vi.fn(),
  ApiRequestError: class extends Error {},
  captureElementRegion: vi.fn(),
  messageHandler: null as null | ((m: unknown) => void),
}));

vi.mock('../lib/api', () => ({
  scanScreenshotStream: mocks.scanScreenshotStream,
  verifyJobStream: mocks.verifyJobStream,
  analyzeOfferStream: mocks.analyzeOfferStream,
  ApiRequestError: mocks.ApiRequestError,
}));

vi.mock('../lib/capture', () => ({
  captureElementRegion: mocks.captureElementRegion,
  captureVisibleTab: vi.fn(),
  getZoom: vi.fn(),
}));

vi.mock('../lib/imageUtils', () => ({
  compressImage: vi.fn(async (d: string) => d),
}));

beforeEach(() => {
  vi.clearAllMocks();
  mocks.captureElementRegion.mockResolvedValue('data:image/jpeg;base64,SCREENSHOT');

  (globalThis as unknown as { browser: unknown }).browser = {
    runtime: {
      onMessage: {
        addListener: (h: (m: unknown) => void) => {
          mocks.messageHandler = h;
        },
        removeListener: vi.fn(),
        send: vi.fn(),
      },
    },
    tabs: {
      query: vi.fn().mockResolvedValue([{ id: 1, windowId: 1 }]),
      sendMessage: vi.fn().mockResolvedValue(undefined),
    },
    storage: { local: { get: vi.fn().mockResolvedValue({}), set: vi.fn() } },
  };
});

// Without this, one test's panel stays mounted and the next one's document-wide
// queries find it. The re-open test would read the previous job's anomaly off
// the leftover DOM, and the capture test would click the previous job's button
// — both pass or fail for reasons that have nothing to do with the code.
afterEach(() => cleanup());

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

function storedJob(scanResult: Record<string, unknown>, id = 'job-1') {
  return {
    id,
    title: 'Sales associate wanted',
    summary: 'Sales role',
    timestamp: '2026-10-09T08:30:00.000Z',
    scanResult,
  };
}

async function renderScam(props: Record<string, unknown> = {}) {
  const { ScamScanView } = await import('./ScamScanView');
  const view = (over: Record<string, unknown>) =>
    React.createElement(ScamScanView, { isOnline: true, ...props, ...over } as never);
  const utils = render(view({}));
  return { ...utils, view, rerenderWith: (over: Record<string, unknown>) => utils.rerender(view(over)) };
}

/** Wait for the results branch, which only renders once a scan is on screen. */
async function waitForResults(container: HTMLElement) {
  await waitFor(() =>
    expect(container.querySelector('[data-role="score-basis"]')).toBeTruthy(),
  );
}

/** Run the real capture flow so the panel holds screenshots to clear. */
async function scanSomething(container: HTMLElement) {
  mocks.scanScreenshotStream.mockResolvedValue({
    response: {
      valid: true,
      company_name: '',
      anomalies: [],
      risk_score: 10,
      risk_level: 'low',
      email_verifications: [],
    },
  });
  mocks.analyzeOfferStream.mockResolvedValue({ data: null });

  await act(async () => {
    mocks.messageHandler?.({
      source: 'trabahero-picker',
      action: 'ELEMENT_SELECTED',
      payload: { bounds: { x: 0, y: 0, width: 800, height: 600 } },
    });
    await new Promise((r) => setTimeout(r, 20));
  });
  const btn = await screen.findByRole('button', { name: /Scan \(\d+\)/ }, { timeout: 3000 });
  await act(async () => {
    fireEvent.click(btn);
  });
  await waitForResults(container);
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
    // completed and found nothing — for a search that never ran, and against
    // the score line directly above it saying the employer was not checked.
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

describe('a reopened scan on screen', () => {
  it('shows what the scan found', async () => {
    const { container } = await renderScam({
      restoredJob: { job: storedJob(storedResult()), token: 1 },
    });
    await waitForResults(container);

    expect(await screen.findByText('Asks applicants to pay a processing fee')).toBeTruthy();
  });

  it('re-applies when the same job is opened again', async () => {
    // The *same* job object with a new token — what a second press of Open on
    // one row actually sends. A fresh object would let an effect keyed on the
    // job pass this test, because React compares dependencies by reference.
    //
    // Observable: the scroll reset runs again. Nothing about the panel's
    // *content* changes when the same job is restored, so the content cannot
    // tell a re-apply from a no-op.
    const job = storedJob(storedResult());
    const { container, rerenderWith } = await renderScam({
      restoredJob: { job, token: 1 },
    });
    await waitForResults(container);

    // Stand in for the reader having scrolled down since the first open.
    const scroller = document.scrollingElement as HTMLElement & { scrollTop: number };
    scroller.scrollTop = 500;

    rerenderWith({ restoredJob: { job, token: 2 } });

    await waitFor(() => expect(scroller.scrollTop).toBe(0));
  });

  it('does not claim a search completed when none ever ran', async () => {
    // The heading that matters here. "Searched, found nothing" asserts a
    // completed search over an employer with no online footprint, which reads
    // as a clean check on a check that never happened.
    const { container } = await renderScam({
      restoredJob: {
        job: storedJob(storedResult({ verificationLoading: true })),
        token: 1,
      },
    });
    await waitForResults(container);

    expect(screen.queryByText('Searched, found nothing')).toBeNull();
    expect(screen.getByText('Verification could not be completed')).toBeTruthy();
  });

  it('drops the thumbnails of a scan it replaces', async () => {
    // Thumbnails are not persisted, so a restored scan has none. Only a panel
    // that genuinely has some can test that: a fresh mount starts empty and
    // would pass whether or not restore cleared anything.
    const { container, rerenderWith } = await renderScam({});
    await scanSomething(container);
    expect(container.querySelectorAll('img[src^="data:"]').length).toBeGreaterThan(0);

    rerenderWith({ restoredJob: { job: storedJob(storedResult()), token: 1 } });
    await waitForResults(container);

    expect(container.querySelectorAll('img[src^="data:"]').length).toBe(0);
  });

  it('reports the start of a fresh capture', async () => {
    // The app bar marker claims the panel is showing a saved result. Without
    // this it would still be claiming that after the reader took a new capture,
    // which is the one thing it must never do.
    const onScanStart = vi.fn();
    const { container } = await renderScam({
      restoredJob: { job: storedJob(storedResult()), token: 1 },
      onScanStart,
    });
    await waitForResults(container);

    await act(async () => {
      // Named by data-role rather than by label: `PickerButton` renders a second
      // "Pick again" as its content-script bridge, and that one activates an
      // overlay rather than starting a capture.
      fireEvent.click(document.querySelector('[data-role="pick-element"]')!);
    });

    expect(onScanStart).toHaveBeenCalledTimes(1);
  });
});

describe('reopening a scan while another is still running', () => {
  it('does not let a late scan overwrite the reopened one', async () => {
    // Reachable in one click: a scan takes up to 240 seconds, the Match tab is
    // always there, and its Open buttons are live throughout. Without an abort
    // the pending request resolves afterwards, replaces the restored panel, and
    // appends a *second* history entry for a posting the reader never chose.
    let release: (v: unknown) => void = () => {};
    // Respects the signal, as the real stream does. A mock that ignores it
    // would let the request complete after an abort, which is precisely the
    // bug this test exists to catch — so ignoring it would make the test pass
    // by disabling the thing it is testing.
    mocks.scanScreenshotStream.mockImplementation(
      (_imgs: unknown, signal: AbortSignal) =>
        new Promise((res, rej) => {
          release = res;
          signal?.addEventListener('abort', () =>
            rej(new DOMException('aborted', 'AbortError')),
          );
        }),
    );
    const onScanComplete = vi.fn();

    const { container, rerenderWith } = await renderScam({ onScanComplete });
    await act(async () => {
      mocks.messageHandler?.({
        source: 'trabahero-picker',
        action: 'ELEMENT_SELECTED',
        payload: { bounds: { x: 0, y: 0, width: 800, height: 600 } },
      });
      await new Promise((r) => setTimeout(r, 20));
    });
    const btn = await screen.findByRole('button', { name: /Scan \(\d+\)/ }, { timeout: 3000 });
    await act(async () => {
      fireEvent.click(btn);
    });

    rerenderWith({ restoredJob: { job: storedJob(storedResult()), token: 1 } });
    await waitForResults(container);

    // Now let the abandoned request answer, as a real one would.
    await act(async () => {
      release({ response: { valid: true, company_name: 'Late Co', anomalies: [], risk_score: 90, risk_level: 'critical', email_verifications: [] } });
      await new Promise((r) => setTimeout(r, 20));
    });

    expect(onScanComplete).not.toHaveBeenCalled();
    expect(container.textContent).toContain('Asks applicants to pay a processing fee');
  });

  it('does not write an abandoned verification onto either job', async () => {
    // The worse half. `startVerification` captures the *old* job's id but reads
    // the current result off a ref, so a late reply merges the new job's
    // content into the old job's history entry. And the abort lands in the
    // catch, which records a *failed* verification — so aborting without also
    // making the aborted path discard would write a fabricated outcome.
    mocks.scanScreenshotStream.mockResolvedValue({
      response: {
        valid: true,
        company_name: 'Acme Trading',
        job_summary: 'Sales associate wanted',
        verification_context: {
          company_name: 'Acme Trading',
          job_summary: 'Sales associate wanted',
        },
        anomalies: [],
        risk_score: 10,
        risk_level: 'low',
        email_verifications: [],
      },
    });
    mocks.verifyJobStream.mockImplementation(
      (_ctx: unknown, signal: AbortSignal) =>
        new Promise((_res, rej) => {
          signal.addEventListener('abort', () =>
            rej(new DOMException('aborted', 'AbortError')),
          );
        }),
    );
    const onScanResultUpdate = vi.fn();

    const { container, rerenderWith } = await renderScam({ onScanResultUpdate });
    await act(async () => {
      mocks.messageHandler?.({
        source: 'trabahero-picker',
        action: 'ELEMENT_SELECTED',
        payload: { bounds: { x: 0, y: 0, width: 800, height: 600 } },
      });
      await new Promise((r) => setTimeout(r, 20));
    });
    const btn = await screen.findByRole('button', { name: /Scan \(\d+\)/ }, { timeout: 3000 });
    await act(async () => {
      fireEvent.click(btn);
    });
    await waitFor(() => expect(mocks.verifyJobStream).toHaveBeenCalled());
    onScanResultUpdate.mockClear();

    rerenderWith({ restoredJob: { job: storedJob(storedResult(), 'job-2'), token: 1 } });
    await waitForResults(container);
    await act(async () => {
      await new Promise((r) => setTimeout(r, 30));
    });

    expect(onScanResultUpdate).not.toHaveBeenCalled();
  });
});