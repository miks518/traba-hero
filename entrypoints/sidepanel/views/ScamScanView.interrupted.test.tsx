import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, waitFor, fireEvent, act, screen, cleanup } from '@testing-library/react';
import React from 'react';

/**
 * An interrupted verification: the run must stop presenting itself as in
 * progress.
 *
 * **The shipped failure.** A failed lookup set a sticky session flag
 * (`verificationFailed`) and `ScamScanView` folded that flag back into the
 * `verifying` prop alongside the real in-flight flags. The card reading
 * `result.verificationLoading` stopped its spinner, but the banner kept
 * "Checking this job post" with its "In progress" ping forever, and
 * `WhatWeChecked` kept the loading heading and spinner card *above* the honest
 * error sentence — a panel that reads as a check that never finished.
 *
 * The root cause is one boolean carrying two distinct states: "in flight" and
 * "failed". These tests drive the real component with the network mocked at
 * `lib/api`, the module boundary the frontend suite already uses, so the
 * sticky-hidden fix at the ScamScanView seam is what has to make them pass.
 */

const baseResponse = {
  valid: true,
  company_name: 'Acme Trading',
  // The follow-up stage reads its context from here, not from company_name —
  // without it the verification never starts and the test exercises nothing.
  verification_context: {
    company_name: 'Acme Trading',
    job_summary: 'Sales associate wanted at Acme Trading in Davao City',
  },
  job_summary: 'Sales associate wanted at Acme Trading in Davao City',
  posting_analysis: 'The post asks for no money.',
  anomalies: [],
  assessment: 'clear',
  assessed: true,
  assessment_breakdown: null,
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
// queries find it.
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

async function scanWithInterruptedVerify() {
  mocks.scanScreenshotStream.mockImplementation(async (_imgs, _sig, onProgress) => {
    onProgress?.({ percent: 50, stage: 'Analyzing' });
    return { response: baseResponse };
  });
  // The lookup dies mid-flight — a broken stream, a 429, a dropped connection.
  // The scan itself completed; the interruption is in the verify stage.
  mocks.verifyJobStream.mockRejectedValue(new Error('connection reset'));
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
  return utils;
}

describe('an interrupted verification', () => {
  it('says the run was interrupted instead of checking forever', async () => {
    const { container } = await scanWithInterruptedVerify();
    await waitFor(
      () => expect(container.querySelector('[data-role="assessment-headline"]')).toBeTruthy(),
    );

    expect(container.querySelector('[data-role="assessment-headline"]')?.textContent).toBe(
      'Scan has been interrupted, please try again',
    );
  });

  it('carries the interrupted copy as a state of the output, not a finding about the employer', async () => {
    const { container } = await scanWithInterruptedVerify();
    await waitFor(
      () => expect(container.querySelector('[data-role="assessment-headline"]')).toBeTruthy(),
    );

    // The interrupted banner is a statement about the system's output, so it
    // must not borrow a colour that describes the posting.
    expect(container.querySelector('[data-role="assessment-block"]')?.getAttribute('data-tone')).toBe(
      'unknown',
    );
  });

  it('stops the loading animation on every layer of the report', async () => {
    const { container } = await scanWithInterruptedVerify();
    await waitFor(
      () => expect(container.querySelector('[data-role="assessment-headline"]')).toBeTruthy(),
    );

    // The banner's "In progress" ping must go, and the checks section must stop
    // presenting itself as still searching.
    expect(container.textContent).not.toContain('In progress');
    expect(container.textContent).not.toContain('Checking this job post');
    const whatWeChecked = container.querySelector('[data-role="what-we-checked"]');
    expect(whatWeChecked).toBeTruthy();
    expect(whatWeChecked?.querySelectorAll('.animate-spin, .animate-ping').length).toBe(0);
  });
});
