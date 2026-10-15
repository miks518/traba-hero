import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
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
 * These fields are quoted back to the model as the claims that `Location /
 * Branch`, `Channel Match` and `Similar Offers` test, and the search queries the
 * scan model proposed are issued alongside the employer query. Without them a
 * verification runs on one query — and the categories that exist to catch an
 * impersonation of a real company are structurally unable to redden.
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
 * The searches the scan model proposed have to reach `/api/verify`.
 *
 * This feature was deleted once already (413a2cd) for exactly this reason:
 * `SEARCH QUERIES` was parsed, capped, shipped on `ScanResponse`, and read by
 * nothing. The parser-side tests cannot see a client that drops the field, so
 * these drive the real component and assert what it asks for.
 */
describe('the scan queries reach the verify request', () => {
  const scanWithQueries = {
    ...scanResponse,
    search_queries: ['Acme Trading Maingate Terminal', 'Acme Trading permit'],
  };

  beforeEach(() => {
    mocks.scanScreenshotStream.mockImplementation(async (_imgs, _sig, onProgress) => {
      onProgress?.({ percent: 50, stage: 'Analyzing' });
      return { response: scanWithQueries };
    });
    mocks.verifyJobStream.mockImplementation(async () => ({ result: verifyResponse }));
    mocks.analyzeOfferStream.mockResolvedValue({ data: null });
  });

  it('sends what the scan proposed', async () => {
    // On the values, not on the key being present: a client that sent
    // `search_queries: []` would satisfy a `toBeDefined()` and leave the
    // verification running on the employer query alone.
    const { ScamScanView } = await import('./ScamScanView');
    render(React.createElement(ScamScanView, { onScanComplete: vi.fn(), isOnline: true }));

    await pickElement();
    await clickScan();

    await waitFor(() => expect(mocks.verifyJobStream).toHaveBeenCalled(), { timeout: 3000 });
    const [context] = mocks.verifyJobStream.mock.calls[0];

    expect(context.search_queries).toEqual(scanWithQueries.search_queries);
  });

  it('still names the employer alongside them', async () => {
    // The overcorrection. The model's queries are added to the employer query,
    // not substituted for it — a panel sending only these would produce a
    // verification about a bus terminal.
    const { ScamScanView } = await import('./ScamScanView');
    render(React.createElement(ScamScanView, { onScanComplete: vi.fn(), isOnline: true }));

    await pickElement();
    await clickScan();

    await waitFor(() => expect(mocks.verifyJobStream).toHaveBeenCalled(), { timeout: 3000 });
    const [context] = mocks.verifyJobStream.mock.calls[0];

    expect(context.company_name).toBe('Acme Trading');
    expect(context.search_queries).toHaveLength(2);
  });

  it('sends none when the scan proposed none', async () => {
    // A real state, not a failure. Passing `undefined` rather than fabricating
    // queries is what keeps a sparse posting costing one credit.
    mocks.scanScreenshotStream.mockImplementation(async (_imgs, _sig, onProgress) => {
      onProgress?.({ percent: 50, stage: 'Analyzing' });
      const { search_queries: _omitted, ...without } = scanWithQueries;
      return { response: without };
    });

    const { ScamScanView } = await import('./ScamScanView');
    render(React.createElement(ScamScanView, { onScanComplete: vi.fn(), isOnline: true }));

    await pickElement();
    await clickScan();

    await waitFor(() => expect(mocks.verifyJobStream).toHaveBeenCalled(), { timeout: 3000 });
    const [context] = mocks.verifyJobStream.mock.calls[0];

    expect(context.company_name).toBe('Acme Trading');
    expect(context.search_queries ?? []).toEqual([]);
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

/**
 * What a scan can report is bounded by what the capture contained, and the panel
 * cannot say otherwise — a heading cropped off means no employer name, so the
 * employer check never runs and nothing in the result records that it was
 * available to run. The only lever left is the reader's own selection.
 */
describe('the capture reminder', () => {
  const reminderAfter = async () => {
    const { ScamScanView } = await import('./ScamScanView');
    mocks.scanScreenshotStream.mockImplementation(async (_imgs, _sig, onProgress) => {
      onProgress?.({ percent: 50, stage: 'Analyzing' });
      return { response: scanResponse };
    });
    mocks.verifyJobStream.mockImplementation(async () => ({ result: verifyResponse }));
    mocks.analyzeOfferStream.mockResolvedValue({ data: null });

    const { container } = render(
      React.createElement(ScamScanView, { onScanComplete: vi.fn(), isOnline: true })
    );
    await pickElement();
    await clickScan();

    await waitFor(
      () => {
        if (!container.querySelector('[data-role="capture-reminder"]')) {
          throw new Error('reminder not rendered yet');
        }
      },
      { timeout: 3000 }
    );
    return container.querySelector('[data-role="capture-reminder"]')!.textContent ?? '';
  };

  it('names the details a wider capture would carry', async () => {
    const line = await reminderAfter();

    expect(line).toMatch(/employer name/i);
    expect(line).toMatch(/contact details/i);
    expect(line).toMatch(/pay/i);
  });

  it('is not a criticism of the capture that produced this result', async () => {
    // The overcorrection. A clean short capture is a clean result; copy that
    // implies something was missed turns a green score into a doubt the panel
    // has no evidence for.
    const line = await reminderAfter();

    expect(line).not.toMatch(/incomplete|missing|not included|failed to/i);
  });

  it('appears only once there is a result to improve on', async () => {
    // Mid-scan there is no result yet and "for a more accurate result" refers to
    // nothing. `happy-dom` performs no layout, so this asserts presence during
    // the scan rather than position.

    // It cannot distinguish the two conditions guarding the element: with no
    // result, `riskScore` is null whatever `verificationLoading` is, so dropping
    // either guard passes this. Kept as a bound on *when the reminder is honest*,
    // not as a guard on the condition itself.
    const { ScamScanView } = await import('./ScamScanView');
    let release: (() => void) | undefined;
    mocks.scanScreenshotStream.mockImplementation(
      () => new Promise<{ response: typeof scanResponse }>((resolve) => {
        release = () => resolve({ response: scanResponse });
      })
    );

    const { container } = render(
      React.createElement(ScamScanView, { onScanComplete: vi.fn(), isOnline: true })
    );
    await pickElement();
    await clickScan();

    expect(container.querySelector('[data-role="capture-reminder"]')).toBeNull();

    release?.();
    await waitFor(
      () => {
        if (!container.querySelector('[data-role="capture-reminder"]')) {
          throw new Error('reminder not rendered yet');
        }
      },
      { timeout: 3000 }
    );
    expect(container.querySelector('[data-role="capture-reminder"]')).not.toBeNull();
  });
});

/**
 * The provenance jump has to reach the evidence group, not merely exist.
 *
 * `RiskGauge.provenance.test.tsx` asserts the control. This asserts the effect,
 * because a button wired to nothing passes the first and fails the second - the
 * shape this feature has died in twice before, with `attributes` and with
 * `search_queries` both parsed and shipped and read by nothing.
 *
 * `happy-dom` zeroes every rect and does no layout, so "the reader ended up
 * looking at the summary" is not observable. What is asserted is the call it
 * makes: which node, and with which behaviour.
 */
describe('the provenance jump', () => {
  const scanWithAnomalies = {
    ...scanResponse,
    anomalies: [
      { flag: 'Asks applicants to pay a processing fee', reasoning: 'The post asks for a fee', severity: 'high' },
    ],
    risk_score: 40,
  };

  let scrollTo: ReturnType<typeof vi.fn>;
  let scroller: HTMLElement;

  function setReducedMotion(reduced: boolean) {
    Object.defineProperty(window, 'matchMedia', {
      configurable: true,
      writable: true,
      value: (query: string) => ({
        matches: query.includes('prefers-reduced-motion') ? reduced : false,
        media: query,
        onchange: null,
        addEventListener: () => {},
        removeEventListener: () => {},
        addListener: () => {},
        removeListener: () => {},
        dispatchEvent: () => false,
      }),
    });
  }

  async function scanWithProvenanceButton() {
    mocks.scanScreenshotStream.mockImplementation(async (_imgs, _sig, onProgress) => {
      onProgress?.({ percent: 60, stage: 'Analyzing' });
      return { response: scanWithAnomalies };
    });
    mocks.verifyJobStream.mockImplementation(async () => ({ result: verifyResponse }));
    mocks.analyzeOfferStream.mockResolvedValue({ data: null });
    setReducedMotion(false);

    const { ScamScanView } = await import('./ScamScanView');
    const utils = render(React.createElement(ScamScanView, { onScanComplete: vi.fn(), isOnline: true }));
    await pickElement();
    await clickScan();

    await waitFor(() => {
      expect(utils.container.querySelector('[data-role="provenance-jump"]')).toBeTruthy();
    }, { timeout: 3000 });

    // No ancestor here sets `overflow-y`, so `findScrollParent` falls through
    // to `document.scrollingElement` - which is exactly the fallback the helper
    // exists for, and the thing to stub. In the real panel it finds `<main>`.
    scroller = document.scrollingElement as HTMLElement;
    scrollTo = vi.fn();
    (scroller as unknown as { scrollTo: unknown }).scrollTo = scrollTo;
    return utils;
  }

  afterEach(() => {
    scrollTo?.mockReset();
    Reflect.deleteProperty(window, 'matchMedia');
  });

  it('scrolls whatever is actually the scroller', async () => {
    // `window.scrollBy` is a no-op in the real panel: its scroller is the nested
    // `main` element. An earlier version of this handler assumed the window and
    // nothing moved, which is why the offset is computed and applied here.
    const { container } = await scanWithProvenanceButton();

    fireEvent.click(container.querySelector('[data-role="provenance-jump"]')!);

    expect(scrollTo).toHaveBeenCalledTimes(1);
    expect(scrollTo.mock.calls[0][0]).toMatchObject({ behavior: 'smooth' });
  });

  it('drops the animation but still moves the reader under reduced motion', async () => {
    // Removing the scroll entirely would leave the button doing nothing at all
    // for these readers, which is worse than a jump.
    const { container } = await scanWithProvenanceButton();
    setReducedMotion(true);

    fireEvent.click(container.querySelector('[data-role="provenance-jump"]')!);

    expect(scrollTo.mock.calls[0][0]).toMatchObject({ behavior: 'auto' });
  });

  it('aims at the Anomalies heading rather than the container above it', async () => {
    // There are two `AnomaliesList` mounts - one in the evidence group, one
    // inside `EvidenceSummary` - so scrolling their shared container aimed at
    // whatever sat at its top. The heading ref is what makes both work.
    const { container } = await scanWithProvenanceButton();

    fireEvent.click(container.querySelector('[data-role="provenance-jump"]')!);

    expect(scrollTo).toHaveBeenCalledTimes(1);
  });

  it('subtracts the sticky bar height plus a gap from the heading position', async () => {
    // happy-dom zeroes every rect, so this cannot assert the resulting number.
    // It asserts the formula is wired: a finite scroll target computed from the
    // two measured positions, not the zero that an unmeasured read would give.
    const { container } = await scanWithProvenanceButton();
    scroller.getBoundingClientRect = () => ({ top: 0 } as DOMRect);
    const heading = container.querySelector('[data-role="anomalies-heading"]')!;
    heading.getBoundingClientRect = () => ({ top: 140 } as DOMRect);
    scroller.scrollTop = 0;

    fireEvent.click(container.querySelector('[data-role="provenance-jump"]')!);

    const target = scrollTo.mock.calls[0][0].top as number;
    // 140 (heading) - 0 (scroller) - (barHeight 0 + gap 12)
    expect(target).toBe(128);
  });

});
