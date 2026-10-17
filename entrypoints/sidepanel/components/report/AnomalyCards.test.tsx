import { describe, it, expect, afterEach } from 'vitest';
import { render, cleanup } from '@testing-library/react';
import React from 'react';
import { AnomalyCards } from './AnomalyCards';
import { VerdictBlock } from './VerdictBlock';
import { mapApiResponse } from '../../lib/mapApiResponse';
import type { Anomaly, ApiScanResponse } from '../../types';

/**
 * The three slots the backend reopened: the rule code, the posting's own words,
 * and the one-line verdict reason.
 *
 * Each of these was rendered as *absent* while its field did not exist, and each
 * comes back with a degradation that matters more than the happy path. The
 * backend screens a quotation and caps a reason; the panel's job is to make an
 * absent one invisible rather than to render an empty shell or, worse, to
 * substitute something it was told not to reuse.
 */

afterEach(cleanup);

function anomaly(over: Partial<Anomaly> = {}): Anomaly {
  return {
    id: 'a',
    title: 'Asks applicants for a processing fee',
    description: 'The post asks for money up front.',
    icon: 'warning',
    severity: 'high',
    ...over,
  };
}

function scanResponse(over: Partial<ApiScanResponse> = {}): ApiScanResponse {
  return {
    valid: true,
    anomalies: [],
    job_summary: 'Sales associate wanted',
    ...over,
  } as ApiScanResponse;
}

describe('the rule code pill', () => {
  it('shows the code the scan carried', () => {
    const { container } = render(
      React.createElement(AnomalyCards, {
        anomalies: [anomaly({ code: 'FEE_MANDATORY' })],
      }),
    );
    expect(container.textContent).toContain('FEE_MANDATORY');
  });

  it('shows the escape valve rather than hiding it', () => {
    // `OTHER` is the drift signal the taxonomy exists to produce. A panel that
    // hid it would make the rate unmeasurable, which is the one thing the escape
    // valve is for.
    const { container } = render(
      React.createElement(AnomalyCards, {
        anomalies: [anomaly({ code: 'OTHER' })],
      }),
    );
    expect(container.textContent).toContain('OTHER');
  });

  it('shows nothing for a scan predating the field', () => {
    // Absent is not OTHER. Defaulting it would put a taxonomy ID on every scan
    // in history that was taken before the taxonomy existed.
    const { container } = render(
      React.createElement(AnomalyCards, { anomalies: [anomaly({ code: undefined })] }),
    );
    const card = container.querySelector('article');
    expect(card?.querySelector('.code-pill')).toBeNull();
  });

  it('never substitutes the free-text title for a missing code', () => {
    // A code pill that is really a sentence in a monospace font is the one place
    // a reader looks up a taxonomy and finds prose instead.
    const { container } = render(
      React.createElement(AnomalyCards, {
        anomalies: [anomaly({ code: undefined, title: 'Asks for money' })],
      }),
    );
    expect(container.querySelector('.code-pill')).toBeNull();
  });
});

describe("the posting's own words", () => {
  it('shows a quote that survived screening', () => {
    const { container } = render(
      React.createElement(AnomalyCards, {
        anomalies: [anomaly({ quote: 'a refundable 150 starter kit fee' })],
      }),
    );
    const well = container.querySelector('.quote-well');
    expect(well).toBeTruthy();
    expect(well?.textContent).toContain('a refundable 150 starter kit fee');
    expect(well?.textContent?.toLowerCase()).toContain('from the post');
  });

  it('degrades to the explanation when there is no quote', () => {
    // The honest degradation, and the whole reason the field is screened: an
    // empty quotation block would read as "the posting said nothing here", which
    // is a claim about the posting rather than about our screening.
    const { container } = render(
      React.createElement(AnomalyCards, {
        anomalies: [anomaly({ quote: undefined, description: 'The post asks for money up front.' })],
      }),
    );
    expect(container.querySelector('.quote-well')).toBeNull();
    expect(container.textContent).toContain('The post asks for money up front.');
  });

  it('does not highlight anything, because nothing says which phrase decided it', () => {
    // The design bolds the deciding span. There is no field for it, so
    // highlighting the whole quote would be decoration pretending to be an
    // analysis, and guessing at the middle of it would be worse.
    const { container } = render(
      React.createElement(AnomalyCards, {
        anomalies: [anomaly({ quote: 'some span from the post' })],
      }),
    );
    expect(container.querySelector('.quote-badge')).toBeNull();
  });
});

describe('the one-line verdict reason', () => {
  it('shows a reason beside the authored headline', () => {
    render(
      React.createElement(VerdictBlock, {
        level: 'critical',
        reason: 'This post asks you to pay a fee before you are hired.',
      }),
    );
    const headline = document.querySelector('[data-role="verdict-headline"]');
    const reason = document.querySelector('[data-role="verdict-reason"]');
    expect(headline?.textContent).toBe('Do not proceed');
    expect(reason?.textContent).toContain('pay a fee');
  });

  it('renders a complete banner with no reason at all', () => {
    // A banner carrying only its authored headline is complete — the instruction
    // stands on its own — so an absent reason must not leave a gap that reads as
    // something withheld.
    render(React.createElement(VerdictBlock, { level: 'high' }));
    expect(document.querySelector('[data-role="verdict-headline"]')?.textContent).toBe(
      'Do not proceed without checking first',
    );
    expect(document.querySelector('[data-role="verdict-reason"]')).toBeNull();
  });

  it('shows no reason while the lookup is still running', () => {
    // The intermediate level is not the verdict, so nothing that reads as a
    // conclusion sits under it either.
    render(
      React.createElement(VerdictBlock, {
        level: 'high',
        verifying: true,
        reason: 'This post asks you to pay a fee.',
      }),
    );
    expect(document.querySelector('[data-role="verdict-reason"]')).toBeNull();
    expect(document.querySelector('[data-role="verdict-headline"]')?.textContent).toBe(
      'Checking this company',
    );
  });
});

describe('the wire mapping', () => {
  it('carries the code and quote through, and absent stays absent', () => {
    const mapped = mapApiResponse(
      scanResponse({
        anomalies: [
          { flag: 'Fee', reasoning: 'why', severity: 'high', code: 'FEE_MANDATORY', quote: 'a fee' },
          { flag: 'Old', reasoning: 'why', severity: 'low' },
        ],
      }),
    );

    expect(mapped.anomalies[0].code).toBe('FEE_MANDATORY');
    expect(mapped.anomalies[0].quote).toBe('a fee');
    // Not defaulted to OTHER, and not defaulted to ''. Both would be claims.
    expect(mapped.anomalies[1].code).toBeUndefined();
    expect(mapped.anomalies[1].quote).toBeUndefined();
  });

  it('synthesises no score when the backend sent none', () => {
    // The standing rule. `0` would render as the bottom of a scale, claiming the
    // posting was assessed and came out clean.
    const mapped = mapApiResponse(
      scanResponse({ risk_level: undefined, risk_score: undefined }),
    );
    expect(mapped.riskScore).toBeNull();
    expect(mapped.riskScored).toBe(false);
  });
});
