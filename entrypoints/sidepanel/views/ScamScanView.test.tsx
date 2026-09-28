import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent, act } from '@testing-library/react';
import React from 'react';

/**
 * The panel and the history entry must agree on one score.
 *
 * A scan is saved to history the moment it returns, before external
 * verification has run. Verification then blends an employer score into the
 * posting score — a clean posting at 0 with a yellow-only lookup becomes
 * round(0 * 0.6 + 30 * 0.4) = 12 — so without an update the same posting reads
 * as 12 in the panel and 0 in the history list.
 *
 * This drives the real component with the network mocked at lib/api, the
 * module boundary the frontend suite already uses. The helper in scanHistory
 * has its own unit tests; only a component test can catch the wiring, since a
 * correct helper that nothing calls still shows the bug.
 */

const scanResponse = {
  valid: true,
  company_name: 'Acme Trading',
  job_summary: 'Sales associate wanted',
  posting_analysis: 'The post asks for no money.',
  red_flags: [],
  verification_context: {
    company_name: 'Acme Trading',
    job_summary: 'Sales associate wanted',
  },
  // The posting stage alone: no flags, so nothing to score.
  risk_score: 0,
  risk_level: 'low',
  score_breakdown: null,
  email_verifications: [],
};

const verifyResponse = {
  items: [
    { label: 'Company Existence', status: 'green', explanation: 'Has a website.', source_title: '', source_url: '' },
    { label: 'Official Registration', status: 'yellow', explanation: 'No registration in the results.', source_title: '', source_url: '' },
    { label: 'Reputation', status: 'yellow', explanation: 'No reports in the results.', source_title: '', source_url: '' },
  ],
  evidence: [],
  report: 'The results show a website.',
  recommendation: 'Ask the employer to confirm details in writing.',
  riskScore: 12,
  riskLevel: 'low',
  scoreBreakdown: null,
  search_ok: true,
  search_error: '',
  search_count: 2,
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

// The picker captures the region through the extension APIs, which do not
// exist here. Stubbed at that boundary rather than by mocking the component,
// so the real message -> state -> scan path still runs.
vi.mock('../lib/capture', () => ({
  captureElementRegion: mocks.captureElementRegion,
  captureVisibleTab: vi.fn(),
  getZoom: vi.fn(),
}));

// PickerButton subscribes to browser.runtime.onMessage on mount, and the whole
// scan flow starts from a picker selection. The handler is captured from the
// stub so the test drives the same message the content script sends.
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

/**
 * Deliver a picker selection the way the content script does.
 *
 * The click is not needed to reach the handler: PickerButton subscribes on
 * mount and accepts an ELEMENT_SELECTED message in any state. Clicking first
 * only makes the test wait on a round trip to a content script that is not
 * running here.
 */
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
  // The button's accessible name includes the icon's text, so match on the
  // label rather than anchoring to the start of the string.
  const scanBtn = await screen.findByRole('button', { name: /Scan \(\d+\)/ }, { timeout: 3000 });
  await act(async () => {
    fireEvent.click(scanBtn);
  });
}

// happy-dom's canvas has no 2d context, so the real compressor cannot run.
// Mocked as a pass-through: image compression is not what this test is about,
// and the screenshot must still reach state for the scan to be reachable.
vi.mock('../lib/imageUtils', () => ({
  compressImage: vi.fn(async (dataUrl: string) => dataUrl),
}));

describe('score stays in sync between the panel and history', () => {
  beforeEach(() => {
    // The scanner is a plain async function returning { response }, not a
    // generator; it reports progress through the onProgress callback.
    mocks.scanScreenshotStream.mockImplementation(async (_imgs, _sig, onProgress) => {
      onProgress?.({ percent: 50, stage: 'Analyzing' });
      return { response: scanResponse };
    });
    mocks.verifyJobStream.mockImplementation(async () => {
      await new Promise((r) => setTimeout(r, 5));
      return { result: verifyResponse };
    });
    mocks.analyzeOfferStream.mockResolvedValue({ data: null });
  });

  it('hands the parent the blended score once verification finishes', async () => {
    const { ScamScanView } = await import('./ScamScanView');
    const onScanComplete = vi.fn();
    const onScanResultUpdate = vi.fn();

    render(
      React.createElement(ScamScanView, {
        onScanComplete,
        onScanResultUpdate,
        isOnline: true,
      })
    );

    await pickElement();
    await clickScan();

    // Saved with the posting-stage score, before verification has run.
    await waitFor(() => expect(onScanComplete).toHaveBeenCalled());
    const saved = onScanComplete.mock.calls[0][0];
    expect(saved.scanResult.riskScore).toBe(0);

    // Then the parent is told about the blended score, for the same job.
    await waitFor(() => expect(onScanResultUpdate).toHaveBeenCalled(), { timeout: 3000 });
    const [jobId, updated] = onScanResultUpdate.mock.calls[0];
    expect(jobId).toBe(saved.id);
    expect(updated.riskScore).toBe(12);
  });

  it('still tells the parent when verification fails, so no spinner is stranded', async () => {
    const { ScamScanView } = await import('./ScamScanView');
    const onScanResultUpdate = vi.fn();
    // Set after beforeEach, which installs the success implementation.
    mocks.verifyJobStream.mockRejectedValue(new Error('network down'));

    render(
      React.createElement(ScamScanView, {
        onScanComplete: vi.fn(),
        onScanResultUpdate,
        isOnline: true,
      })
    );

    await pickElement();
    await clickScan();

    await waitFor(() => expect(onScanResultUpdate).toHaveBeenCalled(), { timeout: 3000 });
    const [, updated] = onScanResultUpdate.mock.calls[0];
    expect(updated.verificationLoading).toBe(false);
    expect(updated.verificationError).toBe(true);
    // The posting score still stands, so history keeps a real number.
    expect(updated.riskScore).toBe(0);
  });
});
