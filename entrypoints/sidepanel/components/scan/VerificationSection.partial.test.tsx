import { describe, it, expect } from 'vitest';
import React from 'react';
import { render } from '@testing-library/react';
import { VerificationSection } from './VerificationSection';
import type { VerificationResult } from '../../types';

/**
 * A partial lookup is the state two queries created: one succeeded and one
 * failed. The findings are real, so the cards stay — but the reader has to be
 * told that some categories were covered by a thinner search than the panel's
 * confident layout implies. Silently rendering the same card set as a complete
 * lookup is the overstatement this project keeps guarding against.
 *
 * This asserts on rendered text, not pixels. `happy-dom` performs no flex layout
 * and zeroes every `getBoundingClientRect()`, so a colour or spacing claim
 * cannot be checked here — only whether the warning is said, and when.
 */

const result = (over: Partial<VerificationResult> = {}): VerificationResult => ({
  items: [
    { label: 'Company Existence', status: 'green', explanation: 'A business by that name operates at 12 Katipunan Ave.' },
    { label: 'Official Registration', status: 'yellow', explanation: 'The results do not mention a registration.' },
    { label: 'Reputation', status: 'yellow', explanation: 'The results do not mention this category.' },
  ],
  evidence: [],
  report: 'The results show a business operating under the searched name.',
  recommendation: 'Ask them to confirm the address in writing.',
  ...over,
});

const renderSection = (over: Partial<VerificationResult> = {}) =>
  render(React.createElement(VerificationSection, { result: result(over) }));

describe('partial search coverage is stated', () => {
  it('warns when one of the searches failed', () => {
    const { container } = renderSection({ searchOk: true, searchPartial: true, queriesIssued: 2, queriesFailed: 1 });
    const text = container.textContent ?? '';

    expect(text).toMatch(/1 of 2 searches failed/i);
  });

  it('says it is not a finding about the employer', () => {
    // The existing "Search Unavailable" notice does this. A partial lookup has
    // the same hazard: a reader could take a thin category for a negative one.
    const { container } = renderSection({ searchPartial: true });
    const text = (container.textContent ?? '').toLowerCase();

    expect(text).toMatch(/not a finding/);
  });

  it('still renders the findings a successful search produced', () => {
    const { container } = renderSection({ searchPartial: true });

    expect(container.textContent).toMatch(/Company Existence/);
    expect(container.textContent).toMatch(/Official Registration/);
  });

  it('says nothing when the lookup was complete', () => {
    const { container } = renderSection({ searchOk: true, searchPartial: false });

    expect(container.textContent).not.toMatch(/searches failed/i);
  });

  it('says nothing when the field is absent, as on an older backend', () => {
    const { container } = renderSection({ searchOk: true });

    expect(container.textContent).not.toMatch(/searches failed/i);
  });

  it('does not claim a total failure', () => {
    // `searchOk: false` is a different state with its own notice. Showing both
    // would tell the reader nothing was retrieved and something was.
    const { container } = renderSection({ searchPartial: true });
    const text = container.textContent ?? '';

    expect(text).not.toMatch(/Search Unavailable/);
  });
});
