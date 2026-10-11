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
  anomalies: [],
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

/**
 * The panel has to hand `/api/verify` the posting's own stated details.
 *
 * These four fields are what the backend builds its scheme queries from, and
 * they are quoted back to the model as the claims that `Location / Branch`,
 * `Channel Match` and `Scheme Corroboration` test. Without them every
 * verification issues the same two employer queries — and the three categories
 * that exist to catch an impersonation of a real company are structurally
 * unable to redden.
 *
 * The whole design sat inert behind this one field, and nothing said so: the
 * backend accepted `attributes`, defaulted it to `{}`, and returned a perfectly
 * ordinary-looking result. The backend's own test closes the schema → prompt
 * loop by POSTing `attributes` by hand, so it cannot see a client that never
 * sends them. This drives the real component and asserts what it asks for.
 */
describe('the scan response reaches the verify request', () => {
  const scanWithAttributes = {
    ...scanResponse,
    attributes: {
      COMPANY: 'Tanika',
      LOCATION: 'Maingate Terminal',
      CONTACT_METHOD: 'personal Gmail',
      MEETING_SPOT: 'Maingate Terminal',
    },
  };

  beforeEach(() => {
    mocks.scanScreenshotStream.mockImplementation(async (_imgs, _sig, onProgress) => {
      onProgress?.({ percent: 50, stage: 'Analyzing' });
      return { response: scanWithAttributes };
    });
    mocks.verifyJobStream.mockImplementation(async () => ({ result: verifyResponse }));
    mocks.analyzeOfferStream.mockResolvedValue({ data: null });
  });

  it('asks /api/verify about what the posting says about itself', async () => {
    const { ScamScanView } = await import('./ScamScanView');
    render(React.createElement(ScamScanView, { onScanComplete: vi.fn(), isOnline: true }));

    await pickElement();
    await clickScan();

    await waitFor(() => expect(mocks.verifyJobStream).toHaveBeenCalled(), { timeout: 3000 });
    const [context] = mocks.verifyJobStream.mock.calls[0];

    // The assertion is on the values, not on the key being present: a client
    // that sent `attributes: {}` would satisfy a `toBeDefined()` and leave
    // every scheme query unbuilt.
    expect(context.attributes).toEqual(scanWithAttributes.attributes);
  });

  it('still names the employer alongside them', async () => {
    // The overcorrection. Forwarding attributes is not a replacement for the
    // employer query, and a panel that sent only the attributes would produce a
    // verification about a bus terminal.
    const { ScamScanView } = await import('./ScamScanView');
    render(React.createElement(ScamScanView, { onScanComplete: vi.fn(), isOnline: true }));

    await pickElement();
    await clickScan();

    await waitFor(() => expect(mocks.verifyJobStream).toHaveBeenCalled(), { timeout: 3000 });
    const [context] = mocks.verifyJobStream.mock.calls[0];

    expect(context.company_name).toBe('Acme Trading');
    expect(context.attributes).toBeTruthy();
  });

  it('sends no attributes when the scan reported none', async () => {
    // A posting that states no checkable detail must still verify, at the two
    // employer queries. Passing `undefined` rather than fabricating keys is what
    // keeps a sparse posting costing what it cost before.
    mocks.scanScreenshotStream.mockImplementation(async (_imgs, _sig, onProgress) => {
      onProgress?.({ percent: 50, stage: 'Analyzing' });
      const { attributes: _omitted, ...without } = scanWithAttributes;
      return { response: without };
    });

    const { ScamScanView } = await import('./ScamScanView');
    render(React.createElement(ScamScanView, { onScanComplete: vi.fn(), isOnline: true }));

    await pickElement();
    await clickScan();

    await waitFor(() => expect(mocks.verifyJobStream).toHaveBeenCalled(), { timeout: 3000 });
    const [context] = mocks.verifyJobStream.mock.calls[0];

    expect(context.company_name).toBe('Acme Trading');
    expect(context.attributes ?? {}).toEqual({});
  });
});

/**
 * The line under the gauge must say whether the employer was *looked up*, not
 * whether the lookup changed the number.
 *
 * It used to read `scoreBreakdown.sources`, which names the stages that
 * contributed a value. The refutation stage contributes nothing when it refutes
 * nothing, so `sources` read `['posting']` after a lookup that ran and confirmed
 * every claim — and the panel then told the reader their employer had never been
 * checked. That is the overwhelmingly common successful outcome, so the panel
 * was wrong in its best case.
 *
 * `describeScoreBasis` is unit-tested in riskDisplay.test.ts. This drives the
 * real component through all four outcomes, because the derivation of
 * *which* outcome it is — the part that was actually wrong — lives in the view
 * and no unit test of the formatter can reach it.
 *
 * happy-dom performs no layout, so these assert rendered text only.
 */
