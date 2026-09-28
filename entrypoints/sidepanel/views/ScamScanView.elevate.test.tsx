import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, act, fireEvent, cleanup } from '@testing-library/react';
import React from 'react';

/**
 * A high or critical score must lead with the evidence.
 *
 * The reader's first question about a dangerous posting is "why", and the
 * answer is the red flags and the employer check. When the panel opens on
 * "Posting Analysis" and "Job Summary" instead, the two blocks that explain the
 * score are pushed below the fold of a 380px side panel.
 *
 * These assert the ORDER and the accent, which is what can be verified here.
 * happy-dom reports every rect as 0, so the FLIP animation itself computes no
 * deltas and snaps; that it looks fluid is not something this environment can
 * check, and pretending otherwise would be a test that proves nothing.
 */

const scanResponse = {
  valid: true,
  company_name: 'Acme Trading',
  job_summary: 'Sales associate wanted',
  posting_analysis: 'The post asks for no money before work.',
  red_flags: [
    { flag: 'Asks applicants to pay a processing fee', reasoning: 'The post asks for a fee', severity: 'high' },
  ],
  verification_context: { company_name: 'Acme Trading', job_summary: 'Sales associate wanted' },
  risk_score: 76,
  risk_level: 'critical',
  score_breakdown: { posting: 40, verification: 30, sources: ['posting', 'verification'] },
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
  riskScore: 76,
  riskLevel: 'critical',
  scoreBreakdown: { posting: 40, verification: 30, sources: ['posting', 'verification'] },
  search_ok: true,
  search_error: '',
  search_count: 2,
};

const mocks = vi.hoisted(() => ({
  scanScreenshotStream: vi.fn(),
  verifyJobStream: vi.fn(),
  analyzeOfferStream: vi.fn(),
  captureElementRegion: vi.fn(),
  messageHandler: null as null | ((m: unknown) => void),
}));

vi.mock('../lib/api', () => ({
  scanScreenshotStream: mocks.scanScreenshotStream,
  verifyJobStream: mocks.verifyJobStream,
  analyzeOfferStream: mocks.analyzeOfferStream,
  ApiRequestError: class extends Error {},
}));

vi.mock('../lib/capture', () => ({ captureElementRegion: mocks.captureElementRegion }));
vi.mock('../lib/imageUtils', () => ({ compressImage: vi.fn(async (d: string) => d) }));

beforeEach(() => {
  vi.clearAllMocks();
  mocks.captureElementRegion.mockResolvedValue('data:image/jpeg;base64,SHOT');
  (globalThis as unknown as { browser: unknown }).browser = {
    runtime: {
      onMessage: {
        addListener: (h: (m: unknown) => void) => { mocks.messageHandler = h; },
        removeListener: vi.fn(),
        send: vi.fn(),
      },
    },
    tabs: { query: vi.fn().mockResolvedValue([{ id: 1, windowId: 1 }]), sendMessage: vi.fn() },
    storage: { local: { get: vi.fn().mockResolvedValue({}), set: vi.fn() } },
  };
  mocks.scanScreenshotStream.mockImplementation(async (_i, _s, onProgress) => {
    onProgress?.({ percent: 50, stage: 'Analyzing' });
    return { response: scanResponse };
  });
  mocks.verifyJobStream.mockImplementation(async () => {
    await new Promise((r) => setTimeout(r, 5));
    return { result: verifyResponse };
  });
  mocks.analyzeOfferStream.mockResolvedValue({ data: null });
});

/**
 * Drive the picker and a scan, then wait for the result to land.
 *
 * Waits on a red flag rather than the job summary: the summary text also
 * appears in the verification context, so a query on it matches twice and
 * reports a false failure.
 */
