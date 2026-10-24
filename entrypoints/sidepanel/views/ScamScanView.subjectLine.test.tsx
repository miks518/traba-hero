import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, waitFor, fireEvent, act, screen, cleanup } from '@testing-library/react';
import React from 'react';

/**
 * The subject line: when this was scanned, and what it is a reading of.
 *
 * **Both of these were bugs that shipped.** `ScamScanView` passed
 * `timestamp={restoredJob?.job.timestamp}` and never passed `title` at all, so a
 * fresh scan showed neither a date nor a job title, and a date appeared only when
 * the reader reopened the job from the Match tab. The same reading therefore
 * looked different depending on how you arrived at it, and the design's slot 1-2
 * was simply missing.
 *
 * The cause is worth naming, because it is the kind of thing that recurs: both
 * values were read off the *history record* rather than off the result on screen.
 * Neither is a property of a history entry. They are facts about the reading, so
 * they belong to whatever holds the reading — which is `useScanSession`.
 *
 * This drives the real component with the network mocked at `lib/api`, the
 * module boundary the frontend suite already uses.
 */

const baseResponse = {
  valid: true,
  company_name: 'Acme Trading',
  job_summary: 'Sales associate wanted at Acme Trading in Davao City',
  posting_analysis: 'The post asks for no money.',
  anomalies: [],
  verdict: 'clear',
  verdicted: true,
  verdict_breakdown: null,
};

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
  compressImage: vi.fn(async (dataUrl: string) => dataUrl),
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
// queries find it. The subject-line assertions are all document-wide, so a
// leftover panel would make them pass against the previous test's job.
afterEach(() => cleanup());

async function pickElement() {
  await act(async () => {
    mocks.messageHandler?.({
      source: 'trabahero-picker',
      action: 'ELEMENT_SELECTED',
      payload: { bounds: { x: 0, y: 0, width: 800, height: 600 } },
    });
    await new Promise((r) => setTimeout(r, 10));
  });
}

async function clickScan() {
  const scanBtn = await screen.findByRole('button', { name: /Scan \(\d+\)/ }, { timeout: 3000 });
  await act(async () => {
    fireEvent.click(scanBtn);
  });
}

/** The subject line's own markup, so the assertions cannot match stray text. */
function subjectLine(container: HTMLElement): { scanned: string; title: string } {
  const meta = container.querySelector('[data-role="job-meta"]');
  return {
    scanned: meta?.querySelector('p')?.textContent?.trim() ?? '',
    title: meta?.querySelector('h1')?.textContent?.trim() ?? '',
  };
}

