import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, waitFor, fireEvent, act, screen, cleanup } from '@testing-library/react';
import React from 'react';

/**
 * The capture prompt has to survive the first pick.
 *
 * It used to be an empty state keyed on `screenshots.length === 0`, so the
 * moment one image was captured the reader lost the only text that said more
 * images were allowed — the multi-pick affordance announced itself exactly
 * when it no longer mattered. The prompt now stands for the whole pre-scan
 * stretch, the primary button reads "Pick More" once something is captured,
 * and both leave together when there is a report to read.
 *
 * Drives the real component with the network mocked at `lib/api`, the module
 * boundary the frontend suite already uses.
 */

const baseResponse = {
  valid: true,
  company_name: 'Acme Trading',
  job_summary: 'Sales associate wanted',
  posting_analysis: 'The post asks for no money.',
  anomalies: [],
  risk_score: 0,
  risk_level: 'low',
  score_breakdown: null,
};

const mocks = vi.hoisted(() => ({
  scanScreenshotStream: vi.fn(),
  verifyJobStream: vi.fn(),
  analyzeOfferStream: vi.fn(),
  ApiRequestError: class extends Error { },
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

// This suite does not auto-cleanup between tests (see ScanActions.test.tsx);
// without this, each test's render stacks on the previous one and the queries
// see duplicated views.
afterEach(cleanup);

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

/** One ELEMENT_SELECTED message = one captured image on the pad. */
async function pickOnce() {
  await act(async () => {
    mocks.messageHandler?.({
      source: 'trabahero-picker',
      action: 'ELEMENT_SELECTED',
      payload: { bounds: { x: 0, y: 0, width: 800, height: 600 } },
    });
    await new Promise((r) => setTimeout(r, 10));
  });
}

async function renderView(onScanComplete?: (job: unknown) => void) {
  const { ScamScanView } = await import('./ScamScanView');
  return render(
    React.createElement(ScamScanView, {
      onScanComplete,
      onScanResultUpdate: vi.fn(),
      isOnline: true,
    })
  );
}

describe('the capture prompt survives the first pick', () => {
  it('announces the multi-pick limit before anything is captured', async () => {
    await renderView();
    expect(screen.getByText(/Select a job post from the page to scan and assess for anomalies. You can pick up to 4 images/)).toBeTruthy();
    expect(screen.getByRole('button', { name: /Pick a Job Post/ })).toBeTruthy();
  });

  it('stays on screen, and the button reads "Pick More", after one pick', async () => {
    await renderView();
    await pickOnce();

    expect(screen.getByText(/Select a job post from the page to scan and assess for anomalies. You can pick up to 4 images/)).toBeTruthy();
    expect(screen.getByRole('button', { name: /Pick More/ })).toBeTruthy();
  });

  it('stays on screen after a second pick', async () => {
    await renderView();
    await pickOnce();
    await pickOnce();

    expect(screen.getByText(/Select a job post from the page to scan and assess for anomalies. You can pick up to 4 images/)).toBeTruthy();
    // Both captures are on the pad, so the scan button counts them.
    expect(screen.getByRole('button', { name: /Scan \(2\)/ })).toBeTruthy();
  });

  it('leaves with the report once the scan settles', async () => {
    mocks.scanScreenshotStream.mockResolvedValue({ response: baseResponse });
    mocks.verifyJobStream.mockResolvedValue({
      result: { items: [], evidence: [], search_ok: true, search_error: '' },
    });
    mocks.analyzeOfferStream.mockResolvedValue({ data: null });

    const onScanComplete = vi.fn();
    await renderView(onScanComplete);
    await pickOnce();

    const scanBtn = await screen.findByRole('button', { name: /Scan \(1\)/ }, { timeout: 3000 });
    await act(async () => {
      fireEvent.click(scanBtn);
    });

    await waitFor(() => expect(onScanComplete).toHaveBeenCalled(), { timeout: 3000 });
    expect(screen.queryByText(/Select a job post from the page to scan and assess for anomalies. You can pick up to 4 images/)).toBeNull();
  });
});
