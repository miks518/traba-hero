import { describe, it, expect, afterEach } from 'vitest';
import { render, cleanup } from '@testing-library/react';
import React from 'react';
import { ActionBlock } from './ActionBlock';
import type { Verdict } from '../../types';

/**
 * The action block used to speak only from its authored table, keyed to the
 * verdict family alone. A `caution` posting got the same two sentences whether
 * the fee was ₱150 to a GCash account or an unexplained "training kit" —
 * generic advice that does not refer to the thing being assessed, which the
 * design record already named as a failure shape for the chips row.
 *
 * Verify writes a recommendation for the checked posting, and the backend
 * screens it before it reaches the wire (`clean_recommendation`: an accusation,
 * hedge or absolute becomes absent). So the block renders that text when it
 * exists and falls back to the authored copy in the states verification did
 * not reach — no run yet, an error, a rejected recommendation.
 *
 * The bullet colour stays code-owned in both branches: text may be the model's,
 * colour may not.
 */

afterEach(cleanup);

function block(props: {
  verdict?: Verdict | null;
  recommendation?: string;
}): string {
  const { container } = render(
    React.createElement(ActionBlock, {
      verdict: props.verdict ?? null,
      recommendation: props.recommendation,
    }),
  );
  return container.querySelector('[data-role="action-block"]')?.textContent ?? '';
}

describe('the action block prefers the verify recommendation', () => {
  it('renders the recommendation when verification produced one', () => {
    const text = block({
      verdict: 'caution',
      recommendation: 'The results show no company named QuickCash Solutions. Ask the poster to confirm the fee recipient in writing.',
    });

    expect(text).toContain('Ask the poster to confirm the fee recipient in writing.');
    expect(text).not.toContain('Ask who receives the fee and why.');
  });

  it('renders one row, not the authored pair, when the recommendation stands', () => {
    const text = block({
      verdict: 'stop',
      recommendation: 'A retrieved source accounts for this request.',
    });

    // The authored second line must be absent alongside a recommendation.
    expect(text).not.toContain('Check the company yourself');
  });

  it('falls back to the authored copy when no recommendation arrived', () => {
    const text = block({ verdict: 'stop' });

    expect(text).toContain('Do not send money or documents.');
    expect(text).toContain('Check the company yourself');
  });

  it('falls back when the recommendation is blank', () => {
    // The backend sends an empty string for a screened-out recommendation; the
    // authored table is the safe and still-actionable degradation.
    const text = block({ verdict: 'caution', recommendation: '   ' });

    expect(text).toContain('Ask who receives the fee and why.');
  });

  it('renders the code-authored fallback recommendation on the no-verdict path', () => {
    // A recommendation with a null verdict is a real state on the wire: the
    // no-employer path and the search-failed path both send a code-authored
    // fallback recommendation with `verdict: null`. That text is authored, not
    // model-written, so it outranks the generic table and the grey bullet is
    // the honest tone for it.
    const text = block({ verdict: null, recommendation: 'Confirm the employer independently before submitting personal details.' });

    expect(text).toContain('Confirm the employer independently before submitting personal details.');
    expect(text).not.toContain('No verdict on this one.');
  });
});
