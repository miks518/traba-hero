import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, fireEvent, act, cleanup } from '@testing-library/react';
import React from 'react';

/**
 * Reopening a saved scan, and what it must not lose or overstate.
 *
 * Two things are cleared on restore and no others. A job is written to history
 * the moment its scan returns — before verification has run — so
 * `verificationLoading: true` is what an unverified job genuinely stores, and
 * restored as-is it renders "Verifying…" forever.
 *
 * `verificationError` is deliberately left alone. It records that a lookup
 * failed, and a reopened scan must still say so: clearing it to make the panel
 * look settled would hide a real outcome.
 *
 * happy-dom performs no layout, so nothing here asserts a rendered position.
 */

const mocks = vi.hoisted(() => ({
  scanScreenshotStream: vi.fn(),
  verifyJobStream: vi.fn(),
  analyzeOfferStream: vi.fn(),
  ApiRequestError: class extends Error {},
  messageHandler: null as null | ((m: unknown) => void),
}));

vi.mock('../lib/api', () => ({
  scanScreenshotStream: mocks.scanScreenshotStream,
  verifyJobStream: mocks.verifyJobStream,
  analyzeOfferStream: mocks.analyzeOfferStream,
  ApiRequestError: mocks.ApiRequestError,
}));

vi.mock('../lib/capture', () => ({
  captureElementRegion: vi.fn(),
  captureVisibleTab: vi.fn(),
  getZoom: vi.fn(),
}));

vi.mock('../lib/imageUtils', () => ({
  compressImage: vi.fn(async (d: string) => d),
}));

// Without this, one test's panel stays mounted and the next one's document-wide
// queries find it. The re-open test would read the previous job's anomaly off
// the leftover DOM, and the capture test would click the previous job's button
// — both pass or fail for reasons that have nothing to do with the code.
afterEach(() => cleanup());

beforeEach(() => {
  vi.clearAllMocks();
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

function storedJob(scanResult: Record<string, unknown>) {
  return {
    id: 'job-1',
    title: 'Sales associate wanted',
    summary: 'Sales role',
    timestamp: '2026-10-09T08:30:00.000Z',
    scanResult,
  };
}

describe('restoreScanResult', () => {
  it('clears the in-flight flag a saved job can carry', async () => {
    const { restoreScanResult } = await import('./ScamScanView');
    const restored = restoreScanResult(storedResult({ verificationLoading: true }) as never);

    expect(restored.verificationLoading).toBe(false);
  });

  it('clears the offer-analysis in-flight flag the same way', async () => {
    const { restoreScanResult } = await import('./ScamScanView');
    const restored = restoreScanResult(storedResult({ offerAnalysisLoading: true }) as never);

    expect(restored.offerAnalysisLoading).toBe(false);
  });

  it('keeps a real verification failure', async () => {
    // The inverse of the two above, and the reason they are cleared one at a
    // time rather than by dropping the whole result: a job whose lookup failed
    // must still say so when it is reopened.
    const { restoreScanResult } = await import('./ScamScanView');
    const restored = restoreScanResult(storedResult({ verificationError: true }) as never);

    expect(restored.verificationError).toBe(true);
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
    // `searchOk: false` is a completed search that could not complete. The
    // stored evidence is the outcome, so restore reports it rather than
    // presenting it as never having run.
    const { restoreScanResult } = await import('./ScamScanView');
    const failed = { items: [], evidence: [], searchOk: false, searchError: 'no key' };
    const restored = restoreScanResult(
      storedResult({ verificationResult: failed }) as never,
    );

    expect(restored.verificationResult?.searchOk).toBe(false);
    expect(restored.verificationError).not.toBe(true);
  });
});

describe('a reopened scan on screen', () => {
  async function renderRestored(job: unknown, onScanStart?: () => void) {
    const { ScamScanView } = await import('./ScamScanView');
    const props: Record<string, unknown> = {
      restoredJob: { job, token: 1 },
      isOnline: true,
    };
    if (onScanStart) props.onScanStart = onScanStart;
    const utils = render(React.createElement(ScamScanView, props as never));
    // `data-role="score-basis"` renders only in the results branch, so it is the
    // one unambiguous signal that the restore landed. "Pick again" is not:
    // `PickerButton` renders a second one as its content-script bridge.
    await waitFor(() =>
      expect(utils.container.querySelector('[data-role="score-basis"]')).toBeTruthy(),
    );
    return utils;
  }

  it('shows what the scan found', async () => {
    await renderRestored(storedJob(storedResult()));

    expect(
      await screen.findByText('Asks applicants to pay a processing fee'),
    ).toBeTruthy();
  });

  it('re-applies when the same job is opened again', async () => {
    const { ScamScanView } = await import('./ScamScanView');
    const first = storedJob(storedResult());

    const { rerender } = render(
      React.createElement(ScamScanView, {
        restoredJob: { job: first, token: 1 },
        isOnline: true,
      } as never),
    );
    await waitFor(() =>
      expect(document.querySelector('[data-role="score-basis"]')).toBeTruthy(),
    );

    // Same job, new token, and a fresh job *object* so this cannot pass by
    // accident on reference change. An effect keyed on the job would fire once
    // and never again, leaving the panel stale after the second Open.
    const second = storedJob(
      storedResult({
        anomalies: [
          {
            id: 'anomaly-0',
            title: 'Applies only through Messenger',
            description: 'No other channel is offered.',
            icon: 'warning' as const,
            severity: 'mid' as const,
          },
        ],
      }),
    );
    rerender(
      React.createElement(ScamScanView, {
        restoredJob: { job: second, token: 2 },
        isOnline: true,
      } as never),
    );

    expect(await screen.findByText('Applies only through Messenger')).toBeTruthy();
    expect(screen.queryByText('Asks applicants to pay a processing fee')).toBeNull();
  });

  it('shows no thumbnails, because screenshots are not stored', async () => {
    const { container } = await renderRestored(storedJob(storedResult()));

    // Not a bug to be fixed. The manifest has no `unlimitedStorage`, so
    // storing images would blow the 5MB budget within ten scans and Chrome
    // fails those writes silently.
    const images = Array.from(container.querySelectorAll('img')).filter((i) =>
      (i.getAttribute('src') ?? '').startsWith('data:'),
    );
    expect(images).toHaveLength(0);
  });

  it('reports the start of a fresh capture', async () => {
    // The app bar marker claims the panel is showing a saved result. Without
    // this it would still be claiming that after the reader took a new capture,
    // which is the one thing it must never do.
    const onScanStart = vi.fn();
    await renderRestored(storedJob(storedResult()), onScanStart);

    await act(async () => {
      // Named by data-role rather than by label: `PickerButton` renders a second
      // "Pick again" as its content-script bridge, and that one does not start
      // a capture — it activates an overlay. The action bar's is the real one.
      fireEvent.click(document.querySelector('[data-role="pick-element"]')!);
    });

    expect(onScanStart).toHaveBeenCalledTimes(1);
  });
});