async function scanAndSettle() {
  await act(async () => {
    mocks.messageHandler?.({
      source: 'trabahero-picker',
      action: 'ELEMENT_SELECTED',
      payload: { bounds: { x: 0, y: 0, width: 800, height: 600 } },
    });
    await new Promise((r) => setTimeout(r, 10));
  });
  const scanBtn = await screen.findByRole('button', { name: /Scan \(\d+\)/ }, { timeout: 3000 });
  await act(async () => { fireEvent.click(scanBtn); });
  await waitFor(
    () => expect(screen.getByText(/Asks applicants to pay a processing fee/)).toBeTruthy(),
    { timeout: 3000 }
  );
}

afterEach(() => {
  // Without this, the next test's render stacks onto this one and every text
  // query matches twice.
  cleanup();
});

describe('evidence leads for a high or critical score', () => {
  it('puts the evidence ahead of the prose once the score settles', async () => {
    const { ScamScanView } = await import('./ScamScanView');
    const { container } = render(
      React.createElement(ScamScanView, { onScanComplete: vi.fn(), isOnline: true })
    );
    await scanAndSettle();

    await waitFor(() => {
      // Which group leads is expressed as `order` on the flex parent, so this
      // asserts that. The DOM order is deliberately constant, and happy-dom
      // performs no flex layout, so a visual assertion here would pass no
      // matter what the classes said.
      const evidence = container.querySelector('[data-group="evidence"]')!;
      const prose = container.querySelector('[data-group="prose"]')!;
      expect(evidence.className).toContain('order-1');
      expect(prose.className).toContain('order-2');
    });
  });

  it('keeps both groups mounted so nothing is torn down on a score change', async () => {
    const { ScamScanView } = await import('./ScamScanView');
    const { container } = render(
      React.createElement(ScamScanView, { onScanComplete: vi.fn(), isOnline: true })
    );
    await scanAndSettle();

    // A remount would reset a collapsed Sources disclosure and lose the block
    // FLIP needs in order to animate it.
    expect(container.querySelector('[data-group="evidence"]')).toBeTruthy();
    expect(container.querySelector('[data-group="prose"]')).toBeTruthy();
  });

  it('marks the verification section with the risk accent for a critical score', async () => {
    const { ScamScanView } = await import('./ScamScanView');
    const { container } = render(
      React.createElement(ScamScanView, { onScanComplete: vi.fn(), isOnline: true })
    );
    await scanAndSettle();

    await waitFor(() => {
      // Scoped to the verification section, because RedFlagsList is already
      // error-coloured and would satisfy any search over the whole panel.
      const heading = screen.getByText('External Verification');
      const section = heading.closest('div[class*="rounded-xl"]') as HTMLElement;
      expect(section.className).toContain('bg-error-container/10');
      expect(section.className).toContain('border-error/40');
    });
  });

  it('leaves the prose ahead while verification is still running', async () => {
    // Reordering on the posting-stage level would move the evidence out from
    // under the reader and then move it back once the employer score lands.
    mocks.verifyJobStream.mockImplementation(() => new Promise(() => {}));

    const { ScamScanView } = await import('./ScamScanView');
    const { container } = render(
      React.createElement(ScamScanView, { onScanComplete: vi.fn(), isOnline: true })
    );

    await act(async () => {
      mocks.messageHandler?.({
        source: 'trabahero-picker',
        action: 'ELEMENT_SELECTED',
        payload: { bounds: { x: 0, y: 0, width: 800, height: 600 } },
      });
      await new Promise((r) => setTimeout(r, 10));
    });
    const scanBtn = await screen.findByRole('button', { name: /Scan \(\d+\)/ }, { timeout: 3000 });
    await act(async () => { fireEvent.click(scanBtn); });

    await waitFor(
      () => expect(screen.getByText(/Asks applicants to pay a processing fee/)).toBeTruthy(),
      { timeout: 3000 }
    );

    const evidence = container.querySelector('[data-group="evidence"]')!;
    const prose = container.querySelector('[data-group="prose"]')!;
    expect(prose.className).toContain('order-1');
    expect(evidence.className).toContain('order-2');
  });
});
