import { describe, it, expect, afterEach } from 'vitest';
import { render, cleanup } from '@testing-library/react';
import React from 'react';
import { AnomalyCards } from './AnomalyCards';
import { AssessmentBlock } from './AssessmentBlock';
import { mapApiResponse } from '../../lib/mapApiResponse';
import type { Anomaly, ApiScanResponse } from '../../types';

/**
 * The three slots the backend reopened: the rule code, the posting's own words,
 * and the one-line assessment reason.
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
    code: 'FEE_MANDATORY',
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

describe('the one-line assessment reason', () => {
  it('shows a reason beside the authored headline', () => {
    render(
      React.createElement(AssessmentBlock, {
        assessment: 'red',
        reason: 'This post asks you to pay a fee before you are hired.',
      }),
    );
    const headline = document.querySelector('[data-role="assessment-headline"]');
    const reason = document.querySelector('[data-role="assessment-reason"]');
    expect(headline?.textContent).toBe('Contradicted');
    expect(reason?.textContent).toContain('pay a fee');
  });

  it('renders a complete banner with no reason at all', () => {
    // A banner carrying only its authored headline is complete — the instruction
    // stands on its own — so an absent reason must not leave a gap that reads as
    // something withheld.
    render(React.createElement(AssessmentBlock, { assessment: 'yellow' }));
    expect(document.querySelector('[data-role="assessment-headline"]')?.textContent).toBe(
      'Caution',
    );
    expect(document.querySelector('[data-role="assessment-reason"]')).toBeNull();
  });

  it('shows no reason while the lookup is still running', () => {
    // The intermediate assessment is not the assessment, so nothing that reads as a
    // conclusion sits under it either.
    render(
      React.createElement(AssessmentBlock, {
        assessment: 'yellow',
        verifying: true,
        reason: 'This post asks you to pay a fee.',
      }),
    );
    expect(document.querySelector('[data-role="assessment-reason"]')).toBeNull();
    expect(document.querySelector('[data-role="assessment-headline"]')?.textContent).toBe(
      'Checking this job post',
    );
  });
});

describe('the evidence assessment on a finding', () => {
  it('checks without asserting a severity while the lookup runs', () => {
    // The finding is visible from the moment the scan lands, but nothing about
    // its final weight is: the scan's severity is what verification may change.
    const { container } = render(
      React.createElement(AnomalyCards, { anomalies: [anomaly()], checking: true }),
    );
    const card = container.querySelector('[data-role="anomaly-card"]');
    const status = card?.querySelector('[role="status"]');

    expect(card?.getAttribute('data-state')).toBe('checking');
    expect(card?.textContent).toContain('Checking');
    expect(card?.textContent).not.toContain('Critical');
    expect(status?.getAttribute('aria-busy')).toBe('true');
  });

  it('keeps the heading and the count while checking', () => {
    // The count is measured against the panel; a loading state that hid it
    // would make the count depend on whether verification had finished.
    const { container } = render(
      React.createElement(AnomalyCards, { anomalies: [anomaly()], checking: true }),
    );
    expect(container.textContent).toContain('Anomalies detected');
    expect(container.textContent).toContain('1 found');
  });

  it('retires a stale finding in grey, with the source that accounts for it', () => {
    const { container } = render(
      React.createElement(AnomalyCards, {
        anomalies: [
          anomaly({
            assessment: {
              status: 'stale',
              finding: 'The careers page lists the exam fee as paid before deployment.',
              sourceTitle: 'Careers',
              sourceUrl: 'https://employer.example/careers',
            },
          }),
        ],
      }),
    );
    const card = container.querySelector('[data-role="anomaly-card"]');
    const link = card?.querySelector('[data-role="anomaly-source"]');

    expect(card?.getAttribute('data-state')).toBe('stale');
    expect(card?.textContent).toContain('Stale');
    expect(card?.textContent).not.toContain('Critical');
    expect(card?.querySelector('.chip-stale')).toBeTruthy();
    expect(card?.querySelector('.status-card-stale')).toBeTruthy();
    expect(link?.getAttribute('href')).toBe('https://employer.example/careers');
    expect(link?.textContent).toContain('Careers');
  });

  it('shows the evidence state, not a model judgement, when a source contradicts the finding', () => {
    // The scan carried this finding with a fee-demand code, and that is not
    // what the chip says. Pricing a finding from the model's own weight is the
    // pattern the assessment moved into code to remove; the chip reports what
    // the evidence found.
    const { container } = render(
      React.createElement(AnomalyCards, {
        anomalies: [
          anomaly({
            assessment: {
              status: 'contradicted',
              finding: 'The employer states on its own page that no fee is charged.',
              sourceTitle: 'Careers',
              sourceUrl: 'https://employer.example/careers',
            },
          }),
        ],
      }),
    );
    const card = container.querySelector('[data-role="anomaly-card"]');

    expect(card?.getAttribute('data-state')).toBe('contradicted');
    expect(card?.textContent).toContain('Contradicted');
    expect(card?.textContent).toContain('Contradicted by a public source');
    expect(card?.querySelector('.status-card-critical')).toBeTruthy();
    expect(card?.querySelector('[data-role="anomaly-source"]')).toBeTruthy();
  });

  it('shows an unresolved finding as amber, not as a pass', () => {
    const { container } = render(
      React.createElement(AnomalyCards, {
        anomalies: [
          anomaly({
            assessment: {
              status: 'unknown',
              finding: 'The results do not mention this fee.',
            },
          }),
        ],
      }),
    );
    const card = container.querySelector('[data-role="anomaly-card"]');

    expect(card?.getAttribute('data-state')).toBe('unknown');
    expect(card?.textContent).toContain('Not confirmed');
    expect(card?.querySelector('.chip-caution')).toBeTruthy();
    expect(card?.querySelector('.status-card-caution')).toBeTruthy();
    // No source is named because none was relied on.
    expect(card?.querySelector('[data-role="anomaly-source"]')).toBeNull();
  });

  it('demotes a stale finding that lost its source', () => {
    // The backend already demotes one, but the card is the last place a retired
    // finding can appear without evidence, and "stale" is the assertion that
    // retires it.
    const { container } = render(
      React.createElement(AnomalyCards, {
        anomalies: [
          anomaly({
            assessment: { status: 'stale', finding: 'A source accounted for it.' },
          }),
        ],
      }),
    );
    const card = container.querySelector('[data-role="anomaly-card"]');

    expect(card?.getAttribute('data-state')).toBe('unknown');
    expect(card?.textContent).not.toContain('Stale');
    expect(card?.textContent).toContain('not confirmed');
  });

  it('says no employer was named instead of spinning forever', () => {
    const { container } = render(
      React.createElement(AnomalyCards, {
        anomalies: [anomaly()],
        needsCompanyName: true,
      }),
    );
    const card = container.querySelector('[data-role="anomaly-card"]');

    expect(card?.getAttribute('data-state')).toBe('unknown');
    expect(card?.textContent).toContain('names no employer');
    expect(card?.querySelector('[role="status"]')).toBeNull();
  });

  it('shows a failed lookup as amber, with no spinner left running', () => {
    const { container } = render(
      React.createElement(AnomalyCards, {
        anomalies: [anomaly()],
        verificationError: true,
      }),
    );
    const card = container.querySelector('[data-role="anomaly-card"]');

    expect(card?.getAttribute('data-state')).toBe('unknown');
    expect(card?.textContent).toContain('did not finish');
    expect(card?.querySelector('[role="status"]')).toBeNull();
  });

  it('tells an old reading apart from one the check could not settle', () => {
    const old = render(
      React.createElement(AnomalyCards, { anomalies: [anomaly()], assessmentRun: false }),
    );
    expect(old.container.textContent).toContain('saved before');

    cleanup();

    const ran = render(
      React.createElement(AnomalyCards, { anomalies: [anomaly()], assessmentRun: true }),
    );
    expect(ran.container.textContent).toContain('No evidence assessment was recorded');
  });

  it('lets the checking state override a assessment left from an earlier run', () => {
    const { container } = render(
      React.createElement(AnomalyCards, {
        anomalies: [
          anomaly({
            assessment: {
              status: 'stale',
              finding: 'A previous run found this.',
              sourceUrl: 'https://employer.example/careers',
            },
          }),
        ],
        checking: true,
      }),
    );
    const card = container.querySelector('[data-role="anomaly-card"]');

    expect(card?.getAttribute('data-state')).toBe('checking');
    expect(card?.querySelector('.chip-stale')).toBeNull();
  });
});

describe('the wire mapping', () => {
  it('carries the code and quote through, and absent stays absent', () => {
    const mapped = mapApiResponse(
      scanResponse({
        anomalies: [
          { flag: 'Fee', reasoning: 'why', code: 'FEE_MANDATORY', quote: 'a fee' },
          { flag: 'Old', reasoning: 'why' },
        ],
      }),
    );

    expect(mapped.anomalies[0].code).toBe('FEE_MANDATORY');
    expect(mapped.anomalies[0].quote).toBe('a fee');
    // Not defaulted to OTHER, and not defaulted to ''. Both would be claims.
    expect(mapped.anomalies[1].code).toBeUndefined();
    expect(mapped.anomalies[1].quote).toBeUndefined();
  });

  it('synthesises no assessment when the backend sent none', () => {
    // The standing rule. A assessment would render as an assessment the system never made.
    const mapped = mapApiResponse(
      scanResponse({ assessment: undefined }),
    );
    expect(mapped.assessment).toBeNull();
    expect(mapped.assessed).toBe(false);
  });
});