describe('what the score line claims about the employer', () => {
  beforeEach(() => {
    mocks.scanScreenshotStream.mockImplementation(async (_imgs, _sig, onProgress) => {
      onProgress?.({ percent: 50, stage: 'Analyzing' });
      return { response: scanResponse };
    });
    mocks.analyzeOfferStream.mockResolvedValue({ data: null });
  });

  /** Run a scan whose verification returns `verify`, then read the line. */
  async function lineAfter(verify: Record<string, unknown> | null) {
    const { ScamScanView } = await import('./ScamScanView');
    if (verify === null) {
      mocks.verifyJobStream.mockRejectedValue(new Error('network down'));
    } else {
      mocks.verifyJobStream.mockImplementation(async () => ({ result: verify }));
    }

    const { container } = render(
      React.createElement(ScamScanView, { onScanComplete: vi.fn(), isOnline: true })
    );
    await pickElement();
    await clickScan();

    await waitFor(
      () => {
        const el = container.querySelector('[data-role="score-basis"]');
        if (!el) throw new Error('score line not rendered yet');
      },
      { timeout: 3000 }
    );
    return container.querySelector('[data-role="score-basis"]')!.textContent ?? '';
  }

  it('credits the web evidence when a claim was refuted', async () => {
    const line = await lineAfter({
      ...verifyResponse,
      items: [
        { label: 'Channel Match', status: 'red', explanation: 'Their site is acme.com.', source_title: '', source_url: '' },
      ],
      scoreBreakdown: { posting: 12, refutation: 25, sources: ['posting', 'verification'] },
    });

    expect(line).toMatch(/web evidence/i);
    expect(line).not.toMatch(/not checked/i);
  });

  it('does not claim the employer was unchecked after a lookup confirmed everything', async () => {
    // The regression, at the level it broke. `sources` is ['posting'] here,
    // because a lookup that refutes nothing contributes nothing to the score —
    // and keying the copy off that said the employer had never been checked.
    const line = await lineAfter({
      ...verifyResponse,
      // The scan in this file has no anomalies, so nothing was refuted.
      scoreBreakdown: { posting: 0, refutation: null, sources: ['posting'] },
    });

    expect(line).not.toMatch(/not checked/i);
    expect(line).toMatch(/no source contradicted/i);
  });

  it('says the lookup did not complete when it failed', async () => {
    // A lookup that failed is not a lookup that never ran. Sending the reader
    // to look for a check that did happen is the cost of conflating them.
    // `searchOk` camelCase: the mock replaces lib/api, which is the boundary
    // where the wire's snake_case is translated, so fixtures must be the
    // translated shape.
    const line = await lineAfter({
      ...verifyResponse,
      searchOk: false,
      searchError: 'TAVILY_API_KEY is not configured',
      scoreBreakdown: { posting: 0, refutation: null, sources: ['posting'] },
    });

    expect(line).toMatch(/did not complete/i);
    expect(line).not.toMatch(/was not checked/i);
  });

  it('says the lookup did not complete when the request errored outright', async () => {
    // No result at all, and a flag saying so. Reporting that as "the employer
    // was not checked" would send the reader looking for a check that was
    // attempted and could not finish.
    const line = await lineAfter(null);

    expect(line).toMatch(/did not complete/i);
    expect(line).not.toMatch(/was not checked/i);
  });

  it('says the employer was not checked when there was no employer to look up', async () => {
    // The genuine `never` case: no verification was ever attempted, because
    // the posting named nobody. `CompanyNameNeeded` says this in more detail
    // below, but the number under the gauge still rests on the posting alone
    // and has to say so.
    mocks.scanScreenshotStream.mockImplementation(async (_imgs, _sig, onProgress) => {
      onProgress?.({ percent: 50, stage: 'Analyzing' });
      return {
        response: {
          ...scanResponse,
          company_name: null,
          verification_context: undefined,
        },
      };
    });

    const { ScamScanView } = await import('./ScamScanView');
    const { container } = render(
      React.createElement(ScamScanView, { onScanComplete: vi.fn(), isOnline: true })
    );
    await pickElement();
    await clickScan();

    await waitFor(
      () => {
        if (!container.querySelector('[data-role="score-basis"]')) {
          throw new Error('score line not rendered yet');
        }
      },
      { timeout: 3000 }
    );
    const line = container.querySelector('[data-role="score-basis"]')!.textContent ?? '';

    expect(line).toMatch(/was not checked/i);
    expect(mocks.verifyJobStream).not.toHaveBeenCalled();
  });

  it('never renders the two-sentence pair this replaced', async () => {
    // Both strings were live at once and could contradict each other. A
    // regression here means one of them is back.
    const line = await lineAfter({
      ...verifyResponse,
      items: [
        { label: 'Channel Match', status: 'red', explanation: 'x', source_title: '', source_url: '' },
      ],
      scoreBreakdown: { posting: 12, refutation: 25, sources: ['posting', 'verification'] },
    });

    expect(line).not.toMatch(/Based only on what the offer itself states/i);
  });
});