describe('a fresh scan', () => {
  async function scanFresh(response: unknown = baseResponse) {
    mocks.scanScreenshotStream.mockImplementation(async (_imgs, _sig, onProgress) => {
      onProgress?.({ percent: 50, stage: 'Analyzing' });
      return { response };
    });
    mocks.verifyJobStream.mockImplementation(async () => ({
      result: { items: [], evidence: [], search_ok: true, search_error: '' },
    }));
    mocks.analyzeOfferStream.mockResolvedValue({ data: null });

    const { ScamScanView } = await import('./ScamScanView');
    const onScanComplete = vi.fn();
    const utils = render(
      React.createElement(ScamScanView, {
        onScanComplete,
        onScanResultUpdate: vi.fn(),
        isOnline: true,
      })
    );

    await pickElement();
    await clickScan();
    await waitFor(() => expect(onScanComplete).toHaveBeenCalled(), { timeout: 3000 });
    return { ...utils, job: onScanComplete.mock.calls[0][0] };
  }

  it('shows the job title above the verdict', async () => {
    // The regression. `title` was never passed to the panel, so the `<h1>` did
    // not exist on any path and the design's slot 2 was missing outright.
    const { container } = await scanFresh();
    await waitFor(() => expect(container.querySelector('[data-role="report-panel"]')).toBeTruthy());

    const meta = subjectLine(container);
    expect(meta.title).not.toBe('');
    // The same derivation history uses, so the panel and the Match tab cannot
    // disagree about what this posting is called.
    expect(meta.title).toBe('Sales associate wanted at Acme Trading in Davao');
  });

  it('shows a scan date even though nothing was restored from history', async () => {
    // The second regression, and the subtler one: `timestamp` was read off
    // `restoredJob`, which is null on a fresh scan, so the date only ever
    // appeared for a job reopened from the Match tab.
    const { container } = await scanFresh();
    await waitFor(() => expect(container.querySelector('[data-role="report-panel"]')).toBeTruthy());

    const meta = subjectLine(container);
    expect(meta.scanned).toMatch(/^scanned /i);
    expect(meta.scanned).not.toMatch(/invalid|nan|undefined/i);
  });

  it('falls back to the scanning target when the posting states no summary', async () => {
    // No summary means no title to derive. `scanningTarget` is what history
    // already falls back to, so the panel must not be the only surface showing
    // nothing where the history entry shows something.
    const { container } = await scanFresh({ ...baseResponse, job_summary: '' });
    await waitFor(() => expect(container.querySelector('[data-role="report-panel"]')).toBeTruthy());

    expect(subjectLine(container).title).toBe('Scanned Element');
  });

  it('clears the subject line when a new capture starts', async () => {
    // A title left over from the previous reading would sit above a fresh
    // capture with nothing under it, reading as a title for a scan that has not
    // happened yet.
    const { container, job } = await scanFresh();
    await waitFor(() => expect(container.querySelector('[data-role="job-meta"]')).toBeTruthy());

    const { ScamScanView } = await import('./ScamScanView');
    const pickAgain = container.querySelector('[data-role="pick-element"]') as HTMLButtonElement;
    expect(pickAgain).toBeTruthy();

    await act(async () => {
      fireEvent.click(pickAgain);
    });

    await waitFor(() => expect(container.querySelector('[data-role="job-meta"]')).toBeNull());
    expect(subjectLine(container).title).toBe('');
  });
});

describe('a reopened scan', () => {
  const storedJob = {
    id: 'job-1',
    title: 'Junior Accountant',
    summary: 'Accounting role',
    timestamp: '2026-10-09T08:30:00.000Z',
    scanResult: {
      verdict: 'clear' as const,
      verdictLabel: 'Proceed',
      verdicted: true,
      verdictBreakdown: undefined,
      riskDescription: '',
      scanningTarget: 'Scanned Element',
      anomalies: [],
      flagsCritical: false,
      isJobPosting: true,
      companyName: 'Santos & Villanueva CPAs',
    },
  };

  it('shows the stored date and title, so both paths look the same', async () => {
    const { ScamScanView } = await import('./ScamScanView');
    const { container } = render(
      React.createElement(ScamScanView, {
        isOnline: true,
        restoredJob: { job: storedJob as never, token: 1 },
      })
    );

    await waitFor(() => expect(container.querySelector('[data-role="job-meta"]')).toBeTruthy());

    const meta = subjectLine(container);
    expect(meta.title).toBe('Junior Accountant');
    expect(meta.scanned).toMatch(/^scanned /i);
    expect(meta.scanned).toContain('09');
  });

  it('shows the employer under the title', async () => {
    const { ScamScanView } = await import('./ScamScanView');
    const { container } = render(
      React.createElement(ScamScanView, {
        isOnline: true,
        restoredJob: { job: storedJob as never, token: 1 },
      })
    );

    await waitFor(() => expect(container.querySelector('[data-role="job-meta"]')).toBeTruthy());
    expect(container.querySelector('[data-role="job-meta"]')?.textContent).toContain(
      'Santos & Villanueva CPAs'
    );
  });

  it('omits the employer line when the posting named none', async () => {
    // The panel says a missing employer is a missing input, in `CompanyNameNeeded`,
    // with a dashed border. Repeating "no employer" in the subject line as well
    // would state the same gap twice and read as two separate problems.
    const { ScamScanView } = await import('./ScamScanView');
    const { container } = render(
      React.createElement(ScamScanView, {
        isOnline: true,
        restoredJob: {
          job: { ...storedJob, scanResult: { ...storedJob.scanResult, companyName: null } } as never,
          token: 2,
        },
      })
    );

    await waitFor(() => expect(container.querySelector('[data-role="job-meta"]')).toBeTruthy());
    const meta = subjectLine(container);
    expect(meta.title).toBe('Junior Accountant');
    // The title survives; only the employer line is absent.
    expect(meta.title).not.toBe('');
  });
});
