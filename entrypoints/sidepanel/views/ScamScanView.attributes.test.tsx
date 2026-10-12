import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, waitFor, fireEvent, act, screen } from '@testing-library/react';
import React from 'react';

/**
 * The posting's own stated claims must survive into history.
 *
 * `ScanResponse` already carries `attributes` and `search_queries`, and the
 * frontend already forwards them to `/api/verify` because the backend quotes
 * them back to the model as the claims its categories test. `ScanResult` drops
 * both, so a scan reopened from history keeps its conclusions and loses the
 * ground they were drawn from — a `Channel Match` failure with no record of
 * the channel the posting claimed.
 *
 * This drives the real component with the network mocked at `lib/api`, the
 * module boundary the frontend suite already uses.
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
  email_verifications: [],
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

vi.mock('../lib/imageUtils', () => ({
  compressImage: vi.fn(async (dataUrl: string) => dataUrl),
}));

/** Run a real scan whose mocked response is `response`, return the saved job. */
async function scanAndSave(response: unknown) {
  mocks.scanScreenshotStream.mockImplementation(async (_imgs, _sig, onProgress) => {
    onProgress?.({ percent: 50, stage: 'Analyzing' });
    return { response };
  });
  mocks.verifyJobStream.mockImplementation(async () => {
    await new Promise((r) => setTimeout(r, 5));
    return { result: { items: [], evidence: [], search_ok: true, search_error: '' } };
  });
  mocks.analyzeOfferStream.mockResolvedValue({ data: null });

  const { ScamScanView } = await import('./ScamScanView');
  const onScanComplete = vi.fn();

  render(
    React.createElement(ScamScanView, {
      onScanComplete,
      onScanResultUpdate: vi.fn(),
      isOnline: true,
    })
  );

  await pickElement();
  await clickScan();

  await waitFor(() => expect(onScanComplete).toHaveBeenCalled(), { timeout: 3000 });
  return onScanComplete.mock.calls[0][0];
}

describe("a reopened scan keeps the posting's claims", () => {
  it('carries the posting stated claims into history', async () => {
    const job = await scanAndSave({
      ...baseResponse,
      attributes: { LOCATION: 'Davao City office', CONTACT_METHOD: 'Messenger' },
      search_queries: ['Acme Trading branches Davao'],
    });

    expect(job.scanResult.attributes).toEqual({
      LOCATION: 'Davao City office',
      CONTACT_METHOD: 'Messenger',
    });
    expect(job.scanResult.searchQueries).toEqual(['Acme Trading branches Davao']);
  });

  it('omits the claims entirely when the scan reports none', async () => {
    // An empty object would render as "the posting claimed nothing", which is a
    // claim about the posting. What is true is that we have nothing to show.
    const job = await scanAndSave({ ...baseResponse });

    expect(job.scanResult.attributes).toBeUndefined();
    expect(job.scanResult.searchQueries).toBeUndefined();
  });
});